"""
Location matching validation script.
Run this before processing to identify matching issues.
"""
import pandas as pd
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from precinct_matching import find_precinct_match_enhanced, load_precinct_address, load_aliases


def load_precinct_master_from_csv(project_root):
    """Load precinct master from CSV file."""
    precinct_csv = project_root / "reference_data" / "precinct_address_information.csv"
    
    if not precinct_csv.exists():
        raise FileNotFoundError(f"Precinct file not found: {precinct_csv}")
    
    df = pd.read_csv(precinct_csv)
    df['Number & Name'] = df['Number & Name'].str.strip()
    number_and_name_parts = df['Number & Name'].str.extract(r'^(\d+)\s*-\s*(.+)$')
    
    df_mapped = pd.DataFrame({
        'PR_NAME': number_and_name_parts[1].str.strip().str.upper(),
        'PR_NUMBER': number_and_name_parts[0].str.strip(),
        'PR_DISTRICT': df['District'].str.strip().str.upper()
    })
    
    return df_mapped, df


def create_precinct_lookup(precinct_master):
    precinct_lookup = {}
    for _, p in precinct_master.iterrows():
        pr_name = p["PR_NAME"]
        pr_display = f"{p['PR_NUMBER']} - {pr_name}"
        precinct_lookup[pr_name] = pr_display
    return precinct_lookup


def validate_location_matching():
    print("=" * 80)
    print("LOCATION MATCHING VALIDATION REPORT (Enhanced with Fuzzy Matching)")
    print("=" * 80)
    print()

    raw_dir = project_root / "input"
    csv_files = list(raw_dir.glob("*.csv")) + list(raw_dir.glob("*.xlsx")) + list(raw_dir.glob("*.xls"))
    
    if not csv_files:
        print(f"ERROR: No raw signup files found in {raw_dir}")
        return False

    print(f"Found {len(csv_files)} signup files")
    
    # Load all raw files
    all_raw = []
    for file_path in csv_files:
        print(f"Loading: {file_path.name}")
        if file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        df['__source_file'] = file_path.name
        all_raw.append(df)
    
    raw = pd.concat(all_raw, ignore_index=True)
    
    # Normalize column names
    col_map = {
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
    
    col_rename = {}
    for key, orig in col_map.items():
        for col in raw.columns:
            if col.strip().lower() == orig.strip().lower():
                col_rename[col] = key
    raw = raw.rename(columns=col_rename)
    
    precinct_master, precinct_address_df = load_precinct_master_from_csv(project_root)
    precinct_lookup = create_precinct_lookup(precinct_master)
    aliases = load_aliases(project_root)
    
    print(f"✓ Loaded precinct address data: {len(precinct_address_df)} precincts")
    print(f"✓ Loaded {len(aliases)} aliases")
    print(f"Total signups: {len(raw)}")
    print(f"Total precincts in master: {len(precinct_lookup)}")
    print()

    unique_locations = raw["location"].dropna().unique()
    print(f"Unique locations in raw signups: {len(unique_locations)}")
    print()

    unmatched_locations = []
    matched_exact = []
    matched_alias = []
    matched_substring = []
    matched_word = []
    matched_fuzzy_polling = []
    matched_fuzzy_address = []
    
    for location in unique_locations:
        match_result, match_type = find_precinct_match_enhanced(
            location, precinct_lookup, precinct_address_df, aliases
        )
        
        if match_type == "no_match":
            unmatched_locations.append(location)
        elif match_type == "alias":
            matched_alias.append((location, match_result))
        elif match_type == "exact":
            matched_exact.append((location, match_result))
        elif match_type == "substring":
            matched_substring.append((location, match_result))
        elif match_type == "word_match":
            matched_word.append((location, match_result))
        elif match_type == "polling_place_fuzzy":
            matched_fuzzy_polling.append((location, match_result))
        elif match_type == "address_fuzzy":
            matched_fuzzy_address.append((location, match_result))

    print(f"✓ Alias matches: {len(matched_alias)}")
    print(f"✓ Exact matches: {len(matched_exact)}")
    print(f"✓ Substring matches: {len(matched_substring)}")
    print(f"✓ Word-based matches: {len(matched_word)}")
    print(f"✓ Fuzzy polling place matches: {len(matched_fuzzy_polling)}")
    print(f"✓ Fuzzy address matches: {len(matched_fuzzy_address)}")
    print(f"✗ Unmatched locations: {len(unmatched_locations)}")
    print()

    if matched_alias:
        print("-" * 80)
        print("ALIAS MATCHES:")
        print("-" * 80)
        for location, match in sorted(matched_alias):
            print(f"  '{location}' → {match}")
        print()

    if matched_fuzzy_polling:
        print("-" * 80)
        print("FUZZY POLLING PLACE MATCHES (with address info):")
        print("-" * 80)
        for location, match in sorted(matched_fuzzy_polling, key=lambda x: x[1].get('match_score', 0), reverse=True)[:20]:
            score = match.get('match_score', 0)
            print(f"  '{location}'")
            print(f"    → {match['precinct_display']}")
            print(f"    → Polling: {match['polling_place']}")
            print(f"    → Address: {match['address']}")
            print(f"    → Match Score: {score}")
            print(f"    → Maps: {match['maps_url']}")
            print()

    if matched_fuzzy_address:
        print("-" * 80)
        print("FUZZY ADDRESS MATCHES:")
        print("-" * 80)
        for location, match in sorted(matched_fuzzy_address, key=lambda x: x[1].get('match_score', 0), reverse=True)[:10]:
            score = match.get('match_score', 0)
            print(f"  '{location}' → {match['precinct_display']} (Score: {score})")
        print()

    if matched_substring:
        print("-" * 80)
        print("SUBSTRING MATCHES (first 10):")
        print("-" * 80)
        for location, match in sorted(matched_substring)[:10]:
            print(f"  '{location}' → {match}")
        if len(matched_substring) > 10:
            print(f"  ... and {len(matched_substring) - 10} more")
        print()

    if matched_word:
        print("-" * 80)
        print("WORD-BASED MATCHES:")
        print("-" * 80)
        for location, match in sorted(matched_word):
            print(f"  '{location}' → {match}")
        print()

    if unmatched_locations:
        print("-" * 80)
        print("⚠️  UNMATCHED LOCATIONS (NEED ATTENTION):")
        print("-" * 80)
        unmatched_with_counts = []
        for location in unmatched_locations:
            signup_count = len(raw[raw["location"] == location])
            unmatched_with_counts.append((location, signup_count))
        
        unmatched_with_counts.sort(key=lambda x: x[1], reverse=True)
        
        for location, signup_count in unmatched_with_counts[:30]:
            print(f"  '{location}' ({signup_count} signups)")
        
        if len(unmatched_with_counts) > 30:
            print(f"  ... and {len(unmatched_with_counts) - 30} more unmatched locations")
        
        print()
        print("These locations will result in volunteers not appearing in upcoming_Assignments.csv")
        print()

    if unmatched_locations:
        print("-" * 80)
        print("SUGGESTED ACTIONS:")
        print("-" * 80)
        print("1. Check if these are valid precinct locations")
        print("2. Update reference_data/precinct_address_information.csv with missing locations")
        print("3. Add aliases to reference_data/aliases.json for common variations")
        print("4. Verify location names in SignUpGenius match official precinct names")
        print()

    total_matched = len(unique_locations) - len(unmatched_locations)
    match_rate = (total_matched / len(unique_locations) * 100) if unique_locations.size > 0 else 0
    
    print("=" * 80)
    print(f"SUMMARY: {total_matched}/{len(unique_locations)} locations matched successfully ({match_rate:.1f}%)")
    print(f"  - Alias: {len(matched_alias)}")
    print(f"  - Exact: {len(matched_exact)}")
    print(f"  - Substring: {len(matched_substring)}")
    print(f"  - Word-based: {len(matched_word)}")
    print(f"  - Fuzzy (polling): {len(matched_fuzzy_polling)}")
    print(f"  - Fuzzy (address): {len(matched_fuzzy_address)}")
    print("=" * 80)

    return len(unmatched_locations) == 0


def main():
    success = validate_location_matching()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
