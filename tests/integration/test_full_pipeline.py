"""
Integration test for the full processing pipeline.
"""
import sys
from pathlib import Path
import unittest
import tempfile
import shutil
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from main_processor import process


class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        """Create temporary test environment."""
        self.test_dir = Path(tempfile.mkdtemp())

        # Create directory structure
        (self.test_dir / "input").mkdir()
        (self.test_dir / "reference_data").mkdir()

        # Create test precinct data
        precinct_data = pd.DataFrame({
            'Number & Name': ['808 - Stone Bridge', '116 - Little River'],
            'District': ['ASHBURN', 'LITTLE RIVER'],
            'Polling Place': ['Stone Bridge High School', 'Little River Elementary'],
            'Address': ['43100 Hay Rd', '42100 Little River Rd']
        })
        precinct_data.to_csv(self.test_dir / "reference_data" / "precinct_address_information.csv", index=False)

        # Create test signup data
        signup_data = pd.DataFrame({
            'Sign Up': ['ASHBURN 808'] * 3,
            'Start Date/Time (mm/dd/yyyy)': ['03/05/2024 06:00'] * 3,
            'End Date/Time (mm/dd/yyyy)': ['03/05/2024 12:00'] * 3,
            'Location': ['Stone Bridge High School'] * 3,
            'Item': ['6am-12pm'] * 3,
            'First Name': ['John', 'Jane', 'John'],  # John appears twice (duplicate)
            'Last Name': ['Doe', 'Smith', 'Doe'],
            'Email': ['john@example.com', 'jane@example.com', 'john2@example.com'],
            'Phone': ['555-1234', '555-5678', '555-1234'],  # Same phone for John
            'PhoneType': ['Mobile'] * 3,
            'Sign Up Timestamp': ['2024-01-15 10:00:00', '2024-01-15 11:00:00', '2024-01-16 09:00:00']
        })
        signup_data.to_csv(self.test_dir / "input" / "test_signups.csv", index=False)
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)
    
    def test_full_pipeline(self):
        """Test the complete processing pipeline."""
        config = {
            'include_backups': True,
            'fuzzy_threshold': 85
        }
        
        results = process(self.test_dir, config)
        
        # Check results structure
        self.assertIn('volunteer_count', results)
        self.assertIn('assignment_rows', results)
        self.assertIn('duplicates_resolved', results)
        
        # Should have 2 unique volunteers (John deduplicated)
        self.assertEqual(results['volunteer_count'], 2)
        
        # Should have resolved 1 duplicate
        self.assertEqual(results['duplicates_resolved'], 1)
        
        # Check output files exist
        self.assertTrue((self.test_dir / "VolunteerMaster.csv").exists())
        self.assertTrue((self.test_dir / "upcoming_Assignments.csv").exists())
        
        # Check VolunteerMaster content
        vm = pd.read_csv(self.test_dir / "VolunteerMaster.csv")
        self.assertEqual(len(vm), 2)
        
        # Check assignments have enhanced columns
        assignments = pd.read_csv(self.test_dir / "upcoming_Assignments.csv")
        self.assertIn('Precinct_Number_Name', assignments.columns)
        self.assertIn('Polling_Place', assignments.columns)
        self.assertIn('Address', assignments.columns)
        self.assertIn('Maps_URL', assignments.columns)


if __name__ == "__main__":
    unittest.main()
