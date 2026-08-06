"""
Delivery Simulation Page - PK/PD Visualization
"""

import streamlit as st
import numpy as np
import sys
from pathlib import Path
from io import BytesIO
from datetime import datetime
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.pk_model import (
    two_compartment_model,
    calculate_pk_parameters,
    create_pk_plot
)

def generate_pdf_report(design, pk_params, results, fig):
    """
    Generate a comprehensive PDF report of the simulation results
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    
    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Container for elements
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2ca02c'),
        spaceAfter=6,
        spaceBefore=6
    )
    
    # Title
    story.append(Paragraph("Delivery Simulation Report (PK/PD Analysis)", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Date and design name
    timestamp = datetime.now().strftime("%B %d, %Y at %H:%M")
    story.append(Paragraph(f"<b>Report Generated:</b> {timestamp}", styles['Normal']))
    formulation_name = design.get('Material', 'Custom Design')
    story.append(Paragraph(f"<b>Formulation:</b> {formulation_name}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Design Parameters Section
    story.append(Paragraph("Design Parameters", heading_style))
    design_data = [
        ['Parameter', 'Value'],
        ['Material Type', design.get('Material', 'Lipid NP')],
        ['Size (nm)', f"{design.get('Size', 100):.1f}"],
        ['Charge (mV)', f"{design.get('Charge', -5):.1f}"],
        ['Encapsulation (%)', f"{design.get('Encapsulation', 70):.1f}"],
        ['Dose (mg/kg)', f"{design.get('dose', 10):.1f}"],
        ['Target', design.get('Target', 'Liver Cells')],
        ['PDI', f"{design.get('PDI', 0.15):.2f}"],
    ]
    design_table = Table(design_data, colWidths=[2.5*inch, 2.5*inch])
    design_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    story.append(design_table)
    story.append(Spacer(1, 0.2*inch))
    
    # PK Parameters Section
    story.append(Paragraph("Pharmacokinetic Parameters", heading_style))
    pk_data = [
        ['Parameter', 'Value', 'Unit'],
        ['Plasma C_max', f"{pk_params['C_max_plasma']:.2f}", 'ng/mL'],
        ['Plasma T_max', f"{pk_params['T_max_plasma']:.1f}", 'hours'],
        ['Tissue C_max', f"{pk_params['C_max_tissue']:.2f}", 'ng/mL'],
        ['Tissue T_max', f"{pk_params['T_max_tissue']:.1f}", 'hours'],
        ['AUC Plasma', f"{pk_params['AUC_plasma']:.1f}", 'ng·h/mL'],
        ['AUC Tissue', f"{pk_params['AUC_tissue']:.1f}", 'ng·h/mL'],
        ['Plasma t₁/₂', f"{pk_params['t_half_plasma']:.1f}" if pk_params['t_half_plasma'] else 'N/A', 'hours'],
        ['Tissue/Plasma Ratio', f"{pk_params['tissue_accumulation_ratio']:.2f}", 'ratio'],
    ]
    pk_table = Table(pk_data, colWidths=[2.0*inch, 1.5*inch, 1.5*inch])
    pk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ca02c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))
    story.append(pk_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Page break before plot
    story.append(PageBreak())
    
    # Add plot image
    story.append(Paragraph("Concentration-Time Profiles", heading_style))
    plot_buffer = BytesIO()
    fig.savefig(plot_buffer, format='png', dpi=150, bbox_inches='tight')
    plot_buffer.seek(0)
    plot_image = Image(plot_buffer, width=6.5*inch, height=4*inch)
    story.append(plot_image)
    story.append(Spacer(1, 0.2*inch))
    
    # Clinical Interpretation
    story.append(PageBreak())
    story.append(Paragraph("Clinical Interpretation & Analysis", heading_style))
    
    interpretation_text = "<b>Distribution Kinetics:</b><br/>"
    if pk_params['T_max_tissue'] > pk_params['T_max_plasma']:
        interpretation_text += f"✓ Tissue peak is delayed by {pk_params['T_max_tissue'] - pk_params['T_max_plasma']:.1f} hours relative to plasma peak, indicating typical distribution kinetics with good tissue penetration.<br/><br/>"
    else:
        interpretation_text += "⚠ Tissue reaches peak concentration earlier than plasma, which may indicate rapid tissue distribution or altered clearance kinetics.<br/><br/>"
    
    interpretation_text += "<b>Tissue Targeting:</b><br/>"
    if pk_params['tissue_accumulation_ratio'] > 1.5:
        interpretation_text += f"✓ Strong tissue accumulation observed (ratio: {pk_params['tissue_accumulation_ratio']:.2f}), indicating excellent targeting efficacy.<br/><br/>"
    elif pk_params['tissue_accumulation_ratio'] > 1.0:
        interpretation_text += f"✓ Moderate tissue accumulation (ratio: {pk_params['tissue_accumulation_ratio']:.2f}), suggesting reasonable tissue targeting.<br/><br/>"
    else:
        interpretation_text += f"⚠ Limited tissue accumulation (ratio: {pk_params['tissue_accumulation_ratio']:.2f}), may need formulation optimization or targeting ligand adjustments.<br/><br/>"
    
    interpretation_text += "<b>Plasma Clearance:</b><br/>"
    if pk_params['t_half_plasma'] is not None:
        if pk_params['t_half_plasma'] < 6:
            interpretation_text += f"⚠ Rapid clearance (t₁/₂ = {pk_params['t_half_plasma']:.1f} h) - increased PEGylation or surface modifications may extend circulation time.<br/><br/>"
        elif pk_params['t_half_plasma'] < 24:
            interpretation_text += f"✓ Moderate circulation time (t₁/₂ = {pk_params['t_half_plasma']:.1f} h) - suitable for most therapeutic applications.<br/><br/>"
        else:
            interpretation_text += f"✓ Extended circulation (t₁/₂ = {pk_params['t_half_plasma']:.1f} h) - excellent for systemic delivery and repeated dosing strategies.<br/><br/>"
    
    interpretation_text += "<b>Peak Exposure Analysis:</b><br/>"
    if pk_params['C_max_plasma'] > 3 * pk_params['C_max_tissue']:
        interpretation_text += "High plasma exposure relative to tissue - consider dose adjustment or formulation changes to improve tissue selectivity.<br/>"
    elif pk_params['C_max_tissue'] > pk_params['C_max_plasma']:
        interpretation_text += "✓ Favorable tissue-selective profile, suggesting effective targeting and reduced systemic exposure."
    
    story.append(Paragraph(interpretation_text, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def get_complete_design():
    """Get design dict with all required keys, filling in defaults if missing"""
    defaults = {
        "Material": "Lipid NP",
        "Size": 100,
        "Charge": -5,
        "Encapsulation": 70,
        "Target": "Liver Cells",
        "Ligand": "GalNAc",
        "Receptor": "ASGPR",
        "HydrodynamicSize": 120,
        "PDI": 0.15,
        "SurfaceArea": 250,
        "PoreSize": 2.5,
        "DegradationTime": 30,
        "Stability": 85,
        "dose": 10.0,
        "kabs": 0.5,
        "kel": 0.1,
        "k12": 0.3,
        "k21": 0.2
    }
    
    # Get current design or start with defaults
    current = st.session_state.design if hasattr(st.session_state, 'design') and st.session_state.design else {}
    
    # Merge current with defaults (defaults fill in missing keys)
    complete_design = defaults.copy()
    complete_design.update(current)
    
    return complete_design

def show():
    """Display PK/PD simulation interface"""
    
    try:
        # Initialize session state variables if they don't exist
        if 'simulation_results' not in st.session_state:
            st.session_state.simulation_results = None
        if 'pdf_report' not in st.session_state:
            st.session_state.pdf_report = None
        
        # Ensure design is complete with all required keys
        st.session_state.design = get_complete_design()
    except Exception as e:
        st.error(f"❌ Error initializing simulation: {str(e)}")
        st.stop()
    
    st.title("📊 Delivery Simulation (PK/PD)")
    st.markdown("Visualize drug delivery kinetics with two-compartment pharmacokinetic modeling")
    
    st.markdown("---")
    
    # Display current design
    with st.expander("📋 Current Design Parameters", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Material", st.session_state.design.get('Material', 'Lipid NP'))
            st.metric("Target", st.session_state.design.get('Target', 'Liver Cells'))
        
        with col2:
            st.metric("Size", f"{st.session_state.design.get('Size', 100):.1f} nm")
            st.metric("Charge", f"{st.session_state.design.get('Charge', -5):.1f} mV")
        
        with col3:
            st.metric("Encapsulation", f"{st.session_state.design.get('Encapsulation', 70):.1f}%")
            st.metric("Ligand", st.session_state.design.get('Ligand', 'None'))
        
        with col4:
            st.metric("PDI", f"{st.session_state.design.get('PDI', 0.15):.2f}")
            st.metric("Stability", f"{st.session_state.design.get('Stability', 85):.0f}%")
    
    st.markdown("---")
    
    # Simulation parameters
    st.subheader("⚙️ Simulation Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        duration = st.number_input(
            "Simulation Duration (hours)",
            min_value=12,
            max_value=168,
            value=48,
            step=6,
            help="Total time to simulate (1 week = 168 hours)"
        )
    
    with col2:
        time_step = st.select_slider(
            "Time Resolution",
            options=[0.05, 0.1, 0.25, 0.5, 1.0],
            value=0.1,
            format_func=lambda x: f"{x} hours",
            help="Smaller values = smoother curves but slower computation"
        )
    
    st.markdown("---")
    
    # Run simulation button
    col_run1, col_run2, col_run3 = st.columns([1, 1, 1])
    
    with col_run2:
        if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
            with st.spinner("Running two-compartment PK model..."):
                # Get PK parameters from design or use defaults
                dose = st.session_state.design.get('dose', 10.0)  # mg/kg
                kabs = st.session_state.design.get('kabs', 0.5)   # absorption rate
                kel = st.session_state.design.get('kel', 0.1)     # elimination rate
                k12 = st.session_state.design.get('k12', 0.3)     # central to peripheral transfer
                k21 = st.session_state.design.get('k21', 0.2)     # peripheral to central transfer
                
                # Run simulation
                time, C_plasma, C_tissue = two_compartment_model(
                    dose=dose,
                    kabs=kabs,
                    kel=kel,
                    k12=k12,
                    k21=k21,
                    duration=duration,
                    dt=time_step
                )
                
                # Calculate PK parameters
                pk_params = calculate_pk_parameters(time, C_plasma, C_tissue)
                
                # Store results
                st.session_state.simulation_results = {
                    'time': time,
                    'C_plasma': C_plasma,
                    'C_tissue': C_tissue,
                    'pk_params': pk_params
                }
                
                st.success("✅ Simulation completed successfully!")
    
    st.markdown("---")
    
    # Display results if available
    if st.session_state.simulation_results is not None:
        st.subheader("📈 Simulation Results")
        
        results = st.session_state.simulation_results
        pk_params = results['pk_params']
        
        # Key PK parameters
        st.markdown("### 🔑 Key Pharmacokinetic Parameters")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Plasma C_max",
                f"{pk_params['C_max_plasma']:.2f}",
                help="Peak concentration in plasma"
            )
            st.metric(
                "Plasma T_max",
                f"{pk_params['T_max_plasma']:.1f} h",
                help="Time to reach peak plasma concentration"
            )
        
        with col2:
            st.metric(
                "Tissue C_max",
                f"{pk_params['C_max_tissue']:.2f}",
                help="Peak concentration in tissue"
            )
            st.metric(
                "Tissue T_max",
                f"{pk_params['T_max_tissue']:.1f} h",
                help="Time to reach peak tissue concentration"
            )
        
        with col3:
            st.metric(
                "AUC Plasma",
                f"{pk_params['AUC_plasma']:.1f}",
                help="Total plasma exposure over time"
            )
            st.metric(
                "AUC Tissue",
                f"{pk_params['AUC_tissue']:.1f}",
                help="Total tissue exposure over time"
            )
        
        with col4:
            if pk_params['t_half_plasma'] is not None:
                st.metric(
                    "Plasma t₁/₂",
                    f"{pk_params['t_half_plasma']:.1f} h",
                    help="Plasma half-life"
                )
            else:
                st.metric("Plasma t₁/₂", "N/A", help="Cannot determine half-life")
            
            st.metric(
                "Tissue Accumulation",
                f"{pk_params['tissue_accumulation_ratio']:.2f}",
                help="AUC tissue / AUC plasma ratio"
            )
        
        st.markdown("---")
        
        # Visualization
        st.markdown("### 📊 Concentration-Time Profiles")
        
        fig = create_pk_plot(
            results['time'],
            results['C_plasma'],
            results['C_tissue'],
            pk_params,
            st.session_state.design
        )
        
        st.pyplot(fig)
        
        st.markdown("---")
        
        # Interpretation
        st.markdown("### 💡 Interpretation")
        
        interpretation_col1, interpretation_col2 = st.columns(2)
        
        with interpretation_col1:
            st.markdown("**Distribution Phase:**")
            if pk_params['T_max_tissue'] > pk_params['T_max_plasma']:
                st.info(f"✅ Tissue peak delayed by {pk_params['T_max_tissue'] - pk_params['T_max_plasma']:.1f} hours - typical distribution kinetics")
            else:
                st.warning("⚠️ Tissue peaks earlier than plasma - verify parameters")
            
            st.markdown("**Tissue Targeting:**")
            if pk_params['tissue_accumulation_ratio'] > 1.5:
                st.success(f"✅ Strong tissue accumulation (ratio: {pk_params['tissue_accumulation_ratio']:.2f})")
            elif pk_params['tissue_accumulation_ratio'] > 1.0:
                st.info(f"✓ Moderate tissue accumulation (ratio: {pk_params['tissue_accumulation_ratio']:.2f})")
            else:
                st.warning(f"⚠️ Limited tissue accumulation (ratio: {pk_params['tissue_accumulation_ratio']:.2f})")
        
        with interpretation_col2:
            st.markdown("**Plasma Clearance:**")
            if pk_params['t_half_plasma'] is not None:
                if pk_params['t_half_plasma'] < 6:
                    st.warning(f"⚠️ Rapid clearance (t₁/₂ = {pk_params['t_half_plasma']:.1f} h) - may need PEGylation")
                elif pk_params['t_half_plasma'] < 24:
                    st.info(f"✓ Moderate circulation time (t₁/₂ = {pk_params['t_half_plasma']:.1f} h)")
                else:
                    st.success(f"✅ Extended circulation (t₁/₂ = {pk_params['t_half_plasma']:.1f} h)")
            
            st.markdown("**Peak Concentration:**")
            if pk_params['C_max_plasma'] > 3 * pk_params['C_max_tissue']:
                st.info("High plasma exposure - consider dose adjustment")
            elif pk_params['C_max_tissue'] > pk_params['C_max_plasma']:
                st.success("Favorable tissue targeting profile")
        
        st.markdown("---")
        
        # Download options
        st.markdown("### 💾 Export Data")
        
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        
        with col_dl1:
            # Export concentration data as CSV
            import pandas as pd
            
            df_results = pd.DataFrame({
                'Time (h)': results['time'],
                'Plasma Concentration': results['C_plasma'],
                'Tissue Concentration': results['C_tissue']
            })
            
            csv_data = df_results.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Concentration Data (CSV)",
                data=csv_data,
                file_name=f"{st.session_state.design.get('Material', 'design')}_pk_data.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_dl2:
            # Export PK parameters
            df_params = pd.DataFrame([pk_params])
            csv_params = df_params.to_csv(index=False)
            
            st.download_button(
                label="📥 Download PK Parameters (CSV)",
                data=csv_params,
                file_name=f"{st.session_state.design.get('Material', 'design')}_pk_params.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_dl3:
            # Export plot
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            
            st.download_button(
                label="📥 Download Plot (PNG)",
                data=buf,
                file_name=f"{st.session_state.design.get('Material', 'design')}_pk_plot.png",
                mime="image/png",
                use_container_width=True
            )
        
        # Add PDF report download button
        st.markdown("")
        st.markdown("### 📄 Generate Report")
        
        col_pdf1, col_pdf2 = st.columns([1, 2])
        
        with col_pdf1:
            if st.button("📋 Generate PDF Report", type="primary", use_container_width=True):
                with st.spinner("Creating PDF report..."):
                    try:
                        pdf_buffer = generate_pdf_report(
                            st.session_state.design,
                            results['pk_params'],
                            results,
                            fig
                        )
                        st.session_state.pdf_report = pdf_buffer
                        st.success("✅ PDF report created!")
                    except Exception as e:
                        st.error(f"Error generating PDF: {str(e)}")
        
        with col_pdf2:
            if st.session_state.pdf_report:
                st.download_button(
                    label="📥 Download PDF Report",
                    data=st.session_state.pdf_report,
                    file_name=f"{st.session_state.design.get('Material', 'design')}_simulation_report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.info("👆 Click **Generate PDF Report** to create the report first")
    
    else:
        st.info("👆 Click **Run Simulation** to generate pharmacokinetic profiles")
        
        # Display sample information
        with st.expander("ℹ️ About Two-Compartment PK Model"):
            st.markdown("""
            ### Model Description
            
            The **two-compartment pharmacokinetic model** simulates drug distribution in the body:
            
            **Central Compartment (Plasma):**
            - Represents blood/plasma
            - Rapid equilibration
            - Site of elimination
            
            **Peripheral Compartment (Tissue):**
            - Represents target tissue or organs
            - Slower equilibration
            - Site of therapeutic action
            
            ### Key Parameters
            
            - **k_abs**: Absorption rate from administration site
            - **k_el**: Elimination rate (metabolism + excretion)
            - **k_12**: Transfer rate from plasma to tissue
            - **k_21**: Transfer rate from tissue back to plasma
            
            ### Interpretation
            
            - **High AUC_tissue/AUC_plasma**: Good tissue targeting
            - **Long t₁/₂**: Extended circulation (stealth effect)
            - **Early T_max_tissue**: Rapid tissue accumulation
            
            This model helps predict:
            - ✅ Optimal dosing regimens
            - ✅ Tissue accumulation kinetics
            - ✅ Clearance and circulation time
            - ✅ Need for PEGylation or surface modification
            """)
