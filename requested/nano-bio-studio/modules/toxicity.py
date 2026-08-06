"""
Toxicity and Safety Assessment Page
"""

import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.toxicity_model import calculate_overall_safety_score

def create_safety_radar_chart(safety_assessment: dict) -> plt.Figure:
    """Create radar chart for safety assessment"""
    
    individual_scores = safety_assessment['individual_scores']
    
    categories = list(individual_scores.keys())
    scores = [individual_scores[cat]['score'] for cat in categories]
    
    # Number of variables
    N = len(categories)
    
    # Compute angle for each axis
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    scores += scores[:1]  # Complete the circle
    angles += angles[:1]
    
    # Initialize the plot
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    # Draw the outline
    ax.plot(angles, scores, 'o-', linewidth=2, color='#E74C3C', label='Risk Score')
    ax.fill(angles, scores, alpha=0.25, color='#E74C3C')
    
    # Add reference circles
    ax.plot(angles, [3] * len(angles), '--', linewidth=1, color='green', alpha=0.5, label='Low Risk Threshold')
    ax.plot(angles, [5] * len(angles), '--', linewidth=1, color='orange', alpha=0.5, label='Moderate Risk Threshold')
    ax.plot(angles, [7] * len(angles), '--', linewidth=1, color='red', alpha=0.5, label='High Risk Threshold')
    
    # Fix axis to go in the right order and start at 12 o'clock
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    # Draw axis labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([cat.capitalize() for cat in categories], size=11)
    
    # Set y-axis limits
    ax.set_ylim(0, 10)
    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(['2', '4', '6', '8', '10'], size=9)
    
    # Add legend
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), framealpha=0.9)
    
    # Add title
    plt.title('Safety Risk Profile', size=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    return fig

def show():
    """Display toxicity and safety assessment interface"""
    st.title("⚠️ Toxicity & Safety Assessment")
    st.markdown("Evaluate potential safety risks based on physicochemical properties")
    
    st.markdown("---")
    
    # Display current design
    with st.expander("📋 Current Design Parameters", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Formulation", st.session_state.design['name'])
            st.metric("Material", st.session_state.design['material'].split('(')[0].strip())
        
        with col2:
            st.metric("Size", f"{st.session_state.design['size']:.1f} nm")
            st.metric("Charge", f"{st.session_state.design['charge']:.1f} mV")
        
        with col3:
            st.metric("Ligand", st.session_state.design['ligand'].split('(')[0].strip())
            st.metric("Payload", st.session_state.design['payload'])
        
        with col4:
            st.metric("Dose", f"{st.session_state.design['dose']:.1f} mg/kg")
            st.metric("PDI", f"{st.session_state.design['pdi']:.2f}")
    
    st.markdown("---")
    
    # Run assessment
    col_assess1, col_assess2, col_assess3 = st.columns([1, 1, 1])
    
    with col_assess2:
        if st.button("🔍 Run Safety Assessment", type="primary", use_container_width=True):
            with st.spinner("Analyzing safety profile..."):
                safety_assessment = calculate_overall_safety_score(st.session_state.design)
                st.session_state.safety_assessment = safety_assessment
                st.success("✅ Safety assessment completed!")
    
    st.markdown("---")
    
    # Display results if available
    if hasattr(st.session_state, 'safety_assessment') and st.session_state.safety_assessment is not None:
        assessment = st.session_state.safety_assessment
        
        # Overall risk score
        st.subheader("🎯 Overall Safety Score")
        
        col_score1, col_score2, col_score3 = st.columns([1, 2, 1])
        
        with col_score2:
            # Create color-coded display
            score = assessment['overall_score']
            risk_level = assessment['risk_level']
            
            if risk_level == "LOW":
                st.success(f"### Risk Level: {risk_level}")
                st.metric("Safety Score", f"{score:.2f} / 10", "Good", delta_color="inverse")
            elif risk_level == "MODERATE":
                st.warning(f"### Risk Level: {risk_level}")
                st.metric("Safety Score", f"{score:.2f} / 10", "Acceptable", delta_color="off")
            elif risk_level == "HIGH":
                st.error(f"### Risk Level: {risk_level}")
                st.metric("Safety Score", f"{score:.2f} / 10", "Concerning", delta_color="normal")
            else:  # VERY HIGH
                st.error(f"### Risk Level: {risk_level}")
                st.metric("Safety Score", f"{score:.2f} / 10", "Critical", delta_color="normal")
            
            st.info(f"**Recommendation:** {assessment['recommendation']}")
        
        st.markdown("---")
        
        # Detailed breakdown
        st.subheader("📊 Risk Factor Breakdown")
        
        individual_scores = assessment['individual_scores']
        
        # Create two columns for display
        col_left, col_right = st.columns(2)
        
        factors_left = ['size', 'charge', 'dose', 'pdi']
        factors_right = ['ligand', 'payload', 'material']
        
        with col_left:
            for factor in factors_left:
                score_data = individual_scores[factor]
                score_val = score_data['score']
                
                # Color code based on score
                if score_val < 3:
                    st.success(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                elif score_val < 5:
                    st.info(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                elif score_val < 7:
                    st.warning(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                else:
                    st.error(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                
                st.caption(score_data['explanation'])
                st.markdown("---")
        
        with col_right:
            for factor in factors_right:
                score_data = individual_scores[factor]
                score_val = score_data['score']
                
                if score_val < 3:
                    st.success(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                elif score_val < 5:
                    st.info(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                elif score_val < 7:
                    st.warning(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                else:
                    st.error(f"**{factor.capitalize()}**: {score_val:.1f}/10")
                
                st.caption(score_data['explanation'])
                st.markdown("---")
        
        # Radar chart
        st.subheader("📈 Safety Risk Profile (Radar Chart)")
        
        fig = create_safety_radar_chart(assessment)
        st.pyplot(fig)
        
        st.markdown("---")
        
        # Recommendations
        st.subheader("💡 Recommendations for Risk Mitigation")
        
        recommendations = []
        
        # Generate specific recommendations
        if individual_scores['charge']['score'] > 5:
            recommendations.append("**Charge**: Consider PEGylation or surface modification to reduce positive charge")
        
        if individual_scores['size']['score'] > 5:
            recommendations.append("**Size**: Optimize size to 20-100 nm range for better EPR effect and reduced clearance")
        
        if individual_scores['dose']['score'] > 5:
            recommendations.append("**Dose**: Consider dose reduction or fractionated dosing regimen")
        
        if individual_scores['pdi']['score'] > 5:
            recommendations.append("**PDI**: Improve synthesis protocol to reduce polydispersity (target PDI <0.2)")
        
        if individual_scores['ligand']['score'] > 5:
            recommendations.append("**Ligand**: Add PEG coating for stealth effect and reduced immunogenicity")
        
        if individual_scores['payload']['score'] > 5:
            recommendations.append("**Payload**: Reduce loading or consider alternative payload formulation")
        
        if individual_scores['material']['score'] > 5:
            recommendations.append("**Material**: Consider switching to more biocompatible material (e.g., lipids, PLGA)")
        
        if recommendations:
            for rec in recommendations:
                st.markdown(f"• {rec}")
        else:
            st.success("✅ No major risk factors identified. Current design has acceptable safety profile.")
        
        st.markdown("---")
        
        # Required studies
        st.subheader("🧪 Recommended Preclinical Studies")
        
        study_col1, study_col2 = st.columns(2)
        
        with study_col1:
            st.markdown("**In Vitro Studies:**")
            st.markdown("- [ ] Cell viability (MTT/MTS assay)")
            st.markdown("- [ ] Hemolysis test")
            st.markdown("- [ ] Complement activation")
            st.markdown("- [ ] Cytokine release assay")
            st.markdown("- [ ] Genotoxicity (Ames test)")
        
        with study_col2:
            st.markdown("**In Vivo Studies:**")
            st.markdown("- [ ] Acute toxicity (single dose)")
            st.markdown("- [ ] Repeat-dose toxicity")
            st.markdown("- [ ] Biodistribution study")
            st.markdown("- [ ] Histopathology")
            st.markdown("- [ ] Clearance and excretion")
        
        if assessment['overall_score'] > 6:
            st.error("⚠️ **High-risk formulation requires extensive safety testing before human use**")
        elif assessment['overall_score'] > 4:
            st.warning("⚠️ **Moderate-risk formulation requires standard preclinical safety package**")
        else:
            st.info("✅ **Low-risk formulation - standard safety testing recommended**")
        
        st.markdown("---")
        
        # Export options
        st.subheader("💾 Export Safety Report")
        
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            # Create safety report text
            report_text = f"""
NANOBIO STUDIO - SAFETY ASSESSMENT REPORT
==========================================

Formulation: {st.session_state.design['name']}
Assessment Date: {st.session_state.design.get('date', 'N/A')}

OVERALL SAFETY SCORE: {assessment['overall_score']:.2f} / 10
RISK LEVEL: {assessment['risk_level']}

RECOMMENDATION:
{assessment['recommendation']}

DETAILED RISK ANALYSIS:
-----------------------

1. Size Risk: {individual_scores['size']['score']:.1f}/10
   {individual_scores['size']['explanation']}

2. Charge Risk: {individual_scores['charge']['score']:.1f}/10
   {individual_scores['charge']['explanation']}

3. Dose Risk: {individual_scores['dose']['score']:.1f}/10
   {individual_scores['dose']['explanation']}

4. PDI Risk: {individual_scores['pdi']['score']:.1f}/10
   {individual_scores['pdi']['explanation']}

5. Ligand Risk: {individual_scores['ligand']['score']:.1f}/10
   {individual_scores['ligand']['explanation']}

6. Payload Risk: {individual_scores['payload']['score']:.1f}/10
   {individual_scores['payload']['explanation']}

7. Material Risk: {individual_scores['material']['score']:.1f}/10
   {individual_scores['material']['explanation']}

DESIGN PARAMETERS:
------------------
Material: {st.session_state.design['material']}
Size: {st.session_state.design['size']} nm
Charge: {st.session_state.design['charge']} mV
PDI: {st.session_state.design['pdi']}
Ligand: {st.session_state.design['ligand']}
Payload: {st.session_state.design['payload']}
Loading: {st.session_state.design['payload_amount']}%
Dose: {st.session_state.design['dose']} mg/kg
Target: {st.session_state.design['target']}

RISK MITIGATION RECOMMENDATIONS:
---------------------------------
{"".join([f"\n{rec}" for rec in recommendations]) if recommendations else "\nNo major concerns identified."}

---
Generated by NanoBio Studio
Experts Group FZE
"""
            
            st.download_button(
                label="📥 Download Safety Report (TXT)",
                data=report_text,
                file_name=f"{st.session_state.design['name']}_safety_report.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col_export2:
            # Export radar chart
            from io import BytesIO
            
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            
            st.download_button(
                label="📥 Download Risk Chart (PNG)",
                data=buf,
                file_name=f"{st.session_state.design['name']}_risk_chart.png",
                mime="image/png",
                use_container_width=True
            )
    
    else:
        st.info("👆 Click **Run Safety Assessment** to evaluate toxicity risks")
        
        with st.expander("ℹ️ About Safety Assessment"):
            st.markdown("""
            ### Heuristic Risk Scoring System
            
            This module evaluates potential safety risks based on established nanotoxicology principles:
            
            **Risk Factors Evaluated:**
            
            1. **Size** - Affects biodistribution, clearance, and barrier penetration
            2. **Surface Charge** - Impacts cell interaction, protein binding, and hemolysis
            3. **Dose** - Direct correlation with systemic exposure and toxicity
            4. **Polydispersity (PDI)** - Affects reproducibility and predictability
            5. **Surface Ligand** - Influences immunogenicity and targeting
            6. **Payload** - Inherent toxicity and off-target effects
            7. **Material** - Biocompatibility and degradation profile
            
            **Risk Levels:**
            - **LOW (<3)**: Favorable safety profile
            - **MODERATE (3-5)**: Acceptable with monitoring
            - **HIGH (5-7)**: Significant concerns
            - **VERY HIGH (>7)**: Major safety issues
            
            **Important Notes:**
            - This is a screening tool based on physicochemical properties
            - Actual toxicity must be validated experimentally
            - Regulatory approval requires comprehensive preclinical studies
            - Consider synergistic effects not captured in individual scores
            
            **References:**
            - FDA Guidance on Nanotechnology Products
            - ISO/TR 13014:2012 - Nanotoxicology
            - EMA Reflection Paper on Nanotechnology
            """)
    
    st.markdown("---")
    st.caption("⚠️ **Disclaimer**: This assessment is for research and educational purposes. Actual safety must be confirmed through proper preclinical and clinical studies.")
