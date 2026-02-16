"""
Unit tests for reporting module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import unittest
import pandas as pd
from reporting import compute_precinct_health


class TestComputePrecinctHealth(unittest.TestCase):
    def setUp(self):
        # Create test data for a single precinct
        self.test_data = pd.DataFrame({
            'Election_Date': ['TBD'] * 10,
            'Assignment_Type': ['Proposed'] * 10,
            'District': ['DULLES'] * 10,
            'Precinct': ['808 - Stone Bridge'] * 10,
            'Precinct_Number_Name': ['808 - Stone Bridge'] * 10,
            'Polling_Place': ['Stone Bridge High School'] * 10,
            'Address': ['43100 Hay Rd, Ashburn, VA 20147'] * 10,
            'Maps_URL': ['https://maps.google.com/...'] * 10,
            'Slot_Time': ['', '5:30 AM', '6:00 AM', '6:30 AM', '7:00 PM', '', '', '', '', ''],
            'Role': [
                'Precinct Captain', 'Opener', 'Ballot Greeter 1', 'Ballot Greeter 2',
                'Closer', 'Equipment Drop Off', 'Equipment Pick Up',
                'Ballot Greeter 1', 'Ballot Greeter 2', 'Ballot Greeter 1'
            ],
            'Volunteer_Key': [
                'CAPTAIN_001', 'OPENER_001', 'GREETER1_001', 'GREETER2_001',
                'CLOSER_001', '__', '__', '__', '__', 'BACKUP_001'
            ],
            'Volunteer_Name': [
                'Captain Smith', 'Opener Jones', 'Greeter One', 'Greeter Two',
                'Closer Brown', '__', '__', '__', '__', 'Backup Volunteer'
            ],
            'Past_Count': [10, 5, 3, 2, 8, 0, 0, 0, 0, 1],
            'Last_Signup_Date': ['2024-01-01'] * 10
        })
    
    def test_health_score_calculation(self):
        """Test that health score is calculated correctly."""
        health_df = compute_precinct_health(self.test_data)
        
        self.assertEqual(len(health_df), 1)
        
        row = health_df.iloc[0]
        
        # Should have Captain (10), Opener (5), Closer (5), Equipment Drop (0), Equipment Pickup (0)
        # Plus some greeter slots
        self.assertTrue(row['Health_Score'] > 0)
        self.assertTrue(row['Max_Score'] > 0)
        self.assertTrue(0 <= row['Health_Percent'] <= 100)
    
    def test_captain_detection(self):
        """Test that captain presence is detected."""
        health_df = compute_precinct_health(self.test_data)
        self.assertEqual(health_df.iloc[0]['Captain'], '✅')
    
    def test_equipment_detection(self):
        """Test that equipment roles are detected as missing."""
        health_df = compute_precinct_health(self.test_data)
        self.assertEqual(health_df.iloc[0]['Equipment_Drop'], '❌')
        self.assertEqual(health_df.iloc[0]['Equipment_Pickup'], '❌')
    
    def test_opener_closer_detection(self):
        """Test opener and closer detection."""
        health_df = compute_precinct_health(self.test_data)
        self.assertEqual(health_df.iloc[0]['Opener'], '✅')
        self.assertEqual(health_df.iloc[0]['Closer'], '✅')
    
    def test_empty_precinct(self):
        """Test handling of precinct with no assignments."""
        empty_data = pd.DataFrame(columns=self.test_data.columns)
        health_df = compute_precinct_health(empty_data)
        self.assertEqual(len(health_df), 0)


if __name__ == "__main__":
    unittest.main()
