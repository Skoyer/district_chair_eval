"""
Generate precinct_info.csv for testing purposes.
This script creates test data by assigning volunteers from VolunteerMaster.csv
in the output directory to different precincts and roles (Captain, Equipment_Drop, Equipment_Pickup, Opener, Closer).
"""

import pandas as pd
from pathlib import Path
import random

def generate_precinct_info():
    # When run from src/, project_root is the parent directory
    project_root = Path(__file__).parent.parent
    src_dir = Path(__file__).parent
    
    output_dir = project_root / "output"

    volunteer_master_files = list(output_dir.glob("VolunteerMaster_*.csv"))

    if volunteer_master_files:
        volunteer_master_path = max(volunteer_master_files, key=lambda p: p.stat().st_mtime)
        print(f"Using latest VolunteerMaster file: {volunteer_master_path.name}")
    else:
        volunteer_master_path = output_dir / "VolunteerMaster.csv"
        print(f"Using VolunteerMaster.csv")

    precinct_master_path = project_root / "reference_data" / "precinct_address_information.csv"
    output_path = output_dir / "precinct_info.csv"

    if not volunteer_master_path.exists():
        print(f"Error: {volunteer_master_path} not found")
        return

    if not precinct_master_path.exists():
        print(f"Error: {precinct_master_path} not found")
        return
    
    volunteers_df = pd.read_csv(volunteer_master_path)
    precincts_df = pd.read_csv(precinct_master_path)
    
    volunteer_keys = volunteers_df['Volunteer_Key'].tolist()
    
    roles = ['Captain', 'Equipment_Drop', 'Equipment_Pickup', 'Opener', 'Closer']
    
    precinct_info_rows = []
    volunteer_index = 0
    
    for _, precinct_row in precincts_df.iterrows():
        district = precinct_row['District']
        precinct_number_name = precinct_row['Number & Name']
        
        for role in roles:
            if volunteer_index < len(volunteer_keys):
                volunteer_key = volunteer_keys[volunteer_index]
                volunteer_index += 1
            else:
                volunteer_index = 0
                volunteer_key = volunteer_keys[volunteer_index]
                volunteer_index += 1
            
            precinct_info_rows.append({
                'District': district,
                'Precinct': precinct_number_name,
                'Role': role,
                'Volunteer_Key': volunteer_key
            })
    
    precinct_info_df = pd.DataFrame(precinct_info_rows)
    
    precinct_info_df.to_csv(output_path, index=False)
    
    print(f"✅ Generated precinct_info.csv with {len(precinct_info_df)} rows")
    print(f"   Saved to: {output_path}")
    print(f"\nSummary:")
    print(f"   Total precincts: {len(precincts_df)}")
    print(f"   Total volunteers used: {volunteer_index}")
    print(f"   Roles per precinct: {len(roles)}")
    print(f"\nSample data:")
    print(precinct_info_df.head(10))

if __name__ == "__main__":
    generate_precinct_info()
