import pandas as pd
from pathlib import Path
from datetime import datetime, time, timedelta
import re
import shutil

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

# Folder containing your raw signup files (CSV or XLSX)
RAW_DATA_DIR = Path("raw_signups")

# Archive folder for old CSV files
ARCHIVE_DIR = Path("archive")

# Output files
VOLUNTEER_MASTER_CSV = Path("VolunteerMaster.csv")
ASSIGNMENTS_CSV = Path("Assignments.csv")
UPCOMING_ASSIGNMENTS_CSV = Path("upcoming_Assignments.csv")

# Precinct Master List (paste your 107 precincts here)
PRECINCT_MASTER_DATA = """PR_NAME	PR_NUMBER	PR_DISTRICT
CARDINAL RIDGE	123	DULLES
LITTLE RIVER	107	DULLES
TOWN HALL	121	DULLES
HUTCHISON FARM	122	DULLES
FREEDOM	112	DULLES
MERCER	108	DULLES
LIBERTY	124	DULLES
JOHN CHAMPE	319	LITTLE RIVER
STONE HILL	712	STERLING
BRAMBLETON MIDDLE	321	LITTLE RIVER
LEGACY	314	LITTLE RIVER
DULLES SOUTH	114	DULLES
MADISON	324	LITTLE RIVER
ROCK RIDGE	714	STERLING
OAK GROVE	715	STERLING
CARTER	713	STERLING
FOREST GROVE	705	STERLING
CROSON	630	BROAD RUN
STERLING	710	STERLING
SULLY	701	STERLING
MOOREFIELD STATION	628	BROAD RUN
MILL RUN	625	BROAD RUN
ROLLING RIDGE	703	STERLING
DISCOVERY	629	BROAD RUN
CLAUDE MOORE PARK	707	STERLING
INDEPENDENCE	326	LITTLE RIVER
PARK VIEW	702	STERLING
EAGLE RIDGE	616	BROAD RUN
WEST BROAD RUN	819	ASHBURN
MIRROR RIDGE	220	ALGONKIAN
ASHBY PONDS	626	BROAD RUN
WAXPOOL	825	ASHBURN
MIDDLEBURG	307	LITTLE RIVER
DOMINION TRAIL	621	BROAD RUN
SUGARLAND SOUTH	215	ALGONKIAN
SENECA	221	ALGONKIAN
CEDAR LANE	810	ASHBURN
RIDGETOP	716	STERLING
CASCADES	210	ALGONKIAN
ALDIE	309	LITTLE RIVER
COUNTRYSIDE	213	ALGONKIAN
RIVER BEND	207	ALGONKIAN
FARMWELL STATION	622	BROAD RUN
LOWES ISLAND	216	ALGONKIAN
SUGARLAND NORTH	214	ALGONKIAN
SOUTH BANK	217	ALGONKIAN
POTOMAC FALLS	209	ALGONKIAN
ALGONKIAN	208	ALGONKIAN
BELMONT STATION	820	ASHBURN
STONE BRIDGE	808	ASHBURN
GALILEE CHURCH	219	ALGONKIAN
UNIVERSITY CENTER	218	ALGONKIAN
BELMONT RIDGE	815	ASHBURN
SELDENS LANDING	813	ASHBURN
ST. LOUIS	308	LITTLE RIVER
HERITAGE	510	LEESBURG
HARPER PARK	823	ASHBURN
RIVERSIDE	822	ASHBURN
PHILOMONT	427	CATOCTIN
TOLBERT	509	LEESBURG
GREENWAY	507	LEESBURG
DOUGLASS	506	LEESBURG
RED ROCK	513	LEESBURG
DRY MILL	503	LEESBURG
RIVER CREEK	512	LEESBURG
EAST LEESBURG	502	LEESBURG
PURCELLVILLE	424	CATOCTIN
WEST LEESBURG	501	LEESBURG
BALL'S BLUFF	508	LEESBURG
SMART'S MILL	504	LEESBURG
ROUND HILL	425	CATOCTIN
MOUNTAIN VIEW	428	CATOCTIN
CLARKES GAP	409	CATOCTIN
ROUND HILL ELEMENTARY	429	CATOCTIN
HAMILTON	416	CATOCTIN
HILLSBORO	426	CATOCTIN
LUCKETTS	403	CATOCTIN
WATERFORD	402	CATOCTIN
EAST LOVETTSVILLE	411	CATOCTIN
BETWEEN THE HILLS	421	CATOCTIN
WEST LOVETTSVILLE	401	CATOCTIN
SYCOLIN CREEK	323	LITTLE RIVER
PINEBROOK	313	LITTLE RIVER
BUFFALO TRAIL	322	LITTLE RIVER
LUNSFORD	120	DULLES
GOSHEN POST	126	DULLES
ARCOLA	119	DULLES
HILLSIDE	615	BROAD RUN
HOVATTER	328	LITTLE RIVER
LIGHTRIDGE	329	LITTLE RIVER
GOOSE CREEK	824	ASHBURN
GUILFORD	711	STERLING
MARBLEHEAD	631	BROAD RUN
WILLARD	327	LITTLE RIVER
HARMONY	430	CATOCTIN
EAST BROAD RUN	818	ASHBURN
ASHBROOK	627	BROAD RUN
CREIGHTON	325	LITTLE RIVER
SIMPSON	423	CATOCTIN
BRIAR WOODS	312	LITTLE RIVER
SANDERS CORNER	817	ASHBURN
RUSSELL BRANCH	620	BROAD RUN
NEWTON-LEE	814	ASHBURN
TUSCARORA	413	CATOCTIN
EVERGREEN	511	LEESBURG
WELLER	623	BROAD RUN
COOL SPRING	505	LEESBURG"""

# Election Day time window
DAY_START = time(5, 30)   # 5:30 AM
DAY_END   = time(19, 0)   # 7:00 PM

# Expected columns in raw files
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
    "sign_up_timestamp": "Sign Up Timestamp",
}

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def parse_time_range_from_item(item_str):
    """Parse strings like '11am-1pm' or '12pm to 3:00 pm'"""
    if not isinstance(item_str, str):
        return None

    s = item_str.lower().strip()
    s = s.replace("to", "-")
    
    time_pattern = r"(\d{1,2}(:\d{2})?\s*(am|pm)?)"
    matches = re.findall(time_pattern, s)

    if len(matches) < 2:
        return None

    def clean_time_token(tok):
        tok = tok[0]
        tok = tok.replace(" ", "")
        if not ("am" in tok or "pm" in tok):
            return None
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
    """Generate 30-minute slots within [start, end)"""
    s = max(datetime.combine(day, start_time), datetime.combine(day, DAY_START))
    e = min(datetime.combine(day, end_time), datetime.combine(day, DAY_END))

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
    return digits


def format_time_12hr(t):
    """Convert time object to '6:00 AM' format"""
    formatted = datetime.combine(datetime.today(), t).strftime("%I:%M %p")
    if formatted.startswith("0"):
        formatted = formatted[1:]
    return formatted


# ---------------------------------------------------------
# ARCHIVE EXISTING CSV FILES
# ---------------------------------------------------------

def archive_existing_csvs():
    """Archive existing CSV files to the archive folder with timestamp"""
    csv_files = [VOLUNTEER_MASTER_CSV, ASSIGNMENTS_CSV, UPCOMING_ASSIGNMENTS_CSV]

    archived_any = False
    for csv_file in csv_files:
        if csv_file.exists():
            if not archived_any:
                ARCHIVE_DIR.mkdir(exist_ok=True)
                archived_any = True

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
            archive_path = ARCHIVE_DIR / archive_name

            shutil.move(str(csv_file), str(archive_path))
            print(f"✓ Archived {csv_file} to {archive_path}")

    if archived_any:
        print()


# ---------------------------------------------------------
# LOAD PRECINCT MASTER
# ---------------------------------------------------------

def load_precinct_master():
    precinct_csv = Path(__file__).parent / "reference_data" / "precinct_address_information.csv"

    if precinct_csv.exists():
        df = pd.read_csv(precinct_csv)

        df['Number & Name'] = df['Number & Name'].str.strip()
        number_and_name_parts = df['Number & Name'].str.extract(r'^(\d+)\s*-\s*(.+)$')

        df_mapped = pd.DataFrame({
            'PR_NAME': number_and_name_parts[1].str.strip().str.upper(),
            'PR_NUMBER': number_and_name_parts[0].str.strip(),
            'PR_DISTRICT': df['District'].str.strip().str.upper()
        })

        return df_mapped
    else:
        from io import StringIO
        df = pd.read_csv(StringIO(PRECINCT_MASTER_DATA), sep="\t")
        df.columns = df.columns.str.strip()
        df["PR_NAME"] = df["PR_NAME"].str.strip().str.upper()
        df["PR_DISTRICT"] = df["PR_DISTRICT"].str.strip().str.upper()
        return df


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
    archive_existing_csvs()

    precinct_master = load_precinct_master()
    
    raw = load_raw_signups(RAW_DATA_DIR)

    # Rename columns
    col_rename = {}
    for key, orig in COL_MAP.items():
        for col in raw.columns:
            if col.strip().lower() == orig.strip().lower():
                col_rename[col] = key
    raw = raw.rename(columns=col_rename)

    required = ["sign_up", "start_datetime", "end_datetime",
                "location", "item", "first_name", "last_name"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")

    # Parse datetime
    raw["start_datetime"] = pd.to_datetime(raw["start_datetime"], errors="coerce")
    raw["end_datetime"] = pd.to_datetime(raw["end_datetime"], errors="coerce")
    
    # Parse sign_up_timestamp if available
    if "sign_up_timestamp" in raw.columns:
        raw["sign_up_timestamp"] = pd.to_datetime(raw["sign_up_timestamp"], errors="coerce")
    else:
        raw["sign_up_timestamp"] = pd.NaT

    # Create volunteer key
    raw["phone"] = raw.get("phone", "").astype(str).map(normalize_phone)
    raw["first_name"] = raw["first_name"].fillna("").astype(str).str.strip()
    raw["last_name"] = raw["last_name"].fillna("").astype(str).str.strip()

    raw["Volunteer_Key"] = (
        raw["first_name"].str.upper() + "_" +
        raw["last_name"].str.upper() + "_" +
        raw["phone"]
    )

    # Build VolunteerMaster
    vm_cols = ["Volunteer_Key", "first_name", "last_name", "email", "phone", "sign_up_timestamp"]
    vm = raw[vm_cols].copy()
    vm["Past_Volunteer_Count"] = 1

    vm = (
        vm.groupby(["Volunteer_Key", "first_name", "last_name", "email", "phone"],
                   as_index=False)
          .agg({
              "Past_Volunteer_Count": "sum",
              "sign_up_timestamp": ["min", "max"]
          })
    )

    vm.columns = ["Volunteer_Key", "first_name", "last_name", "email", "phone",
                  "Past_Volunteer_Count", "First_Signup_Date", "Last_Signup_Date"]

    vm = vm.rename(columns={
        "first_name": "First_Name",
        "last_name": "Last_Name",
        "email": "Email",
        "phone": "Phone",
    })

    if VOLUNTEER_MASTER_CSV.exists():
        existing_vm = pd.read_csv(VOLUNTEER_MASTER_CSV)

        if "First_Signup_Date" in existing_vm.columns:
            existing_vm["First_Signup_Date"] = pd.to_datetime(existing_vm["First_Signup_Date"], errors="coerce")
        if "Last_Signup_Date" in existing_vm.columns:
            existing_vm["Last_Signup_Date"] = pd.to_datetime(existing_vm["Last_Signup_Date"], errors="coerce")

        merged = pd.concat([existing_vm, vm], ignore_index=True)
        merged = (
            merged.groupby(["Volunteer_Key", "First_Name", "Last_Name", "Email", "Phone"],
                           as_index=False)
                  .agg({
                      "Past_Volunteer_Count": "max",
                      "First_Signup_Date": "min",
                      "Last_Signup_Date": "max"
                  })
        )
        merged.to_csv(VOLUNTEER_MASTER_CSV, index=False)
    else:
        vm.to_csv(VOLUNTEER_MASTER_CSV, index=False)

    print(f"✓ VolunteerMaster written to {VOLUNTEER_MASTER_CSV}")

    # -------------------------------------------------
    # Build upcoming_Assignments.csv
    # -------------------------------------------------
    
    # Generate all time slots (6:00 AM to 6:30 PM in 30-min increments)
    time_slots = []
    current = time(6, 0)
    end = time(18, 30)
    while current <= end:
        time_slots.append(current)
        dt = datetime.combine(datetime.today(), current)
        dt += timedelta(minutes=30)
        current = dt.time()

    upcoming_rows = []

    for _, precinct in precinct_master.iterrows():
        district = precinct["PR_DISTRICT"]
        precinct_name = precinct["PR_NAME"]
        precinct_number = precinct["PR_NUMBER"]
        precinct_display = f"{precinct_number} - {precinct_name}"

        # Special roles (no Proposed/Backup split)
        for role in ["Precinct Captain", "Equipment Drop Off", "Equipment Pick Up"]:
            upcoming_rows.append({
                "Election_Date": "TBD",
                "Assignment_Type": "Proposed",
                "District": district,
                "Precinct": precinct_display,
                "Slot_Time": "",
                "Role": role,
                "Volunteer_Key": "__",
                "Volunteer_Name": "__",
                "Past_Count": 0,
                "Last_Signup_Date": "",
            })

        # Opener (5:30 AM)
        for assign_type in ["Proposed", "Backup"]:
            upcoming_rows.append({
                "Election_Date": "TBD",
                "Assignment_Type": assign_type,
                "District": district,
                "Precinct": precinct_display,
                "Slot_Time": "5:30 AM",
                "Role": "Opener",
                "Volunteer_Key": "__",
                "Volunteer_Name": "__",
                "Past_Count": 0,
                "Last_Signup_Date": "",
            })

        # Ballot Greeter slots (6:00 AM - 6:30 PM)
        for slot_time in time_slots:
            slot_str = format_time_12hr(slot_time)

            for role_num in [1, 2]:
                role = f"Ballot Greeter {role_num}"

                for assign_type in ["Proposed", "Backup"]:
                    upcoming_rows.append({
                        "Election_Date": "TBD",
                        "Assignment_Type": assign_type,
                        "District": district,
                        "Precinct": precinct_display,
                        "Slot_Time": slot_str,
                        "Role": role,
                        "Volunteer_Key": "__",
                        "Volunteer_Name": "__",
                        "Past_Count": 0,
                        "Last_Signup_Date": "",
                    })

        # Closer (7:00 PM)
        for assign_type in ["Proposed", "Backup"]:
            upcoming_rows.append({
                "Election_Date": "TBD",
                "Assignment_Type": assign_type,
                "District": district,
                "Precinct": precinct_display,
                "Slot_Time": "7:00 PM",
                "Role": "Closer",
                "Volunteer_Key": "__",
                "Volunteer_Name": "__",
                "Past_Count": 0,
                "Last_Signup_Date": "",
            })

    upcoming_df = pd.DataFrame(upcoming_rows)

    # Now populate from historical data using raw signups
    if not raw.empty:
        # Create a lookup from precinct name to full display format
        precinct_lookup = {}
        for _, p in precinct_master.iterrows():
            pr_name = p["PR_NAME"]
            pr_display = f"{p['PR_NUMBER']} - {pr_name}"
            precinct_lookup[pr_name] = pr_display

        # Load precinct address data for enhanced matching
        from precinct_matching import find_precinct_match as find_precinct_match_enhanced, load_precinct_address
        precinct_address_df = load_precinct_address(Path(__file__).parent)

        # Create a lookup from precinct name to full display format
        precinct_lookup = {}
        for _, p in precinct_master.iterrows():
            pr_name = p["PR_NAME"]
            pr_display = f"{p['PR_NUMBER']} - {pr_name}"
            precinct_lookup[pr_name] = pr_display

        # Helper function to find matching precinct
        def find_precinct_match(location_name):
            return find_precinct_match_enhanced(location_name, precinct_lookup, precinct_address_df)

        # Process raw data to create assignment-like structure
        raw_assignments = []
        for idx, row in raw.iterrows():
            day = row["start_datetime"].date() if pd.notnull(row["start_datetime"]) else None
            if day is None:
                continue

            tr = parse_time_range_from_item(row.get("item", ""))
            if tr:
                t_start, t_end = tr
            else:
                if pd.isnull(row["end_datetime"]):
                    continue
                t_start = row["start_datetime"].time()
                t_end = row["end_datetime"].time()

            slots = generate_half_hour_slots(day, t_start, t_end)
            if not slots:
                continue

            signup_str = str(row.get("sign_up", ""))
            signup_parts = signup_str.split()

            district = ""
            for i, part in enumerate(signup_parts):
                if part.isdigit() and len(part) == 4:
                    district = " ".join(signup_parts[:i]).upper()
                    break

            if not district:
                district = signup_parts[0].upper() if signup_parts else ""

            loc = str(row.get("location", ""))
            precinct_display = find_precinct_match(loc)

            if precinct_display is None:
                continue

            for slot_start in slots:
                raw_assignments.append({
                    "District": district,
                    "Precinct_Name": precinct_display,
                    "Slot_Time_Obj": slot_start.time(),
                    "Volunteer_Key": row["Volunteer_Key"],
                    "Sign_Up_Timestamp": row.get("sign_up_timestamp"),
                })

        if raw_assignments:
            assignments_df = pd.DataFrame(raw_assignments)
            assignments_df["Slot_Time_Str"] = assignments_df["Slot_Time_Obj"].apply(format_time_12hr)

            # Get volunteer names from VolunteerMaster
            vm_lookup = vm.set_index("Volunteer_Key")

            # Group by District, Precinct, Slot to find Proposed/Backup
            for (district, precinct_name, slot_time), group in assignments_df.groupby(
                ["District", "Precinct_Name", "Slot_Time_Str"]
            ):
                # Sort by timestamp (most recent first)
                group = group.sort_values("Sign_Up_Timestamp", ascending=False, na_position="last")

                volunteers = group["Volunteer_Key"].unique()

                # Filter out invalid volunteer keys (empty signups)
                volunteers = [v for v in volunteers if v != "__" and v.strip() != ""]

                if len(volunteers) == 0:
                    continue

                # Get the full precinct display format
                precinct_display = find_precinct_match(precinct_name)

                if precinct_display is None:
                    continue

                # Assign to Poll Greeter 1 and 2
                for idx, vol_key in enumerate(volunteers[:4]):  # Max 2 proposed + 2 backup
                    if idx < 2:
                        assign_type = "Proposed"
                        role_num = idx + 1
                    else:
                        assign_type = "Backup"
                        role_num = idx - 1

                    role = f"Ballot Greeter {role_num}"

                    # Get volunteer info and most recent signup date
                    if vol_key in vm_lookup.index:
                        vol_info = vm_lookup.loc[vol_key]

                        # Handle case where there might be duplicate volunteer keys
                        if isinstance(vol_info, pd.DataFrame):
                            vol_info = vol_info.iloc[0]

                        first_name = str(vol_info['First_Name'])
                        last_name = str(vol_info['Last_Name'])
                        vol_name = f"{first_name} {last_name}"
                        past_count = int(vol_info["Past_Volunteer_Count"])
                        last_signup_raw = vol_info.get("Last_Signup_Date", "")
                        if pd.notna(last_signup_raw) and last_signup_raw != "":
                            last_signup = str(pd.to_datetime(last_signup_raw).date())
                        else:
                            last_signup = ""
                    else:
                        vol_name = vol_key
                        past_count = 1
                        last_signup = ""

                    # Update upcoming_df
                    mask = (
                        (upcoming_df["District"] == district) &
                        (upcoming_df["Precinct"] == precinct_display) &
                        (upcoming_df["Slot_Time"] == slot_time) &
                        (upcoming_df["Role"] == role) &
                        (upcoming_df["Assignment_Type"] == assign_type)
                    )

                    if mask.sum() > 0:
                        idx = upcoming_df[mask].index[0]
                        upcoming_df.at[idx, "Volunteer_Key"] = vol_key
                        upcoming_df.at[idx, "Volunteer_Name"] = vol_name
                        upcoming_df.at[idx, "Past_Count"] = past_count
                        upcoming_df.at[idx, "Last_Signup_Date"] = last_signup

    # Sort as specified
    time_order = ["5:30 AM"] + [format_time_12hr(t) for t in time_slots] + ["7:00 PM"]
    upcoming_df["Time_Sort"] = upcoming_df["Slot_Time"].apply(
        lambda x: time_order.index(x) if x in time_order else 999
    )

    upcoming_df["Assignment_Sort"] = upcoming_df["Assignment_Type"].map({"Proposed": 1, "Backup": 2})

    upcoming_df = upcoming_df.sort_values([
        "Assignment_Sort",
        "District",
        "Precinct",
        "Time_Sort",
        "Role"
    ])

    upcoming_df = upcoming_df.drop(columns=["Time_Sort", "Assignment_Sort"])

    upcoming_df.to_csv(UPCOMING_ASSIGNMENTS_CSV, index=False)
    print(f"✓ upcoming_Assignments written to {UPCOMING_ASSIGNMENTS_CSV}")
    print(f"\nTotal rows in upcoming_Assignments: {len(upcoming_df)}")


if __name__ == "__main__":
    main()