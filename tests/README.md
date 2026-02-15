# Test Scripts

This folder contains validation and testing scripts for the LCRC District Chair signup processing system.

## Available Tests

### `validate_location_matching.py`

**Purpose:** Identifies location matching issues between raw SignUpGenius data and the precinct master list.

**What it does:**
- Loads raw signup data and applies the same column mapping as `process_signups.py`
- Tests each unique location against the precinct master data using three matching strategies:
  1. **Exact match**: Location name exactly matches a precinct name
  2. **Substring match**: Precinct name is contained within the location name
  3. **Word-based match**: All significant words (>2 characters) from precinct name appear in location name
- Reports unmatched locations that will cause volunteers to be missing from `upcoming_Assignments.csv`

**Usage:**
```bash
python tests/validate_location_matching.py
```

**Output:**
- Summary of matched vs unmatched locations
- List of substring matches (may need verification)
- List of word-based fuzzy matches
- **⚠️ List of unmatched locations** with signup counts
- Suggested actions for resolving issues

**Exit codes:**
- `0`: All locations matched successfully
- `1`: Some locations are unmatched (needs attention)

**When to run:**
- After adding new raw signup data
- Before running `process_signups.py` to identify potential issues
- When volunteers are unexpectedly missing from output files
- When new precincts are added to the system

**Example output:**
```
================================================================================
LOCATION MATCHING VALIDATION REPORT
================================================================================

Loading raw signups from: .../raw_signups/all_signup_genius.csv
Total signups: 2972
Total precincts in master: 65

Unique locations in raw signups: 145

✓ Exact matches: 1
✓ Substring matches: 67
✓ Word-based matches: 1
✗ Unmatched locations: 76

--------------------------------------------------------------------------------
⚠️  UNMATCHED LOCATIONS (NEED ATTENTION):
--------------------------------------------------------------------------------
  'Briar Woods High School' (25 signups)
  'John Champe High School' (24 signups)
  ...

These locations will result in volunteers not appearing in upcoming_Assignments.csv
```

## Adding New Tests

When creating new test scripts:

1. Place them in the `tests/` folder
2. Use the same data structures and column mappings as `process_signups.py`
3. Document the test purpose and usage in this README
4. Return appropriate exit codes (0 for success, non-zero for failures)
5. Provide clear, actionable output for any issues found

## Common Issues Identified

### Location Name Mismatches
- SignUpGenius uses full school/building names (e.g., "Briar Woods High School")
- Precinct master uses abbreviated names (e.g., "LITTLE RIVER")
- Solution: Update precinct master data or add location aliases to matching logic

### Missing Precincts
- New precincts added to SignUpGenius but not in `PRECINCT_MASTER_DATA`
- Solution: Update the precinct master data in both `process_signups.py` and test scripts

### Typos and Variations
- Inconsistent location naming in SignUpGenius (e.g., "Galilee Church" vs "Galilee Methodist Church")
- Solution: Improve fuzzy matching logic or standardize SignUpGenius location names
