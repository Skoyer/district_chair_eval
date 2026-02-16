"""
Unit tests for precinct_matching module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import unittest
from precinct_matching import (
    normalize_text,
    find_precinct_match_enhanced,
    load_aliases,
    save_aliases,
    add_alias,
    get_match_stats
)


class TestNormalizeText(unittest.TestCase):
    def test_basic_normalization(self):
        self.assertEqual(normalize_text("Hello World"), "hello world")
    
    def test_punctuation_removal(self):
        self.assertEqual(normalize_text("Hello, World!"), "hello world!")
        self.assertEqual(normalize_text("Test*Location"), "testlocation")
    
    def test_extra_spaces(self):
        self.assertEqual(normalize_text("  Multiple   Spaces  "), "multiple spaces")
    
    def test_non_string(self):
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text(123), "")


class TestFindPrecinctMatchEnhanced(unittest.TestCase):
    def setUp(self):
        self.precinct_lookup = {
            "STONE BRIDGE": "808 - Stone Bridge",
            "LITTLE RIVER": "116 - Little River",
            "CEDAR LANE": "810 - Cedar Lane"
        }
        self.precinct_address_df = None  # Would need mock for full testing
        self.aliases = {
            "briar woods high school": "116 - Little River"
        }
    
    def test_exact_match(self):
        result, match_type = find_precinct_match_enhanced(
            "STONE BRIDGE", self.precinct_lookup
        )
        self.assertEqual(result, "808 - Stone Bridge")
        self.assertEqual(match_type, "exact")
    
    def test_alias_match(self):
        result, match_type = find_precinct_match_enhanced(
            "Briar Woods High School", self.precinct_lookup, 
            aliases=self.aliases
        )
        self.assertEqual(result, "116 - Little River")
        self.assertEqual(match_type, "alias")
    
    def test_substring_match(self):
        result, match_type = find_precinct_match_enhanced(
            "Stone Bridge High School", self.precinct_lookup
        )
        self.assertEqual(result, "808 - Stone Bridge")
        self.assertEqual(match_type, "substring")
    
    def test_word_match(self):
        """Test word-based matching when not substring match."""
        # Use a precinct name that won't match as substring
        result, match_type = find_precinct_match_enhanced(
            "River Little Elementary", self.precinct_lookup
        )
        self.assertEqual(result, "116 - Little River")
        self.assertEqual(match_type, "word_match")
    
    def test_no_match(self):
        result, match_type = find_precinct_match_enhanced(
            "Unknown Location XYZ", self.precinct_lookup
        )
        self.assertIsNone(result)
        self.assertEqual(match_type, "no_match")


class TestAliases(unittest.TestCase):
    def setUp(self):
        self.test_aliases_file = Path(__file__).parent / "test_aliases.json"
        # Clean up before test
        if self.test_aliases_file.exists():
            self.test_aliases_file.unlink()
    
    def tearDown(self):
        # Clean up after test
        if self.test_aliases_file.exists():
            self.test_aliases_file.unlink()
    
    def test_load_save_aliases(self):
        test_data = {"test location": "123 - Test Precinct"}
        save_aliases(test_data, Path(__file__).parent)
        loaded = load_aliases(Path(__file__).parent)
        self.assertEqual(loaded, test_data)


class TestMatchStats(unittest.TestCase):
    def test_stats_structure(self):
        stats = get_match_stats()
        self.assertIn("cache_hits", stats)
        self.assertIn("cache_misses", stats)
        self.assertIn("cache_size", stats)


if __name__ == "__main__":
    unittest.main()
