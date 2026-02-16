"""
Reporting module for needs analysis and dashboard generation.
"""
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Optional matplotlib import
try:
    import matplotlib.pyplot as plt
    import base64
    from io import BytesIO
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available - charts will be disabled")


def compute_precinct_health(upcoming_assignments_df):
    """
    Compute health score for each precinct based on role coverage.
    
    Scoring:
    - Captain: 10 pts (required)
    - Equipment Drop Off: 5 pts
    - Equipment Pick Up: 5 pts
    - Greeter slots: 2 pts per slot type (Proposed/Backup) if >=1 filled
    
    Max score varies by precinct based on slot count.
    """
    results = []
    
    for precinct, group in upcoming_assignments_df.groupby(['District', 'Precinct']):
        district, precinct_name = precinct
        
        score = 0
        max_score = 0
        details = {}
        
        # Captain (10 pts)
        captain = group[group['Role'] == 'Precinct Captain']
        has_captain = (captain['Volunteer_Key'] != '__').any()
        score += 10 if has_captain else 0
        max_score += 10
        details['captain'] = '✅' if has_captain else '❌'
        
        # Equipment (5 pts each)
        for role in ['Equipment Drop Off', 'Equipment Pick Up']:
            equip = group[group['Role'] == role]
            has_equip = (equip['Volunteer_Key'] != '__').any()
            score += 5 if has_equip else 0
            max_score += 5
            details[role.lower().replace(' ', '_')] = '✅' if has_equip else '❌'
        
        # Opener (5 pts)
        opener = group[(group['Role'] == 'Opener') & (group['Assignment_Type'] == 'Proposed')]
        has_opener = (opener['Volunteer_Key'] != '__').any()
        score += 5 if has_opener else 0
        max_score += 5
        details['opener'] = '✅' if has_opener else '❌'
        
        # Closer (5 pts)
        closer = group[(group['Role'] == 'Closer') & (group['Assignment_Type'] == 'Proposed')]
        has_closer = (closer['Volunteer_Key'] != '__').any()
        score += 5 if has_closer else 0
        max_score += 5
        details['closer'] = '✅' if has_closer else '❌'
        
        # Ballot Greeters - check coverage by time slot
        greeters = group[group['Role'].str.startswith('Ballot Greeter', na=False)]
        time_slots = greeters['Slot_Time'].unique()
        
        slot_coverage = 0
        for slot in time_slots:
            if not slot or pd.isna(slot):
                continue
            slot_greeters = greeters[greeters['Slot_Time'] == slot]
            proposed = slot_greeters[slot_greeters['Assignment_Type'] == 'Proposed']
            backup = slot_greeters[slot_greeters['Assignment_Type'] == 'Backup']
            
            has_proposed = (proposed['Volunteer_Key'] != '__').any()
            has_backup = (backup['Volunteer_Key'] != '__').any()
            
            if has_proposed:
                score += 2
                slot_coverage += 1
            if has_backup:
                score += 1
                slot_coverage += 0.5
            
            max_score += 3  # 2 for proposed, 1 for backup
        
        details['slot_coverage'] = slot_coverage
        health_pct = (score / max_score * 100) if max_score > 0 else 0
        
        results.append({
            'District': district,
            'Precinct': precinct_name,
            'Health_Score': score,
            'Max_Score': max_score,
            'Health_Percent': round(health_pct, 1),
            'Need_Score': round(100 - health_pct, 1),
            'Captain': details['captain'],
            'Equipment_Drop': details['equipment_drop_off'],
            'Equipment_Pickup': details['equipment_pick_up'],
            'Opener': details['opener'],
            'Closer': details['closer'],
            'Slot_Coverage': slot_coverage
        })
    
    return pd.DataFrame(results)


def generate_needs_report(project_root, output_format='csv'):
    """
    Generate needs report showing precincts with staffing gaps.
    
    Args:
        project_root: Path to project root
        output_format: 'csv', 'html', or 'markdown'
    
    Returns:
        Path to generated report
    """
    upcoming_csv = project_root / "upcoming_Assignments.csv"
    
    if not upcoming_csv.exists():
        logger.error(f"upcoming_Assignments.csv not found at {upcoming_csv}")
        return None
    
    df = pd.read_csv(upcoming_csv)
    health_df = compute_precinct_health(df)
    
    # Sort by need (highest need first)
    health_df = health_df.sort_values('Need_Score', ascending=False)
    
    # Add priority emoji
    def get_priority(pct):
        if pct < 50:
            return '🔴 Critical'
        elif pct < 75:
            return '🟡 Needs Attention'
        else:
            return '🟢 Good'
    
    health_df['Priority'] = health_df['Health_Percent'].apply(get_priority)
    
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)

    if output_format == 'csv':
        output_path = output_dir / "needs_report.csv"
        health_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    elif output_format == 'markdown':
        output_path = output_dir / "needs_report.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Precinct Needs Report\n\n")
            f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(health_df.to_markdown(index=False))
    elif output_format == 'html':
        output_path = output_dir / "needs_report.html"
        health_df.to_html(output_path, index=False, classes='table table-striped', encoding='utf-8')
    else:
        raise ValueError(f"Unknown output format: {output_format}")
    
    logger.info(f"Generated needs report: {output_path}")
    return output_path


def generate_dashboard(project_root):
    """
    Generate comprehensive HTML dashboard with charts.
    
    Returns:
        Path to generated dashboard HTML
    """
    upcoming_csv = project_root / "upcoming_Assignments.csv"
    volunteer_csv = project_root / "VolunteerMaster.csv"
    
    if not upcoming_csv.exists():
        logger.error("upcoming_Assignments.csv not found")
        return None
    
    df = pd.read_csv(upcoming_csv)
    health_df = compute_precinct_health(df)
    
    # Create charts
    charts = {}
    
    # 1. Health distribution
    fig, ax = plt.subplots(figsize=(8, 5))
    health_ranges = ['0-25%', '25-50%', '50-75%', '75-100%']
    health_counts = [
        len(health_df[health_df['Health_Percent'] <= 25]),
        len(health_df[(health_df['Health_Percent'] > 25) & (health_df['Health_Percent'] <= 50)]),
        len(health_df[(health_df['Health_Percent'] > 50) & (health_df['Health_Percent'] <= 75)]),
        len(health_df[health_df['Health_Percent'] > 75])
    ]
    colors = ['#dc3545', '#ffc107', '#17a2b8', '#28a745']
    ax.bar(health_ranges, health_counts, color=colors)
    ax.set_ylabel('Number of Precincts')
    ax.set_title('Precinct Health Distribution')
    plt.tight_layout()
    charts['health_dist'] = _fig_to_base64(fig)
    plt.close()
    
    # 2. Top 10 needy precincts
    fig, ax = plt.subplots(figsize=(10, 6))
    needy = health_df.nsmallest(10, 'Health_Percent')
    ax.barh(needy['Precinct'], needy['Need_Score'], color='#dc3545')
    ax.set_xlabel('Need Score')
    ax.set_title('Top 10 Precincts Needing Volunteers')
    plt.tight_layout()
    charts['needy_precincts'] = _fig_to_base64(fig)
    plt.close()
    
    # 3. District summary
    fig, ax = plt.subplots(figsize=(10, 6))
    district_summary = health_df.groupby('District').agg({
        'Health_Percent': 'mean',
        'Precinct': 'count'
    }).reset_index()
    district_summary.columns = ['District', 'Avg_Health', 'Precinct_Count']
    ax.bar(district_summary['District'], district_summary['Avg_Health'], color='#17a2b8')
    ax.set_ylabel('Average Health %')
    ax.set_title('Average Health by District')
    ax.set_ylim(0, 100)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    charts['district_summary'] = _fig_to_base64(fig)
    plt.close()
    
    # Generate HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Election Volunteer Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-box {{ background: #007bff; color: white; padding: 15px; border-radius: 5px; flex: 1; text-align: center; }}
        .stat-box.critical {{ background: #dc3545; }}
        .stat-box.warning {{ background: #ffc107; color: #333; }}
        .stat-box.good {{ background: #28a745; }}
        .chart {{ margin: 20px 0; text-align: center; }}
        .chart img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #007bff; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
        .priority-critical {{ color: #dc3545; font-weight: bold; }}
        .priority-warning {{ color: #ffc107; font-weight: bold; }}
        .priority-good {{ color: #28a745; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🗳️ Election Volunteer Dashboard</h1>
        <p>Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
        
        <div class="stats">
            <div class="stat-box">
                <h3>Total Precincts</h3>
                <p style="font-size: 2em; margin: 0;">{len(health_df)}</p>
            </div>
            <div class="stat-box critical">
                <h3>Critical (&lt;50%)</h3>
                <p style="font-size: 2em; margin: 0;">{len(health_df[health_df['Health_Percent'] < 50])}</p>
            </div>
            <div class="stat-box warning">
                <h3>Needs Attention</h3>
                <p style="font-size: 2em; margin: 0;">{len(health_df[(health_df['Health_Percent'] >= 50) & (health_df['Health_Percent'] < 75)])}</p>
            </div>
            <div class="stat-box good">
                <h3>Good Coverage</h3>
                <p style="font-size: 2em; margin: 0;">{len(health_df[health_df['Health_Percent'] >= 75])}</p>
            </div>
        </div>
        
        <h2>📊 Health Distribution</h2>
        <div class="chart">
            <img src="data:image/png;base64,{charts['health_dist']}" alt="Health Distribution">
        </div>
        
        <h2>🔴 Top 10 Needy Precincts</h2>
        <div class="chart">
            <img src="data:image/png;base64,{charts['needy_precincts']}" alt="Needy Precincts">
        </div>
        
        <h2>🏘️ District Summary</h2>
        <div class="chart">
            <img src="data:image/png;base64,{charts['district_summary']}" alt="District Summary">
        </div>
        
        <h2>📋 Detailed Precinct Status</h2>
        <table>
            <thead>
                <tr>
                    <th>Priority</th>
                    <th>District</th>
                    <th>Precinct</th>
                    <th>Health %</th>
                    <th>Captain</th>
                    <th>Opener</th>
                    <th>Closer</th>
                    <th>Equip Drop</th>
                    <th>Equip Pickup</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add table rows
    for _, row in health_df.head(50).iterrows():
        priority_class = 'priority-critical' if row['Health_Percent'] < 50 else ('priority-warning' if row['Health_Percent'] < 75 else 'priority-good')
        html_content += f"""
                <tr>
                    <td class="{priority_class}">{row['Priority']}</td>
                    <td>{row['District']}</td>
                    <td>{row['Precinct']}</td>
                    <td>{row['Health_Percent']}%</td>
                    <td>{row['Captain']}</td>
                    <td>{row['Opener']}</td>
                    <td>{row['Closer']}</td>
                    <td>{row['Equipment_Drop']}</td>
                    <td>{row['Equipment_Pickup']}</td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    dashboard_path = output_dir / "dashboard.html"

    with open(dashboard_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"Generated dashboard: {dashboard_path}")
    return dashboard_path


def _fig_to_base64(fig):
    """Convert matplotlib figure to base64 string."""
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64
