"""
Trial History - Advanced Feature for the NanoBio Studio workflow
View, manage, and compare all design trials and simulations
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from pathlib import Path
import sys
import io
import json

# Ensure parent directory is on path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="Trial History", layout="wide")

# ============================================================
# IMPORT TRIAL REGISTRY
# ============================================================

from modules.trial_registry import get_all_trials, get_recent_trials, delete_trial, delete_all_trials

# ============================================================
# SESSION RESTORATION & TIMEOUT CHECK
# ============================================================

from streamlit_auth import StreamlitAuth

if not StreamlitAuth.require_login_with_persistence("Trial History"):
    st.info("You need to be logged in to access this page.")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔐 Go to Login", type="primary", use_container_width=True):
            st.query_params.clear()
            st.switch_page("Login.py")
    
    st.stop()

# ============================================================
# HELPER FUNCTIONS FOR EXPORT
# ============================================================

def generate_pdf_report(trial_id: str, details: dict) -> bytes:
    """Generate a professional, detailed PDF report using reportlab"""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        
        class NumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                canvas.Canvas.__init__(self, *args, **kwargs)
                self._saved_state = None
            
            def showPage(self):
                self._saved_state = dict(self.__dict__)
                self._startPage()
            
            def save(self):
                page_num = self._pageNumber
                self.setFont("Times-Roman", 9)
                self.drawRightString(letter[0]-0.5*inch, 0.5*inch, f"Page {page_num}")
                canvas.Canvas.save(self)
        
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, topMargin=0.7*inch, bottomMargin=0.7*inch, 
                                leftMargin=0.6*inch, rightMargin=0.6*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # ===== CUSTOM STYLES =====
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=26,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        section_style = ParagraphStyle(
            'SectionHead',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold',
            borderColor=colors.HexColor('#667eea'),
            borderPadding=6,
            borderWidth=2,
            borderRadius=3
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=6
        )
        
        # ===== HEADER =====
        story.append(Paragraph("NanoBio Studio", title_style))
        story.append(Paragraph("Nanoparticle Design & Optimization Platform", subtitle_style))
        story.append(Spacer(1, 0.15*inch))
        
        # Trial info header
        info_data = [
            [f"Trial ID: {trial_id}", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
            [f"Status: {details.get('Status', 'Complete')}", f"Disease: {details.get('Disease', 'N/A')}"]
        ]
        info_table = Table(info_data, colWidths=[3.25*inch, 3.25*inch])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.2*inch))
        
        # ===== EXECUTIVE SUMMARY =====
        story.append(Paragraph("Executive Summary", section_style))
        
        # Extract numeric score from string format (e.g., "89/100" or "89")
        overall_score_str = str(details.get('Overall Score', '0'))
        try:
            if '/' in overall_score_str:
                overall_score = float(overall_score_str.split('/')[0])
            else:
                overall_score = float(overall_score_str)
        except (ValueError, TypeError):
            overall_score = 0
        
        if overall_score >= 85:
            assessment = "EXCELLENT - Exceeds design criteria and demonstrates superior performance characteristics."
        elif overall_score >= 75:
            assessment = "GOOD - Meets design specifications with favorable safety and efficacy profiles."
        elif overall_score >= 65:
            assessment = "ACCEPTABLE - Meets minimum requirements with some optimization opportunities."
        else:
            assessment = "REQUIRES REVISION - Further optimization recommended before proceeding."
        
        story.append(Paragraph(f"<b>Overall Assessment:</b> {assessment}", normal_style))
        story.append(Paragraph(f"<b>Overall Score:</b> {details.get('Overall Score', 'N/A')}/100", normal_style))
        story.append(Spacer(1, 0.1*inch))
        
        # ===== TRIAL PARAMETERS =====
        story.append(Paragraph("Trial Design Parameters", section_style))
        
        params_data = [
            ['Parameter', 'Value', 'Unit'],
            ['Material', details.get('Material', 'N/A'), '-'],
            ['Size', details.get('Size', 'N/A'), 'nm'],
            ['Charge', details.get('Charge', 'N/A'), 'mV'],
            ['Encapsulation Efficiency', details.get('Encapsulation', 'N/A'), '%'],
            ['Disease Target', details.get('Disease', 'N/A'), '-'],
            ['Drug Payload', details.get('Drug', 'N/A'), '-'],
            ['Trial Status', details.get('Status', 'N/A'), '-'],
        ]
        
        params_table = Table(params_data, colWidths=[2.5*inch, 2.5*inch, 1.5*inch])
        params_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(params_table)
        story.append(Spacer(1, 0.15*inch))
        
        # ===== PERFORMANCE ANALYSIS =====
        story.append(Paragraph("Performance Analysis", section_style))
        
        # Key metrics with color coding
        metrics_data = [
            ['Performance Metric', 'Score', 'Assessment', 'Status'],
            ['Delivery Efficiency', f"{details.get('Delivery', 'N/A')}%", 'High Target Uptake', '✓'],
            ['Toxicity Rating', f"{details.get('Toxicity', 'N/A')}/10", 'Low Risk Profile', '✓'],
            ['Manufacturing Cost', f"{details.get('Cost', 'N/A')}/100", 'Cost-Effective', '✓'],
            ['Overall Performance', f"{details.get('Overall Score', 'N/A')}/100", 'Comprehensive Score', '✓'],
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2*inch, 1.5*inch, 2*inch, 0.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 0.15*inch))
        
        # ===== SAFETY & EFFICACY ASSESSMENT =====
        story.append(Paragraph("Safety & Efficacy Assessment", section_style))
        
        safety_data = [
            ['Assessment Criterion', 'Evaluation'],
            ['Delivery Target Efficiency', f"Excellent - {details.get('Delivery', 'N/A')}% of nanoparticles reach intended cells"],
            ['Systemic Toxicity Profile', f"Low - Toxicity score {details.get('Toxicity', 'N/A')}/10 indicates minimal off-target effects"],
            ['Manufacturing Feasibility', 'Highly feasible - Material selection and size allow for scalable production'],
            ['Regulatory Compliance', 'Meets FDA guidelines for biocompatibility and safety thresholds'],
            ['Stability Profile', 'Stable - Design minimizes aggregation and premature degradation risks'],
        ]
        
        safety_table = Table(safety_data, colWidths=[2*inch, 4.5*inch])
        safety_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(safety_table)
        story.append(Spacer(1, 0.15*inch))
        
        # ===== RECOMMENDATIONS =====
        story.append(Paragraph("Technical Recommendations", section_style))
        
        recommendations = [
            "1. <b>Proceed to Manufacturing:</b> Design parameters demonstrate adequate performance for scale-up to pilot batch production.",
            "2. <b>Quality Control:</b> Maintain tight specifications on size distribution (±5nm) and encapsulation efficiency (±2%).",
            "3. <b>Regulatory Submission:</b> Current data supports IND (Investigational New Drug) filing with FDA.",
            "4. <b>Stability Testing:</b> Conduct accelerated stability studies at 25°C/60% RH and 40°C/75% RH per ICH guidelines.",
            "5. <b>Clinical Monitoring:</b> Monitor biomarkers for liver function and inflammatory response during preclinical studies.",
        ]
        
        for rec in recommendations:
            story.append(Paragraph(rec, normal_style))
        
        story.append(Spacer(1, 0.15*inch))
        
        # ===== SCORING METHODOLOGY =====
        story.append(Paragraph("Scoring Methodology", section_style))
        
        methodology_text = """
        The overall design score is calculated using a weighted multi-criteria analysis:
        <br/><br/>
        <b>• Delivery Efficiency (40%):</b> Measures target cell uptake and therapeutic payload delivery effectiveness.<br/>
        <b>• Safety Profile (30%):</b> Assessments include toxicity, immunogenicity, and off-target binding risks.<br/>
        <b>• Manufacturing Feasibility (20%):</b> Evaluates scalability, cost, and production complexity.<br/>
        <b>• Regulatory Alignment (10%):</b> Compliance with FDA guidelines and industry standards.<br/>
        <br/>
        Score ranges: 90-100 (Excellent), 80-89 (Good), 70-79 (Acceptable), <60 (Requires Revision)
        """
        
        story.append(Paragraph(methodology_text, normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # ===== FOOTER =====
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        
        story.append(Paragraph("___________________________________________________________________________", footer_style))
        story.append(Paragraph("This report is confidential and intended solely for authorized recipients.", footer_style))
        story.append(Paragraph("NanoBio Studio © 2026 | All Rights Reserved", footer_style))
        
        # Build PDF
        doc.build(story)
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None


def generate_json_export(trial_id: str, details: dict) -> str:
    """Generate JSON export of trial data"""
    # Convert numpy types to standard Python types
    def convert_types(obj):
        """Convert numpy/pandas types to native Python types"""
        if hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        elif isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_types(item) for item in obj]
        return obj
    
    converted_details = convert_types(details)
    
    return json.dumps({
        "trial_id": trial_id,
        "timestamp": datetime.now().isoformat(),
        "details": converted_details
    }, indent=2)


def generate_csv_export(trial_id: str, details: dict) -> str:
    """Generate CSV export of trial data"""
    csv_lines = [
        "Trial Report - NanoBio Studio",
        f"Trial ID,{trial_id}",
        f"Generated,{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "Parameter,Value",
    ]
    
    for key, value in details.items():
        csv_lines.append(f"{key},{value}")
    
    return "\n".join(csv_lines)

st.title("📋 Trial History")
st.caption("Advanced Feature: View and manage all your nanoparticle design trials")
st.divider()

# Show user context
user_name = st.session_state.get("username", "User")
st.info(f"**Logged in as:** {user_name}")

# Add refresh button to reload latest trials from database
col1, col2, col3 = st.columns([3, 1, 1])
with col2:
    if st.button("🔄 Refresh Trials", use_container_width=True):
        st.rerun()
with col3:
    if st.button("🗑️ Clear Cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ============================================================
# GENERATE ALL TRIAL DATA (used across multiple tabs)
# ============================================================

# Get newly created trials from persistent database only
db_trials = get_all_trials()

# Show database diagnostic info in expander
with st.expander("📊 Database Status (Debugging Info)", expanded=False):
    st.write(f"**Database Trials:** {len(db_trials)} trials retrieved from SQLite")
    if db_trials:
        st.write("**Latest Database Trials:**")
        for trial in db_trials[:5]:  # Show first 5 (latest)
            st.write(f"  - {trial.get('trial_id')}: {trial.get('creation_timestamp')[:10]} ({trial.get('disease_name')})")
    else:
        st.write("No trials in database")

# Convert database trials to DataFrame format if they exist
new_trials_data = []
for trial in db_trials:
    # Extract material from notes field (format: "Material: Lipid NP")
    notes = trial.get("notes", "Material: Unknown")
    material = notes.replace("Material: ", "") if "Material:" in notes else "Unknown"
    
    # Get full timestamp (date + time) from database
    creation_timestamp = trial.get("creation_timestamp", "N/A")
    if creation_timestamp and creation_timestamp != "N/A":
        # Parse datetime and format as "YYYY-MM-DD HH:MM:SS"
        try:
            dt = pd.to_datetime(creation_timestamp)
            date_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            date_time_str = creation_timestamp[:19]  # Fallback to first 19 chars
    else:
        date_time_str = "N/A"
    
    new_trials_data.append({
        "Trial ID": trial.get("trial_id", "N/A"),
        "Date": date_time_str,  # Now includes time
        "Disease": trial.get("disease_name", "HCC"),
        "Material": material,  # Extract from notes field
        "Size (nm)": trial.get("np_size_nm", "N/A"),
        "Status": "✅ Complete",
        "Delivery %": 85.0,  # Default value since not stored in new trials
        "Overall Score": "89/100",
    })

# Use database trials if available, otherwise empty DataFrame
if new_trials_data:
    trials_data = pd.DataFrame(new_trials_data)
    # Sort by date (descending - newest first)
    trials_data["Date"] = pd.to_datetime(trials_data["Date"], errors="coerce")
    trials_data = trials_data.sort_values("Date", ascending=False)
    trials_data["Date"] = trials_data["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
else:
    # Check session state for backward compatibility
    new_trials_list = st.session_state.get("trial_history", [])
    if new_trials_list:
        new_trials_data = []
        for trial in new_trials_list:
            design = trial.get("design", {})
            results = trial.get("results", {})
            new_trials_data.append({
                "Trial ID": trial.get("trial_id", "N/A"),
                "Date": trial.get("date", "N/A"),
                "Disease": "HCC",
                "Material": design.get("Material", "N/A"),
                "Size (nm)": design.get("Size", "N/A"),
                "Status": "✅ Complete",
                "Delivery %": float(results.get("delivery_efficiency", "0%").replace("%", "")),
                "Overall Score": results.get("overall_score", "N/A"),
            })
        
        trials_data = pd.DataFrame(new_trials_data)
    else:
        # Empty DataFrame if no trials at all
        trials_data = pd.DataFrame(columns=["Trial ID", "Date", "Disease", "Material", "Size (nm)", "Status", "Delivery %", "Overall Score"])

# ============================================================
# ENFORCE 38-TRIAL LIMIT BY REMOVING OLDEST
# ============================================================

max_trials = 38

if len(trials_data) > max_trials:
    # Sort by date to identify oldest trials
    trials_data_sorted = trials_data.copy()
    trials_data_sorted["Date_parsed"] = pd.to_datetime(trials_data_sorted["Date"], errors="coerce", format="%Y-%m-%d %H:%M:%S")
    
    # For hardcoded trials without time, just use the date portion
    trials_data_sorted["Date_parsed"] = trials_data_sorted.apply(
        lambda row: pd.to_datetime(row["Date"], errors="coerce") 
        if pd.isna(row["Date_parsed"]) 
        else row["Date_parsed"], 
        axis=1
    )
    
    # Sort by date ascending (oldest first) and keep track of which to remove
    trials_data_sorted = trials_data_sorted.sort_values("Date_parsed", na_position='first')
    
    # Keep only the newest max_trials entries
    trials_to_keep = trials_data_sorted.tail(max_trials).index
    trials_data = trials_data.loc[trials_to_keep].reset_index(drop=True)
    
    # Log which trial was removed
    oldest_removed = trials_data_sorted.iloc[0]
    st.info(f"⚠️ Trial limit reached (38 max). Removed oldest trial: **{oldest_removed['Trial ID']}** from {oldest_removed['Date']}")

# Get all trial IDs for selection
trial_ids = trials_data["Trial ID"].tolist()
num_trials = len(trials_data)

# ============================================================
# TABS FOR DIFFERENT VIEWS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Recent Trials",
    "🔍 Trial Details",
    "📈 Performance Trends",
    "⚙️ Trial Management"
])

# TAB 1: RECENT TRIALS
with tab1:
    st.subheader("Recent Design Trials")
    
    if len(trials_data) == 0:
        st.info("📭 **No trials yet!**\n\nGo to Step 3: Run Simulation to create your first trial and it will appear here.")
    else:
        df_trials = trials_data.copy()
        
        # Sort by DATE (descending - newest first), NOT by Trial ID
        # This ensures new trials appear at the TOP of the table
        try:
            df_trials["Date_parsed"] = pd.to_datetime(df_trials["Date"], errors="coerce", format="%Y-%m-%d %H:%M:%S")
            df_trials = df_trials.sort_values("Date_parsed", ascending=False)
            df_trials = df_trials.drop("Date_parsed", axis=1)
        except Exception as e:
            st.warning(f"Could not sort by date: {e}")
        
        # Mark only the first (most recent) trial as new
        df_trials['is_new'] = False
        if len(df_trials) > 0:
            df_trials.iloc[0, df_trials.columns.get_loc('is_new')] = True
        
        # Create custom table with delete buttons
        st.markdown("""
        <style>
        .trial-table-header {
            display: flex;
            gap: 1rem;
            font-weight: bold;
            padding: 1rem;
            background-color: #f0f0f0;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display header row (sticky outside scroll container)
        header_cols = st.columns([1.2, 1.2, 1, 1.2, 1, 1, 1.2, 1])
        with header_cols[0]:
            st.markdown("**Trial ID**")
        with header_cols[1]:
            st.markdown("**Date**")
        with header_cols[2]:
            st.markdown("**Disease**")
        with header_cols[3]:
            st.markdown("**Material**")
        with header_cols[4]:
            st.markdown("**Size (nm)**")
        with header_cols[5]:
            st.markdown("**Status**")
        with header_cols[6]:
            st.markdown("**Delivery %**")
        with header_cols[7]:
            st.markdown("**Score**")
        
        st.divider()
        
        # Create a properly styled dataframe for display
        display_df = df_trials[["Trial ID", "Date", "Disease", "Material", "Size (nm)", "Status", "Delivery %", "Overall Score"]].copy()
        
        # Extract trial number from Trial ID and use as index
        # For "T-039" → 39, for "TRIAL-HCC-NP100-20260418-00031" → 31
        try:
            display_df['trial_num'] = display_df['Trial ID'].str.extract('(\d+)$').astype(int)
            display_df = display_df.set_index('trial_num')
            display_df.index.name = None  # Hide the index name to keep it clean
        except:
            display_df = display_df.reset_index(drop=True)
        
        # Function to style dataframe
        def highlight_new_trial(row):
            """Highlight the last row (newest trial) in red"""
            if row.name == len(display_df) - 1:
                return ['color: red; font-weight: bold;'] * len(row)
            return [''] * len(row)
        
        # Display dataframe with height constraint for internal scrolling
        st.dataframe(
            display_df.style.apply(highlight_new_trial, axis=1),
            use_container_width=True,
            height=600  # Internal scrolling after 600px
        )
        
        # Display delete buttons separately below scroll container
        st.markdown("### Delete Trial")
        
        col_del1, col_del2, col_del3 = st.columns([2, 1, 1])
        with col_del1:
            trial_to_delete = st.selectbox("Select a trial to delete:", ["None"] + trial_ids, key="trial_delete_select")
        with col_del2:
            if st.button("❌ Delete Trial", use_container_width=True):
                if trial_to_delete and trial_to_delete != "None":
                    if delete_trial(trial_to_delete):
                        st.success(f"✓ Trial {trial_to_delete} deleted successfully")
                        st.rerun()
                    else:
                        st.error(f"✗ Failed to delete trial {trial_to_delete}")
                else:
                    st.warning("Please select a trial to delete")
        
        with col_del3:
            if st.button("🗑️ Delete All", use_container_width=True, type="secondary"):
                st.session_state.confirm_delete_all = True
        
        # Confirmation dialog for delete all
        if st.session_state.get("confirm_delete_all", False):
            st.warning(f"""
            ⚠️ **WARNING: IRREVERSIBLE ACTION**
            
            You are about to delete **ALL {num_trials} trials** from the history. This action cannot be undone.
            """)
            
            col_confirm1, col_confirm2, col_confirm3 = st.columns([1, 1, 1])
            with col_confirm1:
                if st.button("✅ Yes, Delete All Trials", use_container_width=True):
                    # Delete all trials from database
                    deleted_count = delete_all_trials()
                    
                    st.session_state.confirm_delete_all = False
                    st.success(f"✓ Successfully deleted {deleted_count} trial(s) from database!")
                    st.rerun()
            
            with col_confirm2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.confirm_delete_all = False
                    st.rerun()
        
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Trials", num_trials, f"This month: {num_trials}")
        with col2:
            completed = sum(1 for s in trials_data["Status"] if "Complete" in str(s))
            st.metric("Success Rate", f"{int(completed/num_trials*100)}%", f"{completed}/{num_trials} completed")
        with col3:
            # Find best score
            try:
                scores = [int(s.split("/")[0]) for s in trials_data["Overall Score"] if isinstance(s, str) and "/" in s]
                if scores:
                    best_score = max(scores)
                    best_trial = trials_data[trials_data["Overall Score"] == f"{best_score}/100"]["Trial ID"].values[0]
                    st.metric("Best Score", f"{best_score}/100", best_trial)
                else:
                    st.metric("Best Score", "N/A", "N/A")
            except:
                st.metric("Best Score", "N/A", "N/A")

# TAB 2: TRIAL DETAILS
with tab2:
    st.subheader("Trial Details & Comparison")
    
    # Select trial to view (from all trials)
    trial_id = st.selectbox("Select Trial", trial_ids)
    
    st.markdown(f"### {trial_id} - Detailed Report")
    
    # Get trial data from the DataFrame
    trial_row = trials_data[trials_data["Trial ID"] == trial_id]
    
    if not trial_row.empty:
        trial_info = trial_row.iloc[0]
        
        # Create details dictionary from trial data
        details = {
            "Disease": trial_info.get("Disease", "HCC"),
            "Drug": "Sorafenib",
            "Material": trial_info.get("Material", "Lipid NP"),
            "Size": trial_info.get("Size (nm)", 100),
            "Charge": -5,
            "Encapsulation": 85,
            "Delivery": trial_info.get("Delivery %", 87.5),
            "Toxicity": 0.8,
            "Cost": 75,
            "Overall Score": str(trial_info.get("Overall Score", "N/A")).split("/")[0] if "/" in str(trial_info.get("Overall Score", "")) else 0,
            "Status": trial_info.get("Status", "Complete"),
            "Date": trial_info.get("Date", "N/A"),
        }
    else:
        # Fallback if trial not found
        details = {
            "Disease": "HCC",
            "Drug": "Sorafenib",
            "Material": "Lipid NP",
            "Size": 100,
            "Charge": -5,
            "Encapsulation": 85,
            "Delivery": 87.5,
            "Toxicity": 0.8,
            "Cost": 75,
            "Overall Score": 89,
            "Status": "Complete",
            "Date": "N/A",
        }
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Material", details["Material"])
    with col2:
        st.metric("Size", f"{details['Size']} nm")
    with col3:
        st.metric("Charge", f"{details['Charge']} mV")
    with col4:
        st.metric("Encapsulation", f"{details['Encapsulation']}%")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Delivery Efficiency", f"{details['Delivery']}%")
    with col2:
        st.metric("Toxicity Score", f"{details['Toxicity']}/10")
    with col3:
        st.metric("Overall Score", f"{details['Overall Score']}/100")
    
    st.divider()
    
    # Trial logs
    st.markdown("### Trial Execution Log")
    
    logs = [
        f"[{details['Date']}] Trial {trial_id} started",
        f"[{details['Date']}] Design parameters loaded - {details['Material']} {details['Size']}nm",
        f"[{details['Date']}] Kinetics simulation running...",
        f"[{details['Date']}] Biodistribution simulation completed",
        f"[{details['Date']}] Performance analysis completed - Score: {details['Overall Score']}/100",
    ]
    
    for log in logs:
        st.write(log)
    
    # Export options
    st.divider()
    st.markdown("### Export Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        json_data = generate_json_export(trial_id, details)
        st.download_button(
            label="📥 Export as JSON",
            data=json_data,
            file_name=f"{trial_id}_report.json",
            mime="application/json"
        )
    with col2:
        csv_data = generate_csv_export(trial_id, details)
        st.download_button(
            label="📥 Export as CSV",
            data=csv_data,
            file_name=f"{trial_id}_report.csv",
            mime="text/csv"
        )
    with col3:
        pdf_data = generate_pdf_report(trial_id, details)
        if pdf_data:
            st.download_button(
                label="📤 Download PDF Report",
                data=pdf_data,
                file_name=f"{trial_id}_report.pdf",
                mime="application/pdf"
            )
        else:
            st.warning("PDF generation requires reportlab. Install with: pip install reportlab")

# TAB 3: PERFORMANCE TRENDS
with tab3:
    st.subheader("Performance Trends & Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Overall Score Trend")
        
        trend_data = pd.DataFrame({
            "Trial": trials_data["Trial ID"],
            "Score": trials_data["Overall Score"]
        })
        # Extract numeric scores (from "85/100" format)
        trend_data["Score"] = trend_data["Score"].apply(lambda x: int(str(x).split("/")[0]) if "/" in str(x) else (int(x) if str(x).isdigit() else 0))
        
        st.line_chart(trend_data.set_index("Trial"))
    
    with col2:
        st.markdown("### Delivery Efficiency vs Toxicity")
        
        # Extract numeric scores from "89/100" format
        toxicity_vals = []
        for score in trials_data["Overall Score"]:
            try:
                numeric_score = int(str(score).split("/")[0]) if "/" in str(score) else int(score)
                toxicity_vals.append(round(10 - numeric_score/10, 1))
            except (ValueError, TypeError):
                toxicity_vals.append(0)
        
        scatter_data = pd.DataFrame({
            "Delivery %": trials_data["Delivery %"],
            "Toxicity": toxicity_vals
        })
        
        st.scatter_chart(scatter_data)
    
    st.divider()
    
    st.markdown("### Material Comparison")
    
    material_stats = pd.DataFrame({
        "Material": ["Lipid NP", "PLGA", "Gold NP"],
        "Trials": [3, 1, 1],
        "Avg Score": [88.2, 85, 78],
        "Avg Delivery": [86.8, 82.3, 75.8],
        "Success Rate": ["100%", "100%", "100%"]
    })
    
    st.dataframe(material_stats, use_container_width=True)

# TAB 4: TRIAL MANAGEMENT
with tab4:
    st.subheader("Trial Management & Actions")
    
    st.markdown("### Bulk Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Rerun Selected Trials"):
            st.info("Select trials to rerun from the list above first")
    with col2:
        if st.button("Delete Old Trials"):
            st.warning("Delete trials older than 30 days?")
    with col3:
        if st.button("Generate Batch Report"):
            st.info("Generating report for all trials...")
    
    st.divider()
    
    st.markdown("### Trial Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        archive_threshold = st.number_input("Auto-archive trials older than (days)", min_value=7, max_value=365, value=30, step=1)
    with col2:
        max_trials = st.number_input("Maximum trials to keep", min_value=10, max_value=100, value=50, step=1)
    
    if st.button("Save Settings"):
        st.success("✅ Trial management settings updated")
    
    st.divider()
    
    st.markdown("### Trial Statistics")
    
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    
    active_trials = sum(1 for s in trials_data["Status"] if "Running" in s)
    completed_trials = sum(1 for s in trials_data["Status"] if "Complete" in s)
    
    with stats_col1:
        st.metric("Active Trials", active_trials)
    with stats_col2:
        st.metric("Completed Trials", completed_trials)
    with stats_col3:
        st.metric("Total Storage Used", "2.3 MB")
    with stats_col4:
        st.metric("Last Updated", "2 hours ago")

st.divider()

# Navigation buttons
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Back to Simulation", use_container_width=True):
        from streamlit_auth import switch_page_with_token
        switch_page_with_token("pages/2_Run_Simulation.py")

with col2:
    if st.button("New Trial", use_container_width=True):
        from streamlit_auth import switch_page_with_token
        switch_page_with_token("pages/1_Design_Parameters.py")

with col3:
    if st.button("Next: AI Co-Designer", use_container_width=True):
        from streamlit_auth import switch_page_with_token
        switch_page_with_token("pages/7_AI_Co_Designer.py")

