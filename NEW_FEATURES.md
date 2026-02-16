# New Features Summary

## Changes Implemented

### 1. Timestamped Output Files
**Modified Files:** `src/main_processor.py`

- `VolunteerMaster.csv` and `upcoming_Assignments.csv` now save timestamped copies to the `output/` folder
- Format: `VolunteerMaster_YYYYMMDD_HHMMSS.csv` and `upcoming_Assignments_YYYYMMDD_HHMMSS.csv`
- Original files still saved to project root for backward compatibility
- Timestamped files created automatically on each run

### 2. Copy upcoming_Assignments.csv to Input Folder
**Modified Files:** `src/main_processor.py`

- After processing, `upcoming_Assignments.csv` is automatically copied to the `input/` folder
- This allows the file to be used as input for subsequent operations
- Enables workflow where assignments can be reviewed and reprocessed

### 3. Streamlit Web Interface
**New File:** `streamlit_app.py`

A user-friendly web interface with 4 main operations:

#### Option 1: Create Blank Signup from SignUpGenius File
- Scans `input/` directory for files with "signup" in the name
- Creates a blank template CSV with the same column structure
- Saves to `output/` with timestamp
- Provides download button for the template

#### Option 2: Create Blank Signup from upcoming_Assignments.csv
- Reads `upcoming_Assignments.csv` from `input/` folder
- Creates a blank template with assignment structure
- Saves to `output/` with timestamp
- Provides download button for the template

#### Option 3: Process upcoming_Assignments.csv and Show Needs Report
- Reads `upcoming_Assignments.csv` from `input/` folder
- Generates needs report in selected format (CSV, HTML, or Markdown)
- Displays report directly in the web interface
- Provides download button for the report

#### Option 4: Process SignUpGenius File(s) and Create Needs Report
- Processes all CSV/Excel files in `input/` directory
- Configurable options:
  - Include/exclude backup assignments
  - Fuzzy matching threshold (0-100)
  - Report format (CSV, HTML, Markdown)
- Shows processing metrics (volunteer count, assignments, duplicates)
- Generates and displays needs report
- Creates dashboard.html

**To Run the Streamlit App:**
```bash
streamlit run streamlit_app.py
```

### 4. Precinct Info Generator Script
**New File:** `generate_precinct_info.py`

- One-time script to generate test data
- Creates `reference_data/precinct_info.csv`
- Assigns volunteers sequentially to precincts and roles
- Roles: Captain, Equipment_Drop, Equipment_Pickup, Opener, Closer
- Uses actual volunteer data from `VolunteerMaster.csv`
- Uses actual precinct data from `reference_data/precinct_address_information.csv`

**Generated File Structure:**
```csv
District,Precinct,Role,Volunteer_Key
Ashburn,808 - Stone Bridge,Captain,AAKASH_REDDY_7035936900
Ashburn,808 - Stone Bridge,Equipment_Drop,ABBY_LACKEY_2022852214
...
```

**To Run:**
```bash
python generate_precinct_info.py
```

**Output:** 535 rows (107 precincts × 5 roles)

## File Structure Changes

```
project_root/
├── input/                          # Input files (renamed from raw_signups)
│   ├── *signup*.csv               # SignUpGenius files
│   └── upcoming_Assignments.csv   # Auto-copied after processing
├── output/                         # Output files (renamed from reports)
│   ├── VolunteerMaster_YYYYMMDD_HHMMSS.csv
│   ├── upcoming_Assignments_YYYYMMDD_HHMMSS.csv
│   ├── needs_report.csv
│   ├── VolunteerMaster_suggestions.csv
│   ├── review_needed.csv
│   └── dashboard.html
├── reference_data/
│   ├── precinct_address_information.csv
│   ├── precinct_info.csv          # NEW: Test data
│   └── aliases.json
├── streamlit_app.py                # NEW: Web interface
├── generate_precinct_info.py       # NEW: Test data generator
├── VolunteerMaster.csv             # Root copy (for compatibility)
└── upcoming_Assignments.csv        # Root copy (for compatibility)
```

## Testing

All changes have been tested:
- ✅ Integration tests pass
- ✅ Timestamped files created successfully
- ✅ Files copied to input folder correctly
- ✅ Streamlit app created and dependencies installed
- ✅ Precinct info generator script runs successfully

## Usage Examples

### Using the Streamlit Interface
```bash
# Start the web interface
streamlit run streamlit_app.py

# Navigate to http://localhost:8501 in your browser
# Select an option from the dropdown
# Follow the on-screen instructions
```

### Using the Command Line (Original Method)
```bash
# Process signups
python app.py

# Generate reports only
python app.py report

# Validate location matching
python app.py validate

# Open dashboard
python app.py dashboard
```

### Generate Test Data
```bash
# Create precinct_info.csv with test assignments
python generate_precinct_info.py
```

## Benefits

1. **Better Organization**: Timestamped outputs prevent overwriting and provide audit trail
2. **Workflow Flexibility**: Copying to input folder enables iterative processing
3. **User-Friendly Interface**: Streamlit app makes operations accessible to non-technical users
4. **Better Testing**: Precinct info generator creates realistic test data for needs reports
5. **Backward Compatible**: Original files still saved to root directory
