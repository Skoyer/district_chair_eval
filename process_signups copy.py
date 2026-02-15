import pandas as pd
from pathlib import Path
from datetime import datetime, time, timedelta
import re

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

# Folder containing your raw signup files (CSV or XLSX)
RAW_DATA_DIR = Path("raw_signups")

# Output files (you'll import these into your Excel model)
VOLUNTEER_MASTER_CSV = Path("VolunteerMaster.csv")
ASSIGNMENTS_CSV = Path("Assignments.csv")

# Election Day time window
DAY_START = time(5, 30)   # 5:30 AM
DAY_END   = time(19, 0)   # 7:00 PM

# Expected columns in raw files (map to your real names if needed)
COL_MAP = {
    "sign_up": "Sign Up",
    "start_datetime": "Start Date/Time (mm/dd/yyyy)",
    "end_datetime": "End Date/Time (mm/dd/yyyy)",
    "location": "Location",
    "item": "Item",
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email",
    "phone": "Phone",
    "phone_type": "PhoneType",
}

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def parse_time_range_from_item(item_str):
    """
    Parse strings like:
      '11am-1pm' or '12pm to 3:00 pm'
    into naive time objects (start_time, end_time).
    Returns None if parsing fails.
    """

    if not isinstance(item_str, str):
        return None

    s = item_str.lower().strip()
    # Common separators
    s = s.replace("to", "-")
    # e.g. '11am-1pm', '12pm-3:00 pm'

    # Find two time-like tokens
    # patterns like 12, 12pm, 12:30, 12:30pm, 3:00 pm etc.
    time_pattern = r"(\d{1,2}(:\d{2})?\s*(am|pm)?)"
    matches = re.findall(time_pattern, s)

    if len(matches) < 2:
        return None

    def clean_time_token(tok):
        tok = tok[0]  # full match from regex
        tok = tok.replace(" ", "")
        # If it has no am/pm, we can't safely infer -> return None
        if not ("am" in tok or "pm" in tok):
            return None
        # Add :00 if only hour
        if re.fullmatch(r"\d{1,2}(am|pm)", tok):
            tok = tok[:-2] + ":00" + tok[-2:]
        return tok

    t1 = clean_time_token(matches[0])
    t2 = clean_time_token(matches[1])
    if not t1 or not t2:
        return None

    try:
        t1_obj = datetime.strptime(t1, "%I:%M%p").time()
        t2_obj = datetime.strptime(t2, "%I:%M%p").time()
        return (t1_obj, t2_obj)
    except ValueError:
        return None


def generate_half_hour_slots(day, start_time, end_time):
    """
    Given a date `day` and start/end times (time objects),
    generate a list of 30-minute start datetimes within [start, end).
    Clamped to DAY_START and DAY_END.
    """
    # Clamp to election-day bounds
    s = max(datetime.combine(day, start_time), datetime.combine(day, DAY_START))
    e = min(datetime.combine(day, end_time),   datetime.combine(day, DAY_END))

    slots = []
    cur = s
    while cur < e:
        slots.append(cur)
        cur += timedelta(minutes=30)
    return slots


def normalize_phone(phone):
    if not isinstance(phone, str):
        return ""
    digits = re.sub(r"\D+", "", phone)
    return digits  # simple normalization


# ---------------------------------------------------------
# LOAD ALL RAW FILES
# ---------------------------------------------------------

def load_raw_signups(raw_dir: Path) -> pd.DataFrame:
    all_rows = []
    for path in raw_dir.glob("*"):
        if path.suffix.lower() not in [".csv", ".xlsx", ".xls"]:
            continue

        print(f"Loading {path.name} ...")
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        df["__source_file"] = path.name
        all_rows.append(df)

    if not all_rows:
        raise FileNotFoundError(f"No CSV/XLSX files found in {raw_dir}")

    big_df = pd.concat(all_rows, ignore_index=True)
    return big_df


# ---------------------------------------------------------
# MAIN PROCESSING
# ---------------------------------------------------------

def main():
    raw = load_raw_signups(RAW_DATA_DIR)

    # Rename columns to standardized names
    col_rename = {}
    for key, orig in COL_MAP.items():
        # tolerate small differences in capitalization
        for col in raw.columns:
            if col.strip().lower() == orig.strip().lower():
                col_rename[col] = key
    raw = raw.rename(columns=col_rename)

    required = ["sign_up", "start_datetime", "end_datetime",
                "location", "item", "first_name", "last_name"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Missing expected columns in raw data: {missing}")

    # Parse datetime columns
    raw["start_datetime"] = pd.to_datetime(raw["start_datetime"], errors="coerce")
    raw["end_datetime"]   = pd.to_datetime(raw["end_datetime"],   errors="coerce")

    # Create a volunteer key (Name + Phone) as requested
    raw["phone"] = raw.get("phone", "")
    raw["phone"] = raw["phone"].astype(str).map(normalize_phone)

    raw["first_name"] = raw["first_name"].fillna("").astype(str).str.strip()
    raw["last_name"]  = raw["last_name"].fillna("").astype(str).str.strip()

    raw["Volunteer_Key"] = (
        raw["first_name"].str.upper()
        + "_"
        + raw["last_name"].str.upper()
        + "_"
        + raw["phone"]
    )

    # Build VolunteerMaster with PastVolunteerCount
    vm_cols = ["Volunteer_Key", "first_name", "last_name", "email", "phone"]
    vm = raw[vm_cols].copy()
    vm["Past_Volunteer_Count"] = 1

    # group & sum count
    vm = (
        vm.groupby(["Volunteer_Key", "first_name", "last_name", "email", "phone"],
                   as_index=False)
          .agg({"Past_Volunteer_Count": "sum"})
    )

    vm = vm.rename(columns={
        "first_name": "First_Name",
        "last_name": "Last_Name",
        "email": "Email",
        "phone": "Phone",
    })

    # Save / append VolunteerMaster
    if VOLUNTEER_MASTER_CSV.exists():
        existing_vm = pd.read_csv(VOLUNTEER_MASTER_CSV)
        merged = pd.concat([existing_vm, vm], ignore_index=True)
        # For duplicates, keep max Past_Volunteer_Count
        merged = (
            merged.groupby(["Volunteer_Key", "First_Name", "Last_Name", "Email", "Phone"],
                           as_index=False)
                  .agg({"Past_Volunteer_Count": "max"})
        )
        merged.to_csv(VOLUNTEER_MASTER_CSV, index=False)
    else:
        vm.to_csv(VOLUNTEER_MASTER_CSV, index=False)

    print(f"VolunteerMaster written to {VOLUNTEER_MASTER_CSV}")

    # -------------------------------------------------
    # Build Assignments exploded to 30-minute slots
    # -------------------------------------------------
    assign_rows = []

    for idx, row in raw.iterrows():
        day = row["start_datetime"].date() if pd.notnull(row["start_datetime"]) else None
        if day is None:
            continue

        # 1) Try to parse a time range from 'Item'
        tr = parse_time_range_from_item(row.get("item", ""))
        if tr:
            t_start, t_end = tr
        else:
            # 2) Fall back: use the overall event start/end times
            if pd.isnull(row["end_datetime"]):
                continue
            t_start = row["start_datetime"].time()
            t_end   = row["end_datetime"].time()

        slots = generate_half_hour_slots(day, t_start, t_end)
        if not slots:
            continue

        # District name is in 'sign_up' (e.g., 'DULLES 2024 Election Day Ballot Greeters')
        district = str(row.get("sign_up", "")).split()[0].upper()

        # Precinct: from 'Location' (before comma)
        loc = str(row.get("location", ""))
        precinct_name = loc.split(",")[0].strip().upper()

        for slot_start in slots:
            slot_end = slot_start + timedelta(minutes=30)

            assign_rows.append({
                "District": district,
                "Precinct_Name": precinct_name,
                "Slot_Start": slot_start,
                "Slot_End": slot_end,
                "Volunteer_Key": row["Volunteer_Key"],
                "Role": "Poll Watcher",  # you can enhance this mapping
                "PositionNumber": 1,     # default; you can handle 2nd person later
                "__source_file": row["__source_file"],
            })

    assignments = pd.DataFrame(assign_rows)

    # Append or create Assignments CSV
    if ASSIGNMENTS_CSV.exists():
        existing_asg = pd.read_csv(ASSIGNMENTS_CSV, parse_dates=["Slot_Start", "Slot_End"])
        assignments = pd.concat([existing_asg, assignments], ignore_index=True)

    assignments.to_csv(ASSIGNMENTS_CSV, index=False)
    print(f"Assignments written to {ASSIGNMENTS_CSV}")


if __name__ == "__main__":
    main()