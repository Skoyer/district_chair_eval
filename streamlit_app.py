import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import logging

sys.path.insert(0, str(Path(__file__).parent / "src"))

from main_processor import process, load_precinct_master
from reporting import generate_needs_report, generate_dashboard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="LCRC Volunteer Signup Processor", layout="wide")

st.title("🗳️ LCRC Election Volunteer Signup Processor")
st.markdown("---")

project_root = Path(__file__).parent
input_dir = project_root / "input"
output_dir = project_root / "output"
reference_dir = project_root / "reference_data"

input_dir.mkdir(exist_ok=True)
output_dir.mkdir(exist_ok=True)

option = st.selectbox(
    "Choose an operation:",
    [
        "1) Create Blank Signup from SignUpGenius file",
        "2) Create Blank Signup from upcoming_Assignments.csv",
        "3) Process upcoming_Assignments.csv and show needs report",
        "4) Process SignUpGenius file(s) and create needs report"
    ]
)

st.markdown("---")

if option == "1) Create Blank Signup from SignUpGenius file":
    st.header("Create Blank Signup Template")

    upcoming_file = input_dir / "upcoming_Assignments.csv"

    if not upcoming_file.exists():
        st.error(f"upcoming_Assignments.csv not found in {input_dir}")
        st.info("Please run the main processor first to generate upcoming_Assignments.csv")
    else:
        if st.button("Create Blank Signup Template"):
            try:
                df = pd.read_csv(upcoming_file)

                blank_df = df.copy()
                blank_df['Volunteer_Key'] = '__'
                blank_df['Volunteer_Name'] = '__'
                blank_df['Past_Count'] = 0
                blank_df['Last_Signup_Date'] = ''

                output_path = output_dir / f"blank_signup_template_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                blank_df.to_csv(output_path, index=False, encoding='utf-8-sig')

                st.success(f"✅ Created blank signup template with {len(blank_df)} rows: {output_path.name}")
                st.info(f"Template includes all {len(blank_df)} district/precinct/role/timeslot combinations with volunteer information blanked out")
                st.dataframe(blank_df.head(20))

                with open(output_path, 'rb') as f:
                    st.download_button(
                        label="Download Blank Template",
                        data=f,
                        file_name=output_path.name,
                        mime='text/csv'
                    )

            except Exception as e:
                st.error(f"Error creating blank signup: {str(e)}")
                logger.exception("Error in create blank signup")

elif option == "2) Create Blank Signup from upcoming_Assignments.csv":
    st.header("Create Blank Signup from upcoming_Assignments.csv")
    
    upcoming_file = input_dir / "upcoming_Assignments.csv"
    
    if not upcoming_file.exists():
        st.error(f"upcoming_Assignments.csv not found in {input_dir}")
        st.info("Please run the main processor first to generate upcoming_Assignments.csv")
    else:
        if st.button("Create Blank Signup from Assignments"):
            try:
                df = pd.read_csv(upcoming_file)

                blank_df = df.copy()
                blank_df['Volunteer_Key'] = '__'
                blank_df['Volunteer_Name'] = '__'
                blank_df['Past_Count'] = 0
                blank_df['Last_Signup_Date'] = ''

                output_path = output_dir / f"blank_signup_template_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                blank_df.to_csv(output_path, index=False, encoding='utf-8-sig')

                st.success(f"✅ Created blank signup template with {len(blank_df)} rows: {output_path.name}")
                st.info(f"Template includes all {len(blank_df)} district/precinct/role/timeslot combinations")
                st.dataframe(blank_df.head(20))

                with open(output_path, 'rb') as f:
                    st.download_button(
                        label="Download Blank Template",
                        data=f,
                        file_name=output_path.name,
                        mime='text/csv'
                    )

            except Exception as e:
                st.error(f"Error creating blank signup: {str(e)}")
                logger.exception("Error in create blank signup from assignments")

elif option == "3) Process upcoming_Assignments.csv and show needs report":
    st.header("Process upcoming_Assignments.csv and Show Needs Report")
    
    upcoming_file = input_dir / "upcoming_Assignments.csv"
    
    if not upcoming_file.exists():
        st.error(f"upcoming_Assignments.csv not found in {input_dir}")
        st.info("Please run the main processor first to generate upcoming_Assignments.csv")
    else:
        output_format = st.selectbox("Output format:", ["csv", "html", "markdown"])
        
        if st.button("Generate Needs Report"):
            try:
                with st.spinner("Processing assignments and generating needs report..."):
                    df = pd.read_csv(upcoming_file)
                    precinct_master, _ = load_precinct_master(project_root)

                    generate_needs_report(project_root, output_format=output_format)
                    
                    needs_report_path = output_dir / f"needs_report.{output_format}"
                    
                    if needs_report_path.exists():
                        st.success(f"✅ Generated needs report: {needs_report_path.name}")
                        
                        if output_format == 'csv':
                            report_df = pd.read_csv(needs_report_path)
                            st.dataframe(report_df, use_container_width=True)
                            
                            with open(needs_report_path, 'rb') as f:
                                st.download_button(
                                    label="Download Needs Report",
                                    data=f,
                                    file_name=needs_report_path.name,
                                    mime='text/csv'
                                )
                        elif output_format == 'html':
                            with open(needs_report_path, 'r') as f:
                                st.components.v1.html(f.read(), height=600, scrolling=True)
                        else:
                            with open(needs_report_path, 'r') as f:
                                st.markdown(f.read())
                    else:
                        st.error("Needs report was not generated")
                        
            except Exception as e:
                st.error(f"Error generating needs report: {str(e)}")
                logger.exception("Error in generate needs report")

elif option == "4) Process SignUpGenius file(s) and create needs report":
    st.header("Process SignUpGenius File(s) and Create Needs Report")
    
    signup_files = list(input_dir.glob("*.csv")) + list(input_dir.glob("*.xlsx"))
    signup_files = [f for f in signup_files if f.name != "upcoming_Assignments.csv"]
    
    if not signup_files:
        st.error(f"No signup files found in {input_dir}")
        st.info("Please place CSV or Excel files in the input directory")
    else:
        st.success(f"Found {len(signup_files)} file(s) in input directory")
        
        for f in signup_files:
            st.write(f"- {f.name}")
        
        include_backups = st.checkbox("Include backup assignments", value=True)
        fuzzy_threshold = st.slider("Fuzzy matching threshold", 0, 100, 85)
        output_format = st.selectbox("Needs report format:", ["csv", "html", "markdown"])
        
        if st.button("Process Signups and Generate Needs Report"):
            try:
                with st.spinner("Processing signups..."):
                    config = {
                        'include_backups': include_backups,
                        'fuzzy_threshold': fuzzy_threshold
                    }
                    
                    result = process(project_root, config)
                    
                    st.success("✅ Processing complete!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Volunteers", result['volunteer_count'])
                    with col2:
                        st.metric("Assignment Rows", result['assignment_rows'])
                    with col3:
                        st.metric("Duplicates Resolved", result['duplicates_resolved'])
                    
                with st.spinner("Generating needs report..."):
                    generate_needs_report(project_root, output_format=output_format)
                    
                    needs_report_path = output_dir / f"needs_report.{output_format}"
                    
                    if needs_report_path.exists():
                        st.success(f"✅ Generated needs report: {needs_report_path.name}")
                        
                        if output_format == 'csv':
                            report_df = pd.read_csv(needs_report_path)
                            st.dataframe(report_df, use_container_width=True)
                            
                            with open(needs_report_path, 'rb') as f:
                                st.download_button(
                                    label="Download Needs Report",
                                    data=f,
                                    file_name=needs_report_path.name,
                                    mime='text/csv'
                                )
                        elif output_format == 'html':
                            with open(needs_report_path, 'r') as f:
                                st.components.v1.html(f.read(), height=600, scrolling=True)
                        else:
                            with open(needs_report_path, 'r') as f:
                                st.markdown(f.read())
                    
                    dashboard_path = output_dir / "dashboard.html"
                    if dashboard_path.exists():
                        st.info(f"📊 Dashboard generated: {dashboard_path.name}")
                        
            except Exception as e:
                st.error(f"Error processing signups: {str(e)}")
                logger.exception("Error in process signups")

st.markdown("---")
st.markdown("### 📁 File Locations")
st.write(f"**Input Directory:** `{input_dir}`")
st.write(f"**Output Directory:** `{output_dir}`")
st.write(f"**Reference Data:** `{reference_dir}`")
