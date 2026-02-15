import pandas as pd
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from precinct_matching import find_precinct_match_enhanced, load_precinct_address

PRECINCT_MASTER_DATA = """
PR_NAME	PR_NUMBER	DISTRICT
ALGONKIAN	101	ALGONKIAN
ASHBURN	102	ASHBURN
ASHBURN FARM	103	ASHBURN
BELMONT	104	LEESBURG
BELMONT RIDGE	105	LEESBURG
BLUE RIDGE	106	BLUE RIDGE
BRAMBLETON	107	ASHBURN
BROAD RUN	108	BROAD RUN
CATOCTIN	109	CATOCTIN
DULLES	110	DULLES
EAST BROAD RUN	111	ASHBURN
EVERGREEN	112	STERLING
GOOSE CREEK	113	ASHBURN
HARMONY	114	LEESBURG
LEESBURG	115	LEESBURG
LITTLE RIVER	116	LITTLE RIVER
LOWES ISLAND	117	ALGONKIAN
MERCER	118	ALGONKIAN
MOOREFIELD	119	ASHBURN
POTOMAC	120	STERLING
ROLLING RIDGE	121	LEESBURG
RUST	122	LEESBURG
SENECA	123	BROAD RUN
SHENANDOAH	124	STERLING
SLEETER LAKE	125	LEESBURG
STERLING	126	STERLING
SUGARLAND	127	STERLING
SULLY	128	DULLES
TUSCARORA	129	LEESBURG
WOODGROVE	130	CATOCTIN
ARCOLA	201	DULLES
ASHBURN LIBRARY	202	ASHBURN
BELMONT STATION	203	LEESBURG
CASCADES	204	STERLING
COUNTRYSIDE	205	STERLING
CREIGHTON'S CORNER	206	LEESBURG
DOMINION	207	DULLES
EAGLE RIDGE	616	BROAD RUN
FARMWELL STATION	208	ASHBURN
FOREST GROVE	209	BROAD RUN
FRANKLIN PARK	210	DULLES
GALILEE CHURCH	219	ALGONKIAN
HERITAGE	211	BROAD RUN
HUTCHISON FARM	212	BROAD RUN
LANSDOWNE	213	LEESBURG
LEGACY	214	ASHBURN
LINCOLN	215	LEESBURG
LOUDOUN VALLEY	216	BLUE RIDGE
MILL CREEK	217	DULLES
MOOREFIELD STATION	218	ASHBURN
NEWTON-LEE	220	STERLING
NORTH POINT	221	ASHBURN
PINEBROOK	222	DULLES
POTOMAC FALLS	223	STERLING
RIVERSIDE	224	LEESBURG
ROCK RIDGE	225	ASHBURN
ROSA LEE CARTER	226	BROAD RUN
RYAN	227	ASHBURN
SELDENS LANDING	228	BROAD RUN
SMART'S MILL	229	BROAD RUN
STONE BRIDGE	230	DULLES
STONE HILL	231	ASHBURN
TRAILSIDE	232	ASHBURN
VILLAGE	233	LEESBURG
WILLOWSFORD	234	ASHBURN
"""

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

def load_precinct_master():
    from io import StringIO
    df = pd.read_csv(StringIO(PRECINCT_MASTER_DATA), sep="\t")
    return df

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

    raw_signups_path = project_root / "raw_signups" / "all_signup_genius.csv"
    
    if not raw_signups_path.exists():
        print(f"ERROR: Raw signups file not found at {raw_signups_path}")
        return False

    print(f"Loading raw signups from: {raw_signups_path}")
    raw = pd.read_csv(raw_signups_path)
    
    col_rename = {}
    for key, orig in COL_MAP.items():
        for col in raw.columns:
            if col.strip().lower() == orig.strip().lower():
                col_rename[col] = key
    raw = raw.rename(columns=col_rename)
    
    precinct_master = load_precinct_master()
    precinct_lookup = create_precinct_lookup(precinct_master)
    
    precinct_address_df = load_precinct_address(project_root)
    if precinct_address_df is not None:
        print(f"✓ Loaded precinct address data: {len(precinct_address_df)} precincts")
    else:
        print("⚠️  Precinct address data not found - using basic matching only")
    
    print(f"Total signups: {len(raw)}")
    print(f"Total precincts in master: {len(precinct_lookup)}")
    print()

    unique_locations = raw["location"].dropna().unique()
    print(f"Unique locations in raw signups: {len(unique_locations)}")
    print()

    unmatched_locations = []
    matched_exact = []
    matched_substring = []
    matched_word = []
    matched_fuzzy_polling = []
    matched_fuzzy_address = []
    
    for location in unique_locations:
        match_result, match_type = find_precinct_match_enhanced(location, precinct_lookup, precinct_address_df)
        
        if match_type == "no_match":
            unmatched_locations.append(location)
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

    print(f"✓ Exact matches: {len(matched_exact)}")
    print(f"✓ Substring matches: {len(matched_substring)}")
    print(f"✓ Word-based matches: {len(matched_word)}")
    print(f"✓ Fuzzy polling place matches: {len(matched_fuzzy_polling)}")
    print(f"✓ Fuzzy address matches: {len(matched_fuzzy_address)}")
    print(f"✗ Unmatched locations: {len(unmatched_locations)}")
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
        print("3. Verify location names in SignUpGenius match official precinct names")
        print("4. Consider adding location aliases to the matching logic")
        print()

    total_matched = len(unique_locations) - len(unmatched_locations)
    print("=" * 80)
    print(f"SUMMARY: {total_matched}/{len(unique_locations)} locations matched successfully")
    print(f"  - Exact: {len(matched_exact)}")
    print(f"  - Substring: {len(matched_substring)}")
    print(f"  - Word-based: {len(matched_word)}")
    print(f"  - Fuzzy (polling): {len(matched_fuzzy_polling)}")
    print(f"  - Fuzzy (address): {len(matched_fuzzy_address)}")
    print("=" * 80)

    return len(unmatched_locations) == 0

if __name__ == "__main__":
    success = validate_location_matching()
    sys.exit(0 if success else 1)
