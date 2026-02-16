"""
Main volunteer signup processor with deduplication, enhanced matching, and reporting.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, time, timedelta
import re
import shutil
import logging
from urllib.parse import quote

from precinct_matching import (
    find_precinct_match_enhanced, 
    load_precinct_address, 
    load_aliases,
    get_match_stats
)

# Setup logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

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
    """Extract digits only from phone number."""
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


def normalize_volunteer_key(first_name, last_name, phone):
    """Create normalized volunteer key for deduplication."""
    first = str(first_name).lower().strip()
    last = str(last_name).lower().strip()
    phone_digits = normalize_phone(str(phone))
    return f"{first}_{last}_{phone_digits}"


# ---------------------------------------------------------
# ARCHIVE EXISTING CSV FILES
# ---------------------------------------------------------

def archive_existing_csvs(project_root, volunteer_master_csv, assignments_csv, upcoming_assignments_csv):
    """Archive existing CSV files to the archive folder with timestamp"""
    archive_dir = project_root / "archive"
    csv_files = [volunteer_master_csv, assignments_csv, upcoming_assignments_csv]

    archived_any = False
    for csv_file in csv_files:
        if csv_file.exists():
            if not archived_any:
                archive_dir.mkdir(exist_ok=True)
                archived_any = True

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{csv_file.stem}_{timestamp}{csv_file.suffix}"
            archive_path = archive_dir / archive_name

            shutil.move(str(csv_file), str(archive_path))
            logger.info(f"Archived {csv_file} to {archive_path}")

    return archived_any


# ---------------------------------------------------------
# LOAD PRECINCT MASTER
# ---------------------------------------------------------

def load_precinct_master(project_root):
    """Load precinct master data from CSV."""
    precinct_csv = project_root / "reference_data" / "precinct_address_information.csv"

    if precinct_csv.exists():
        df = pd.read_csv(precinct_csv)
        df['Number & Name'] = df['Number & Name'].str.strip()
        number_and_name_parts = df['Number & Name'].str.extract(r'^(\d+)\s*-\s*(.+)$')

        df_mapped = pd.DataFrame({
            'PR_NAME': number_and_name_parts[1].str.strip().str.upper(),
            'PR_NUMBER': number_and_name_parts[0].str.strip(),
            'PR_DISTRICT': df['District'].str.strip().str.upper()
        })

        return df_mapped, df  # Return both mapped and full address data
    else:
        raise FileNotFoundError(f"Precinct address file not found: {precinct_csv}")


# ---------------------------------------------------------
# LOAD ALL RAW FILES
# ---------------------------------------------------------

def load_raw_signups(raw_dir: Path) -> pd.DataFrame:
    """Load all CSV/XLSX files from input directory."""
    all_rows = []
    for path in raw_dir.glob("*"):
        if path.suffix.lower() not in [".csv", ".xlsx", ".xls"]:
            continue

        logger.info(f"Loading {path.name} ...")
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        df["__source_file"] = path.name
        all_rows.append(df)

    if not all_rows:
        raise FileNotFoundError(f"No CSV/XLSX files found in {raw_dir}")

    big_df = pd.concat(all_rows, ignore_index=True)
    logger.info(f"Loaded {len(big_df)} total rows from {len(all_rows)} files")
    return big_df


# ---------------------------------------------------------
# DEDUPLICATION
# ---------------------------------------------------------

def deduplicate_volunteers(raw_df):
    """
    Deduplicate volunteers based on normalized key.
    Returns deduplicated DataFrame and count of duplicates found.
    Preserves all columns needed for assignment processing.
    """
    # Create normalized volunteer key
    raw_df["Volunteer_Key_Raw"] = (
        raw_df["first_name"].str.lower().str.strip() + "_" +
        raw_df["last_name"].str.lower().str.strip() + "_" +
        raw_df["phone"].map(normalize_phone)
    )

    original_count = len(raw_df)

    # Identify duplicate keys
    key_counts = raw_df["Volunteer_Key_Raw"].value_counts()
    duplicate_keys = key_counts[key_counts > 1].index.tolist()

    duplicates_found = len(duplicate_keys)

    if duplicates_found > 0:
        logger.warning(f"Found and resolved {duplicates_found} duplicate volunteer entries")

        # Log duplicate details
        for key in duplicate_keys[:10]:
            count = key_counts[key]
            logger.info(f"  Duplicate: {key} ({count} entries)")

        # For duplicates, keep only the most recent signup per volunteer
        # Sort by timestamp (descending) and keep first for each key
        deduped = raw_df.sort_values("sign_up_timestamp", ascending=False)
        deduped = deduped.drop_duplicates(subset="Volunteer_Key_Raw", keep="first")
        deduped = deduped.sort_index()  # Restore original order
    else:
        deduped = raw_df

    return deduped, duplicates_found


# ---------------------------------------------------------
# BUILD VOLUNTEER MASTER
# ---------------------------------------------------------

def build_volunteer_master(raw_df, volunteer_master_csv):
    """Build or update VolunteerMaster.csv with deduplication."""
    # Create volunteer key (uppercase for storage)
    raw_df["Volunteer_Key"] = (
        raw_df["first_name"].str.upper().str.strip() + "_" +
        raw_df["last_name"].str.upper().str.strip() + "_" +
        raw_df["phone"].map(normalize_phone)
    )

    vm_cols = ["Volunteer_Key", "first_name", "last_name", "email", "phone", "sign_up_timestamp"]
    vm = raw_df[vm_cols].copy()
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

    if volunteer_master_csv.exists():
        existing_vm = pd.read_csv(volunteer_master_csv)

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
        merged.to_csv(volunteer_master_csv, index=False)

        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        output_dir = volunteer_master_csv.parent / "output"
        output_dir.mkdir(exist_ok=True)
        timestamped_path = output_dir / f"VolunteerMaster_{timestamp}.csv"
        merged.to_csv(timestamped_path, index=False)

        logger.info(f"Updated VolunteerMaster: {len(merged)} volunteers")
        logger.info(f"Saved timestamped copy to: {timestamped_path}")
        return merged
    else:
        vm.to_csv(volunteer_master_csv, index=False)

        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        output_dir = volunteer_master_csv.parent / "output"
        output_dir.mkdir(exist_ok=True)
        timestamped_path = output_dir / f"VolunteerMaster_{timestamp}.csv"
        vm.to_csv(timestamped_path, index=False)

        logger.info(f"Created VolunteerMaster: {len(vm)} volunteers")
        logger.info(f"Saved timestamped copy to: {timestamped_path}")
        return vm


# ---------------------------------------------------------
# BUILD UPCOMING ASSIGNMENTS
# ---------------------------------------------------------

def build_upcoming_assignments(precinct_master, precinct_address_df, raw_df, vm,
                                upcoming_assignments_csv, aliases, include_backups=True):
    """Build upcoming assignments with enhanced matching and address info."""

    # Load existing assignments from precinct_info.csv
    project_root = upcoming_assignments_csv.parent
    precinct_info_path = project_root / "output" / "precinct_info.csv"

    role_mapping = {
        'Captain': 'Precinct Captain',
        'Equipment_Drop': 'Equipment Drop Off',
        'Equipment_Pickup': 'Equipment Pick Up',
        'Opener': 'Opener',
        'Closer': 'Closer'
    }

    existing_assignments = {}
    if precinct_info_path.exists():
        logger.info(f"Loading existing assignments from {precinct_info_path}")
        precinct_info_df = pd.read_csv(precinct_info_path, encoding='utf-8')

        for _, row in precinct_info_df.iterrows():
            district = str(row.get('District', '')).upper()
            precinct = str(row.get('Precinct', '')).upper()
            role = row.get('Role', '')
            volunteer_key = row.get('Volunteer_Key', '__')

            mapped_role = role_mapping.get(role, role)

            key = (district, precinct, mapped_role)
            existing_assignments[key] = volunteer_key

        logger.info(f"Loaded {len(existing_assignments)} existing assignments")

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
        
        # Get full address info
        addr_info = precinct_address_df[precinct_address_df['Number & Name'] == precinct_display]
        if not addr_info.empty:
            polling_place = addr_info.iloc[0]['Polling Place']
            address = addr_info.iloc[0]['Address']
            maps_url = f"https://www.google.com/maps/place/{quote(address)}"
        else:
            polling_place = ""
            address = ""
            maps_url = ""

        # Special roles (no Proposed/Backup split)
        for role in ["Precinct Captain", "Equipment Drop Off", "Equipment Pick Up"]:
            key = (district, precinct_display, role)
            volunteer_key = existing_assignments.get(key, "__")

            volunteer_name = "__"
            past_count = 0
            last_signup_date = ""

            if volunteer_key != "__" and volunteer_key in vm.set_index("Volunteer_Key").index:
                vm_lookup = vm.set_index("Volunteer_Key")
                vol_info = vm_lookup.loc[volunteer_key]
                if isinstance(vol_info, pd.DataFrame):
                    vol_info = vol_info.iloc[0]
                volunteer_name = f"{vol_info['First_Name']} {vol_info['Last_Name']}"
                past_count = int(vol_info.get("Past_Volunteer_Count", 0))
                last_signup_raw = vol_info.get("Last_Signup_Date", "")
                if pd.notna(last_signup_raw) and last_signup_raw != "":
                    last_signup_date = str(pd.to_datetime(last_signup_raw).date())

            upcoming_rows.append({
                "Election_Date": "TBD",
                "Assignment_Type": "Proposed",
                "District": district,
                "Precinct": precinct_display,
                "Precinct_Number_Name": precinct_display,
                "Polling_Place": polling_place,
                "Address": address,
                "Maps_URL": maps_url,
                "Slot_Time": "",
                "Role": role,
                "Volunteer_Key": volunteer_key,
                "Volunteer_Name": volunteer_name,
                "Past_Count": past_count,
                "Last_Signup_Date": last_signup_date,
            })

        # Opener (5:30 AM)
        assign_types = ["Proposed", "Backup"] if include_backups else ["Proposed"]
        for assign_type in assign_types:
            key = (district, precinct_display, "Opener")
            volunteer_key = existing_assignments.get(key, "__")

            volunteer_name = "__"
            past_count = 0
            last_signup_date = ""

            if volunteer_key != "__" and volunteer_key in vm.set_index("Volunteer_Key").index:
                vm_lookup = vm.set_index("Volunteer_Key")
                vol_info = vm_lookup.loc[volunteer_key]
                if isinstance(vol_info, pd.DataFrame):
                    vol_info = vol_info.iloc[0]
                volunteer_name = f"{vol_info['First_Name']} {vol_info['Last_Name']}"
                past_count = int(vol_info.get("Past_Volunteer_Count", 0))
                last_signup_raw = vol_info.get("Last_Signup_Date", "")
                if pd.notna(last_signup_raw) and last_signup_raw != "":
                    last_signup_date = str(pd.to_datetime(last_signup_raw).date())

            upcoming_rows.append({
                "Election_Date": "TBD",
                "Assignment_Type": assign_type,
                "District": district,
                "Precinct": precinct_display,
                "Precinct_Number_Name": precinct_display,
                "Polling_Place": polling_place,
                "Address": address,
                "Maps_URL": maps_url,
                "Slot_Time": "5:30 AM",
                "Role": "Opener",
                "Volunteer_Key": volunteer_key,
                "Volunteer_Name": volunteer_name,
                "Past_Count": past_count,
                "Last_Signup_Date": last_signup_date,
            })

        # Ballot Greeter slots (6:00 AM - 6:30 PM)
        for slot_time in time_slots:
            slot_str = format_time_12hr(slot_time)

            for role_num in [1, 2]:
                role = f"Ballot Greeter {role_num}"

                for assign_type in assign_types:
                    upcoming_rows.append({
                        "Election_Date": "TBD",
                        "Assignment_Type": assign_type,
                        "District": district,
                        "Precinct": precinct_display,
                        "Precinct_Number_Name": precinct_display,
                        "Polling_Place": polling_place,
                        "Address": address,
                        "Maps_URL": maps_url,
                        "Slot_Time": slot_str,
                        "Role": role,
                        "Volunteer_Key": "__",
                        "Volunteer_Name": "__",
                        "Past_Count": 0,
                        "Last_Signup_Date": "",
                    })

        # Closer (7:00 PM)
        for assign_type in assign_types:
            key = (district, precinct_display, "Closer")
            volunteer_key = existing_assignments.get(key, "__")

            volunteer_name = "__"
            past_count = 0
            last_signup_date = ""

            if volunteer_key != "__" and volunteer_key in vm.set_index("Volunteer_Key").index:
                vm_lookup = vm.set_index("Volunteer_Key")
                vol_info = vm_lookup.loc[volunteer_key]
                if isinstance(vol_info, pd.DataFrame):
                    vol_info = vol_info.iloc[0]
                volunteer_name = f"{vol_info['First_Name']} {vol_info['Last_Name']}"
                past_count = int(vol_info.get("Past_Volunteer_Count", 0))
                last_signup_raw = vol_info.get("Last_Signup_Date", "")
                if pd.notna(last_signup_raw) and last_signup_raw != "":
                    last_signup_date = str(pd.to_datetime(last_signup_raw).date())

            upcoming_rows.append({
                "Election_Date": "TBD",
                "Assignment_Type": assign_type,
                "District": district,
                "Precinct": precinct_display,
                "Precinct_Number_Name": precinct_display,
                "Polling_Place": polling_place,
                "Address": address,
                "Maps_URL": maps_url,
                "Slot_Time": "7:00 PM",
                "Role": "Closer",
                "Volunteer_Key": volunteer_key,
                "Volunteer_Name": volunteer_name,
                "Past_Count": past_count,
                "Last_Signup_Date": last_signup_date,
            })

    upcoming_df = pd.DataFrame(upcoming_rows)

    # Populate from raw signups
    if not raw_df.empty:
        # Create precinct lookup
        precinct_lookup = {}
        for _, p in precinct_master.iterrows():
            pr_name = p["PR_NAME"]
            pr_display = f"{p['PR_NUMBER']} - {pr_name}"
            precinct_lookup[pr_name] = pr_display

        # Process raw assignments
        raw_assignments = []
        unmatched_locations = []
        
        for idx, row in raw_df.iterrows():
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
            match_result, match_type = find_precinct_match_enhanced(
                loc, precinct_lookup, precinct_address_df, aliases
            )
            
            if match_result is None:
                unmatched_locations.append((loc, match_type))
                logger.warning(f"Unmatched location: '{loc}' (type: {match_type})")
                continue

            if isinstance(match_result, dict):
                precinct_display = match_result['precinct_display']
            else:
                precinct_display = match_result

            for slot_start in slots:
                raw_assignments.append({
                    "District": district,
                    "Precinct_Name": precinct_display,
                    "Slot_Time_Obj": slot_start.time(),
                    "Volunteer_Key": row["Volunteer_Key"],
                    "Sign_Up_Timestamp": row.get("sign_up_timestamp"),
                })

        # Log unmatched location summary
        if unmatched_locations:
            from collections import Counter
            loc_counts = Counter(unmatched_locations)
            logger.warning(f"Total unmatched locations: {len(loc_counts)}")
            for (loc, mtype), count in loc_counts.most_common(10):
                logger.warning(f"  {loc}: {count} occurrences ({mtype})")

        if raw_assignments:
            assignments_df = pd.DataFrame(raw_assignments)
            assignments_df["Slot_Time_Str"] = assignments_df["Slot_Time_Obj"].apply(format_time_12hr)

            vm_lookup = vm.set_index("Volunteer_Key")

            for (district, precinct_name, slot_time), group in assignments_df.groupby(
                ["District", "Precinct_Name", "Slot_Time_Str"]
            ):
                group = group.sort_values("Sign_Up_Timestamp", ascending=False, na_position="last")
                volunteers = group["Volunteer_Key"].unique()
                volunteers = [v for v in volunteers if v != "__" and str(v).strip() != ""]

                if len(volunteers) == 0:
                    continue

                for idx, vol_key in enumerate(volunteers[:4] if include_backups else volunteers[:2]):
                    if idx < 2:
                        assign_type = "Proposed"
                        role_num = idx + 1
                    else:
                        assign_type = "Backup"
                        role_num = idx - 1

                    role = f"Ballot Greeter {role_num}"

                    if vol_key in vm_lookup.index:
                        vol_info = vm_lookup.loc[vol_key]
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

                    mask = (
                        (upcoming_df["District"] == district) &
                        (upcoming_df["Precinct"] == precinct_name) &
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

    # Sort
    time_order = ["5:30 AM"] + [format_time_12hr(t) for t in time_slots] + ["7:00 PM"]
    upcoming_df["Time_Sort"] = upcoming_df["Slot_Time"].apply(
        lambda x: time_order.index(x) if x in time_order else 999
    )
    upcoming_df["Assignment_Sort"] = upcoming_df["Assignment_Type"].map({"Proposed": 1, "Backup": 2})

    upcoming_df = upcoming_df.sort_values([
        "Assignment_Sort", "District", "Precinct", "Time_Sort", "Role"
    ])
    upcoming_df = upcoming_df.drop(columns=["Time_Sort", "Assignment_Sort"])

    upcoming_df.to_csv(upcoming_assignments_csv, index=False)
    logger.info(f"Wrote upcoming_Assignments: {len(upcoming_df)} rows")

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output_dir = upcoming_assignments_csv.parent / "output"
    output_dir.mkdir(exist_ok=True)
    timestamped_path = output_dir / f"upcoming_Assignments_{timestamp}.csv"
    upcoming_df.to_csv(timestamped_path, index=False)
    logger.info(f"Saved timestamped copy to: {timestamped_path}")

    input_dir = upcoming_assignments_csv.parent / "input"
    input_dir.mkdir(exist_ok=True)
    input_copy_path = input_dir / "upcoming_Assignments.csv"
    upcoming_df.to_csv(input_copy_path, index=False)
    logger.info(f"Copied to input folder: {input_copy_path}")

    return upcoming_df


# ---------------------------------------------------------
# MAIN PROCESSING
# ---------------------------------------------------------

def process(project_root, config=None):
    """
    Main processing function.
    
    Args:
        project_root: Path to project root
        config: Optional dict with settings like:
            - include_backups: bool (default True)
            - fuzzy_threshold: int (default 85)
    """
    if config is None:
        config = {}
    
    include_backups = config.get('include_backups', True)
    fuzzy_threshold = config.get('fuzzy_threshold', 85)
    
    # Paths
    raw_data_dir = project_root / "input"
    volunteer_master_csv = project_root / "VolunteerMaster.csv"
    assignments_csv = project_root / "Assignments.csv"
    upcoming_assignments_csv = project_root / "upcoming_Assignments.csv"
    
    # Archive existing files
    archive_existing_csvs(project_root, volunteer_master_csv, assignments_csv, upcoming_assignments_csv)
    
    # Load data
    precinct_master, precinct_address_df = load_precinct_master(project_root)
    aliases = load_aliases(project_root)
    
    logger.info(f"Loaded {len(precinct_master)} precincts")
    logger.info(f"Loaded {len(aliases)} aliases")
    
    raw = load_raw_signups(raw_data_dir)
    
    # Rename columns
    col_rename = {}
    for key, orig in COL_MAP.items():
        for col in raw.columns:
            if col.strip().lower() == orig.strip().lower():
                col_rename[col] = key
    raw = raw.rename(columns=col_rename)
    
    # Validate required columns
    required = ["sign_up", "start_datetime", "end_datetime", "location", "item", "first_name", "last_name"]
    missing = [c for c in required if c not in raw.columns]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}")
    
    # Parse datetime
    raw["start_datetime"] = pd.to_datetime(raw["start_datetime"], errors="coerce")
    raw["end_datetime"] = pd.to_datetime(raw["end_datetime"], errors="coerce")
    
    if "sign_up_timestamp" in raw.columns:
        raw["sign_up_timestamp"] = pd.to_datetime(raw["sign_up_timestamp"], errors="coerce")
    else:
        raw["sign_up_timestamp"] = pd.NaT
    
    # Normalize phone and names
    raw["phone"] = raw.get("phone", "").astype(str).map(normalize_phone)
    raw["first_name"] = raw["first_name"].fillna("").astype(str).str.strip()
    raw["last_name"] = raw["last_name"].fillna("").astype(str).str.strip()
    
    # Deduplicate volunteers
    raw_deduped, dup_count = deduplicate_volunteers(raw)
    
    # Create volunteer key for assignments
    raw_deduped["Volunteer_Key"] = (
        raw_deduped["first_name"].str.upper() + "_" +
        raw_deduped["last_name"].str.upper() + "_" +
        raw_deduped["phone"]
    )
    
    # Build VolunteerMaster
    vm = build_volunteer_master(raw_deduped, volunteer_master_csv)
    
    # Build upcoming assignments
    upcoming_df = build_upcoming_assignments(
        precinct_master, precinct_address_df, raw_deduped, vm,
        upcoming_assignments_csv, aliases, include_backups
    )
    
    # Log match stats
    stats = get_match_stats()
    logger.info(f"Fuzzy match cache stats: {stats}")
    
    return {
        'volunteer_count': len(vm),
        'assignment_rows': len(upcoming_df),
        'duplicates_resolved': dup_count,
        'match_stats': stats
    }
