import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
from main_processor import process

project_root = Path(__file__).parent
input_dir = project_root / "input"

signup_file = input_dir / "all_signup_genius.csv"

if signup_file.exists():
    print(f"Processing {signup_file.name}...")
    
    config = {
        'signup_files': [signup_file],
        'include_backups': True
    }
    
    result = process(project_root, config)
    
    upcoming_file = project_root / "upcoming_Assignments.csv"
    if upcoming_file.exists():
        df = pd.read_csv(upcoming_file)
        
        captain_assignments = df[df['Role'] == 'Precinct Captain']
        filled_captains = captain_assignments[captain_assignments['Volunteer_Key'] != '__']
        
        equipment_drop = df[df['Role'] == 'Equipment Drop Off']
        filled_equipment_drop = equipment_drop[equipment_drop['Volunteer_Key'] != '__']
        
        print(f"\nTotal Captain slots: {len(captain_assignments)}")
        print(f"Filled Captain slots: {len(filled_captains)}")
        print(f"\nTotal Equipment Drop Off slots: {len(equipment_drop)}")
        print(f"Filled Equipment Drop Off slots: {len(filled_equipment_drop)}")
        
        print(f"\nSample filled Captain assignments:")
        print(filled_captains[['District', 'Precinct', 'Role', 'Volunteer_Key', 'Volunteer_Name']].head(10))
        
        print(f"\nSample filled Equipment Drop Off assignments:")
        print(filled_equipment_drop[['District', 'Precinct', 'Role', 'Volunteer_Key', 'Volunteer_Name']].head(10))
else:
    print(f"Error: {signup_file} not found")
