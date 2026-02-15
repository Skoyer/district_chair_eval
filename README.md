# Election Volunteer Signup Processor

A Python script that processes volunteer signup data for election poll workers across 107 precincts in Loudoun County, Virginia. The script consolidates signup information, tracks volunteer history, and generates assignment schedules.

## Purpose

This tool helps election coordinators manage poll worker assignments by:
- Consolidating volunteer signups from multiple CSV/Excel files
- Tracking volunteer participation history
- Generating structured assignment schedules for election day
- Organizing volunteers by district, precinct, time slot, and role

## Features

- **Automatic File Archiving**: Archives existing output files with timestamps before generating new ones
- **Multi-Format Support**: Reads both CSV and Excel (.xlsx, .xls) signup files
- **Volunteer Tracking**: Maintains a master list of volunteers with signup history
- **Smart Time Parsing**: Extracts time ranges from various formats (e.g., "11am-1pm", "12pm to 3:00 pm")
- **30-Minute Time Slots**: Breaks volunteer shifts into half-hour increments
- **Precinct Matching**: Fuzzy matching to link signup locations to official precinct names
- **Assignment Prioritization**: Assigns volunteers to "Proposed" and "Backup" slots based on signup timestamps

## Input Requirements

### Directory Structure
- `raw_signups/`: Place all volunteer signup CSV/Excel files here
- `archive/`: Auto-created folder for archived output files

### Expected Signup File Columns
- Sign Up
- Start Date/Time (mm/dd/yyyy)
- End Date/Time (mm/dd/yyyy)
- Location
- Item (time range description)
- First Name
- Last Name
- Email
- Phone
- PhoneType
- Sign Up Timestamp

## Output Files

### 1. VolunteerMaster.csv
Master list of all volunteers with:
- Volunteer_Key (unique identifier: FIRSTNAME_LASTNAME_PHONE)
- First_Name, Last_Name, Email, Phone
- Past_Volunteer_Count (number of signups)
- First_Signup_Date, Last_Signup_Date

### 2. upcoming_Assignments.csv
Complete assignment schedule with:
- Election_Date (set to "TBD")
- Assignment_Type (Proposed or Backup)
- District (e.g., DULLES, STERLING, ASHBURN)
- Precinct (number and name)
- Slot_Time (5:30 AM to 7:00 PM in 30-min increments)
- Role (Opener, Ballot Greeter 1/2, Closer, Precinct Captain, Equipment Drop Off/Pick Up)
- Volunteer_Key, Volunteer_Name
- Past_Count, Last_Signup_Date

## Roles and Time Slots

- **Opener**: 5:30 AM (Proposed + Backup)
- **Ballot Greeter 1 & 2**: 6:00 AM - 6:30 PM in 30-minute slots (Proposed + Backup for each)
- **Closer**: 7:00 PM (Proposed + Backup)
- **Precinct Captain**: No time slot (Proposed only)
- **Equipment Drop Off**: No time slot (Proposed only)
- **Equipment Pick Up**: No time slot (Proposed only)

## Districts Covered

- DULLES
- LITTLE RIVER
- STERLING
- BROAD RUN
- ALGONKIAN
- ASHBURN
- LEESBURG
- CATOCTIN

## Usage

```bash
python process_signups.py