"""
Unit tests for volunteer_utils module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import unittest
import pandas as pd
from volunteer_utils import compute_volunteer_affinity


class TestComputeVolunteerAffinity(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.vm_data = pd.DataFrame({
            'Volunteer_Key': ['JOHN_DOE_5551234', 'JANE_SMITH_5555678', 'BOB_JONES_5559012'],
            'First_Name': ['John', 'Jane', 'Bob'],
            'Last_Name': ['Doe', 'Smith', 'Jones'],
            'Email': ['john@example.com', 'jane@example.com', 'bob@example.com'],
            'Phone': ['5551234', '5555678', '5559012'],
            'Past_Volunteer_Count': [10, 5, 3]
        })
        
        self.assignments_data = pd.DataFrame({
            'Volunteer_Key': ['JOHN_DOE_5551234'] * 7 + ['JANE_SMITH_5555678'] * 3 + ['BOB_JONES_5559012'] * 2,
            'Precinct': ['808 - Stone Bridge'] * 5 + ['116 - Little River'] * 2 +
                       ['808 - Stone Bridge'] * 2 + ['116 - Little River'] * 1 +
                       ['810 - Cedar Lane'] * 2,
            'Role': ['Ballot Greeter 1'] * 12,
            'Assignment_Type': ['Proposed'] * 12
        })
    
    def test_high_affinity_detection(self):
        """Test that volunteers with >=5 signups at same precinct are detected."""
        # Create temp files
        vm_file = Path(__file__).parent / "test_vm.csv"
        assign_file = Path(__file__).parent / "test_assignments.csv"
        
        self.vm_data.to_csv(vm_file, index=False)
        self.assignments_data.to_csv(assign_file, index=False)
        
        try:
            suggestions, review = compute_volunteer_affinity(vm_file, assign_file, threshold=5)
            
            # John Doe has 5+ signups at Stone Bridge
            self.assertEqual(len(suggestions), 1)
            self.assertEqual(suggestions.iloc[0]['Volunteer_Key'], 'JOHN_DOE_5551234')
            self.assertEqual(suggestions.iloc[0]['Signup_Count'], 5)
            
            # Others should be in review
            self.assertEqual(len(review), 2)
        finally:
            vm_file.unlink()
            assign_file.unlink()
    
    def test_affinity_score_calculation(self):
        """Test that affinity score is calculated correctly."""
        vm_file = Path(__file__).parent / "test_vm.csv"
        assign_file = Path(__file__).parent / "test_assignments.csv"
        
        self.vm_data.to_csv(vm_file, index=False)
        self.assignments_data.to_csv(assign_file, index=False)
        
        try:
            suggestions, review = compute_volunteer_affinity(vm_file, assign_file, threshold=3)
            
            # John Doe: 5/7 signups at Stone Bridge = 71.4%
            john_row = suggestions[suggestions['Volunteer_Key'] == 'JOHN_DOE_5551234']
            self.assertEqual(len(john_row), 1)
            self.assertAlmostEqual(john_row.iloc[0]['Affinity_Score'], 71.4, places=0)
        finally:
            vm_file.unlink()
            assign_file.unlink()


if __name__ == "__main__":
    unittest.main()
