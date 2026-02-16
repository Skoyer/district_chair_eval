# Election Volunteer Signup Processor

A Python application that processes volunteer signup data for election poll workers across 107 precincts in Loudoun County, Virginia. The system consolidates signup information, tracks volunteer history, generates assignment schedules, and provides comprehensive reporting.

## Quick Start

```bash
# Process signups (default)
python app.py

# Validate location matching before processing
python app.py validate

# Generate reports only
python app.py report --output-format=html

# Generate HTML dashboard
python app.py dashboard

# Skip backup assignments
python app.py --no-backups

# Full options
python app.py process --auto-guess-threshold=3 --output-format=html --verbose
```

## Project Structure

```
.
├── app.py                          # Main entry point with CLI
├── manifest.json                   # Project manifest (programs, inputs, outputs)
├── src/
│   ├── main_processor.py          # Core processing logic
│   ├── precinct_matching.py       # Fuzzy matching with aliases & caching
│   ├── volunteer_utils.py         # Affinity scoring & suggestions
│   └── reporting.py               # Needs reports & dashboard
├── tests/
│   ├── validate_location_matching.py   # Pre-processing validation
│   ├── unit/                     # Unit tests
│   └── integration/              # Integration tests
├── input/                         # Input CSV/Excel files
├── reference_data/
│   ├── precinct_address_information.csv  # Precinct master data
│   └── aliases.json              # Location aliases (auto-created)
├── output/                        # Generated reports
│   ├── needs_report.csv
│   ├── VolunteerMaster_suggestions.csv
│   ├── review_needed.csv
│   └── dashboard.html
├── archive/                       # Timestamped backups
├── VolunteerMaster.csv           # Master volunteer database
├── upcoming_Assignments.csv      # Assignment schedule
└── app.log                       # Application logs
```

## Inputs

### Required
- **input/*.csv** or **input/*.xlsx** - Volunteer signup files from SignUpGenius
  - Expected columns: `Sign Up`, `Start Date/Time`, `End Date/Time`, `Location`, `Item`, `First Name`, `Last Name`, `Email`, `Phone`, `Sign Up Timestamp`

- **reference_data/precinct_address_information.csv** - Precinct master data
  - Columns: `Number & Name`, `District`, `Polling Place`, `Address`

### Optional (Auto-Created)
- **VolunteerMaster.csv** - Historical volunteer data (merged with new signups)
- **reference_data/aliases.json** - Location aliases for improved matching

## Outputs

| File | Description |
|------|-------------|
| `VolunteerMaster.csv` | Master volunteer database with signup history |
| `upcoming_Assignments.csv` | Complete assignment schedule with enhanced columns (Precinct_Number_Name, Polling_Place, Address, Maps_URL) |
| `output/needs_report.csv` | Precinct staffing needs analysis with health scores |
| `output/VolunteerMaster_suggestions.csv` | High-affinity volunteer suggestions (auto-guesses) |
| `output/review_needed.csv` | Volunteers below affinity threshold |
| `output/dashboard.html` | Interactive HTML dashboard with charts |
| `archive/` | Timestamped backups of previous runs |
| `app.log` | Application log file |

## Features

### Core Processing
- **Multi-format Support**: Reads CSV and Excel (.xlsx, .xls) files
- **Automatic Archiving**: Backs up existing outputs with timestamps
- **Volunteer Deduplication**: Normalizes and merges duplicate entries
- **Smart Time Parsing**: Extracts time ranges from various formats
- **30-Minute Time Slots**: Breaks shifts into half-hour increments

### Enhanced Matching
- **5-Tier Matching Strategy**: Alias → Exact → Substring → Word-based → Fuzzy
- **python-Levenshtein**: Fast fuzzy string matching (10x speedup)
- **LRU Caching**: Cached fuzzy match results for repeated runs
- **Location Aliases**: JSON-based alias system for common variations
- **Address Matching**: Matches on polling place names and addresses

### Reporting & Analysis
- **Needs Report**: Health scores for each precinct (Captain, Equipment, Greeter coverage)
- **Volunteer Affinity**: Auto-suggests volunteers based on signup frequency
- **HTML Dashboard**: Interactive dashboard with charts
- **Multiple Output Formats**: CSV, HTML, Markdown

### CLI Interface
```
python app.py [mode] [options]

Modes:
  process     Process signups (default)
  validate    Run location matching validation
  report      Generate reports only
  dashboard   Generate HTML dashboard

Options:
  --no-backups              Skip backup assignments
  --auto-guess-threshold N  Minimum signups for auto-suggestion (default: 5)
  --output-format FORMAT    csv, html, or markdown (default: csv)
  --fuzzy-threshold N       Fuzzy matching threshold 0-100 (default: 85)
  --verbose, -v             Enable debug logging
```

## Roles and Time Slots

| Role | Time | Assignment Types |
|------|------|------------------|
| Opener | 5:30 AM | Proposed + Backup |
| Ballot Greeter 1 & 2 | 6:00 AM - 6:30 PM (30-min slots) | Proposed + Backup each |
| Closer | 7:00 PM | Proposed + Backup |
| Precinct Captain | No time slot | Proposed only |
| Equipment Drop Off | No time slot | Proposed only |
| Equipment Pick Up | No time slot | Proposed only |

## Districts Covered

- DULLES
- LITTLE RIVER
- STERLING
- BROAD RUN
- ALGONKIAN
- ASHBURN
- LEESBURG
- CATOCTIN

## Dependencies

```bash
pip install pandas fuzzywuzzy python-Levenshtein matplotlib openpyxl
```

Or use the virtual environment:
```bash
.\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```

## Workflow

1. **Place signup files** in `input/`
2. **Validate** (optional but recommended):
   ```bash
   python app.py validate
   ```
3. **Process signups**:
   ```bash
   python app.py
   ```
4. **Review reports** in `output/`
5. **Open dashboard**:
   ```bash
   python app.py dashboard
   start output/dashboard.html  # Windows
   open output/dashboard.html   # Mac
   ```

## Adding Location Aliases

If locations fail to match, add aliases to `reference_data/aliases.json`:

```json
{
  "marblehead senior center": "631 - Marblehead",
  "goshen post": "126 - Goshen Post"
}
```

## Logging

All operations are logged to `app.log` with timestamps. Use `--verbose` for debug output.

## Testing

```bash
# Run validation
python tests/validate_location_matching.py

# Run unit tests (when implemented)
pytest tests/unit/
```

## License

Internal use for LCRC District Chair operations.
