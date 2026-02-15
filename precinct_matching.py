import re
import pandas as pd
from pathlib import Path
from fuzzywuzzy import fuzz
from urllib.parse import quote

def load_precinct_address(project_root=None):
    if project_root is None:
        project_root = Path(__file__).parent
    precinct_address_csv = project_root / "reference_data" / "precinct_address_information.csv"
    if not precinct_address_csv.exists():
        return None
    return pd.read_csv(precinct_address_csv)

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'[*,]', '', text.lower().strip())
    text = text.replace('  ', ' ')
    return text

def find_precinct_match_enhanced(location_name, precinct_lookup, precinct_address_df=None):
    location_norm = normalize_text(location_name)
    location_upper = location_name.upper().strip()
    
    if location_upper in precinct_lookup:
        return precinct_lookup[location_upper], "exact"
    
    for pr_name, pr_display in precinct_lookup.items():
        if pr_name in location_upper:
            return pr_display, "substring"
    
    for pr_name, pr_display in precinct_lookup.items():
        pr_words = set(pr_name.split())
        location_words = set(location_upper.split())
        
        significant_pr_words = {w for w in pr_words if len(w) > 2}
        if significant_pr_words and significant_pr_words.issubset(location_words):
            return pr_display, "word_match"
    
    if precinct_address_df is not None and not precinct_address_df.empty:
        parts = location_norm.split()
        potential_school = ' '.join(parts[:-5]) if len(parts) > 5 else location_norm
        potential_address = ' '.join(parts[-5:]) if len(parts) > 5 else ""
        
        best_match = None
        best_score = 0
        best_type = None
        
        for _, row in precinct_address_df.iterrows():
            polling_norm = normalize_text(row['Polling Place'])
            
            if polling_norm in location_norm or location_norm in polling_norm:
                fuzzy_score = fuzz.partial_ratio(location_norm, polling_norm)
                if fuzzy_score > best_score and fuzzy_score > 85:
                    best_score = fuzzy_score
                    best_match = row
                    best_type = 'polling_place_fuzzy'
        
        if potential_address and best_match is None:
            for _, row in precinct_address_df.iterrows():
                addr_norm = normalize_text(row['Address'])
                if addr_norm in location_norm or potential_address in addr_norm:
                    fuzzy_score = fuzz.partial_ratio(potential_address, addr_norm)
                    if fuzzy_score > best_score and fuzzy_score > 85:
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

def find_precinct_match(location_name, precinct_lookup, precinct_address_df=None):
    result, match_type = find_precinct_match_enhanced(location_name, precinct_lookup, precinct_address_df)
    
    if isinstance(result, dict):
        return result['precinct_display']
    
    return result
