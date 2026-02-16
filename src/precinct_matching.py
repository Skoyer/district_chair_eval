"""
Precinct matching module with enhanced fuzzy matching, caching, and alias support.
"""
import re
import json
import pandas as pd
from pathlib import Path
from functools import lru_cache
from urllib.parse import quote

# Try to use rapidfuzz (faster) with fallback to fuzzywuzzy
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    from fuzzywuzzy import fuzz
    RAPIDFUZZ_AVAILABLE = False


def load_precinct_address(project_root=None):
    """Load precinct address information from CSV."""
    if project_root is None:
        project_root = Path(__file__).parent.parent
    precinct_address_csv = project_root / "reference_data" / "precinct_address_information.csv"
    if not precinct_address_csv.exists():
        return None
    return pd.read_csv(precinct_address_csv)


def load_aliases(project_root=None):
    """Load location aliases from JSON file."""
    if project_root is None:
        project_root = Path(__file__).parent.parent
    aliases_file = project_root / "reference_data" / "aliases.json"
    if not aliases_file.exists():
        return {}
    with open(aliases_file, 'r') as f:
        return json.load(f)


def save_aliases(aliases, project_root=None):
    """Save location aliases to JSON file."""
    if project_root is None:
        project_root = Path(__file__).parent.parent
    aliases_file = project_root / "reference_data" / "aliases.json"
    aliases_file.parent.mkdir(parents=True, exist_ok=True)
    with open(aliases_file, 'w') as f:
        json.dump(aliases, f, indent=2)


def normalize_text(text):
    """Normalize text for matching: lowercase, strip punctuation, remove extra spaces."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r'[*,]', '', text.lower().strip())
    text = re.sub(r'\s+', ' ', text)
    return text


@lru_cache(maxsize=1024)
def cached_fuzzy_match(str1, str2):
    """Cached fuzzy partial ratio for performance."""
    return fuzz.partial_ratio(str1, str2)


def find_precinct_match_enhanced(location_name, precinct_lookup, precinct_address_df=None, 
                                  aliases=None, fuzzy_threshold=85):
    """
    Enhanced precinct matching with aliases, caching, and multiple strategies.
    
    Matching strategy (in order of precedence):
    1. Alias match (from aliases.json)
    2. Exact name match
    3. Substring match
    4. Word-based match
    5. Fuzzy polling place match (cached)
    6. Fuzzy address match (cached)
    
    Returns: (result_dict or display_name, match_type)
    """
    location_norm = normalize_text(location_name)
    location_upper = location_name.upper().strip()
    
    # 1. Check aliases first
    if aliases:
        alias_key = location_norm
        if alias_key in aliases:
            return aliases[alias_key], "alias"
    
    # 2. Exact match
    if location_upper in precinct_lookup:
        return precinct_lookup[location_upper], "exact"
    
    # 3. Substring match
    for pr_name, pr_display in precinct_lookup.items():
        if pr_name in location_upper:
            return pr_display, "substring"
    
    # 4. Word-based match
    for pr_name, pr_display in precinct_lookup.items():
        pr_words = set(pr_name.split())
        location_words = set(location_upper.split())
        
        significant_pr_words = {w for w in pr_words if len(w) > 2}
        if significant_pr_words and significant_pr_words.issubset(location_words):
            return pr_display, "word_match"
    
    # 5 & 6. Fuzzy matching with caching
    if precinct_address_df is not None and not precinct_address_df.empty:
        parts = location_norm.split()
        potential_school = ' '.join(parts[:-5]) if len(parts) > 5 else location_norm
        potential_address = ' '.join(parts[-5:]) if len(parts) > 5 else ""
        
        best_match = None
        best_score = 0
        best_type = None
        
        # Fuzzy polling place match
        for _, row in precinct_address_df.iterrows():
            polling_norm = normalize_text(row['Polling Place'])
            
            # Quick substring check before expensive fuzzy
            if polling_norm in location_norm or location_norm in polling_norm:
                fuzzy_score = cached_fuzzy_match(location_norm, polling_norm)
                if fuzzy_score > best_score and fuzzy_score > fuzzy_threshold:
                    best_score = fuzzy_score
                    best_match = row
                    best_type = 'polling_place_fuzzy'
        
        # Fuzzy address match
        if potential_address and best_match is None:
            for _, row in precinct_address_df.iterrows():
                addr_norm = normalize_text(row['Address'])
                if addr_norm in location_norm or potential_address in addr_norm:
                    fuzzy_score = cached_fuzzy_match(potential_address, addr_norm)
                    if fuzzy_score > best_score and fuzzy_score > fuzzy_threshold:
                        best_score = fuzzy_score
                        best_match = row
                        best_type = 'address_fuzzy'
        
        if best_match is not None:
            return {
                'precinct_display': best_match['Number & Name'],
                'polling_place': best_match['Polling Place'],
                'address': best_match['Address'],
                'maps_url': f"https://www.google.com/maps/place/{quote(best_match['Address'])}",
                'match_type': best_type,
                'match_score': best_score
            }, best_type
    
    return None, "no_match"


def find_precinct_match(location_name, precinct_lookup, precinct_address_df=None, 
                        aliases=None, fuzzy_threshold=85):
    """
    Simple wrapper that returns just the precinct display name.
    """
    result, match_type = find_precinct_match_enhanced(
        location_name, precinct_lookup, precinct_address_df, aliases, fuzzy_threshold
    )
    
    if isinstance(result, dict):
        return result['precinct_display']
    
    return result


def add_alias(location_name, precinct_display, project_root=None):
    """Add a new alias for a location."""
    aliases = load_aliases(project_root)
    aliases[normalize_text(location_name)] = precinct_display
    save_aliases(aliases, project_root)
    # Clear cache since aliases changed
    cached_fuzzy_match.cache_clear()


def get_match_stats():
    """Get cache statistics for fuzzy matching."""
    return {
        'cache_hits': cached_fuzzy_match.cache_info().hits,
        'cache_misses': cached_fuzzy_match.cache_info().misses,
        'cache_size': cached_fuzzy_match.cache_info().currsize
    }
