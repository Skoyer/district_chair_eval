"""
Volunteer utilities for affinity scoring and auto-suggestions.
"""
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def compute_volunteer_affinity(volunteer_master_csv, upcoming_assignments_csv, threshold=5):
    """
    Compute volunteer affinity (frequency of signing up for same precinct).
    
    Args:
        volunteer_master_csv: Path to VolunteerMaster.csv
        upcoming_assignments_csv: Path to upcoming_Assignments.csv
        threshold: Minimum signups to auto-suggest (default 5)
    
    Returns:
        suggestions_df: Volunteers meeting threshold
        review_needed_df: Volunteers below threshold
    """
    if not volunteer_master_csv.exists() or not upcoming_assignments_csv.exists():
        logger.warning("Required files not found for affinity computation")
        return pd.DataFrame(), pd.DataFrame()
    
    vm = pd.read_csv(volunteer_master_csv)
    assignments = pd.read_csv(upcoming_assignments_csv)
    
    # Filter out unassigned slots
    assigned = assignments[assignments['Volunteer_Key'] != '__']
    
    if assigned.empty:
        logger.info("No assigned volunteers found for affinity analysis")
        return pd.DataFrame(), pd.DataFrame()
    
    # Count signups per volunteer per precinct
    affinity = assigned.groupby(['Volunteer_Key', 'Precinct']).size().reset_index(name='Signup_Count')
    
    # Get volunteer info
    affinity = affinity.merge(
        vm[['Volunteer_Key', 'First_Name', 'Last_Name', 'Email', 'Phone']],
        on='Volunteer_Key',
        how='left'
    )
    
    # Compute affinity score (normalized by total signups)
    total_signups = assigned.groupby('Volunteer_Key').size().reset_index(name='Total_Signups')
    affinity = affinity.merge(total_signups, on='Volunteer_Key')
    affinity['Affinity_Score'] = (affinity['Signup_Count'] / affinity['Total_Signups'] * 100).round(1)
    
    # Split by threshold
    suggestions = affinity[affinity['Signup_Count'] >= threshold].copy()
    review_needed = affinity[affinity['Signup_Count'] < threshold].copy()
    
    # Sort by signup count descending
    suggestions = suggestions.sort_values(['Signup_Count', 'Volunteer_Key'], ascending=[False, True])
    review_needed = review_needed.sort_values(['Signup_Count', 'Volunteer_Key'], ascending=[False, True])
    
    logger.info(f"Found {len(suggestions)} high-affinity volunteer assignments (>= {threshold} signups)")
    logger.info(f"Found {len(review_needed)} assignments needing review (< {threshold} signups)")
    
    return suggestions, review_needed


def generate_volunteer_suggestions(project_root, threshold=5):
    """
    Generate volunteer suggestions and save to CSV files.
    
    Returns:
        dict with paths to generated files
    """
    volunteer_master_csv = project_root / "VolunteerMaster.csv"
    upcoming_assignments_csv = project_root / "upcoming_Assignments.csv"
    
    suggestions, review_needed = compute_volunteer_affinity(
        volunteer_master_csv, upcoming_assignments_csv, threshold
    )
    
    output_files = {}

    if not suggestions.empty:
        suggestions_file = project_root / "output" / "VolunteerMaster_suggestions.csv"
        suggestions_file.parent.mkdir(exist_ok=True)
        suggestions.to_csv(suggestions_file, index=False)
        output_files['suggestions'] = suggestions_file
        logger.info(f"Saved suggestions to {suggestions_file}")

    if not review_needed.empty:
        review_file = project_root / "output" / "review_needed.csv"
        review_file.parent.mkdir(exist_ok=True)
        review_needed.to_csv(review_file, index=False)
        output_files['review_needed'] = review_file
        logger.info(f"Saved review list to {review_file}")
    
    return output_files


def get_volunteer_history(volunteer_key, volunteer_master_csv, upcoming_assignments_csv):
    """
    Get full history for a specific volunteer.
    
    Returns:
        dict with volunteer info and assignment history
    """
    if not volunteer_master_csv.exists() or not upcoming_assignments_csv.exists():
        return None
    
    vm = pd.read_csv(volunteer_master_csv)
    assignments = pd.read_csv(upcoming_assignments_csv)
    
    volunteer = vm[vm['Volunteer_Key'] == volunteer_key]
    if volunteer.empty:
        return None
    
    vol_assignments = assignments[assignments['Volunteer_Key'] == volunteer_key]
    
    return {
        'info': volunteer.iloc[0].to_dict(),
        'assignments': vol_assignments.to_dict('records'),
        'total_assignments': len(vol_assignments),
        'unique_precincts': vol_assignments['Precinct'].nunique() if not vol_assignments.empty else 0
    }
