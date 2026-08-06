"""
Nanoparticle Design Page
"""

import streamlit as st
import sys
from pathlib import Path

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent))
from utils.design_scorer import DesignScorer

def show():
    """Display nanoparticle design interface"""
    st.title("🔬 Design Nanoparticle")
    st.markdown("Customize your nanoparticle formulation with precise parameter control")
    
    st.markdown("---")
    
    # Design parameters in columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Basic Properties")
        
        # Store name in session (not used in design dict for simulation)
        design_name = st.text_input(
            "Formulation Name",
            st.session_state.design.get('FormulationName', ''),
            help="Unique identifier for your nanoparticle design"
        )
        if design_name:
            st.session_state.design['FormulationName'] = design_name
        
        st.session_state.design['Material'] = st.selectbox(
            "Nanoparticle Type",
            [
                "Lipid Nanoparticle (LNP)",
                "Gold Nanoparticle (AuNP)",
                "Polymeric Nanoparticle (PLGA)",
                "Silica Nanoparticle (MSN)",
                "Liposome",
                "Quantum Dot (QD)",
                "Carbon Nanotube (CNT)",
                "Dendrimer",
                "Metal-Organic Framework (MOF)",
                "Exosome"
            ],
            index=0 if st.session_state.design.get('Material', 'Lipid NP') == "Lipid Nanoparticle" else 
                  [i for i, m in enumerate(["Lipid Nanoparticle (LNP)", "Gold Nanoparticle (AuNP)", "Polymeric Nanoparticle (PLGA)", "Silica Nanoparticle (MSN)", "Liposome", "Quantum Dot (QD)", "Carbon Nanotube (CNT)", "Dendrimer", "Metal-Organic Framework (MOF)", "Exosome"]) if st.session_state.design.get('Material', 'Lipid NP') in m][0] if any(st.session_state.design.get('Material', 'Lipid NP') in m for m in ["Lipid Nanoparticle (LNP)", "Gold Nanoparticle (AuNP)", "Polymeric Nanoparticle (PLGA)", "Silica Nanoparticle (MSN)", "Liposome", "Quantum Dot (QD)", "Carbon Nanotube (CNT)", "Dendrimer", "Metal-Organic Framework (MOF)", "Exosome"]) else 0,
            help="Select the base nanoparticle platform"
        )
        
        st.session_state.design['Size'] = st.number_input(
            "Size (nm)",
            min_value=1.0,
            max_value=500.0,
            value=float(st.session_state.design.get('Size', 100)),
            step=1.0,
            format="%.1f",
            help="Hydrodynamic diameter - affects biodistribution, clearance, and EPR effect"
        )
        
        st.session_state.design['Charge'] = st.number_input(
            "Surface Charge (mV)",
            min_value=-50.0,
            max_value=50.0,
            value=float(st.session_state.design.get('Charge', -5)),
            step=1.0,
            format="%.1f",
            help="Zeta potential - affects stability, cell uptake, and toxicity"
        )
        
        st.session_state.design['PDI'] = st.number_input(
            "Polydispersity Index (PDI)",
            min_value=0.01,
            max_value=0.50,
            value=float(st.session_state.design.get('PDI', 0.15)),
            step=0.01,
            format="%.3f",
            help="Particle size uniformity - lower values indicate more uniform distribution"
        )
    
    with col2:
        st.subheader("Surface Modification & Payload")
        
        st.session_state.design['Ligand'] = st.selectbox(
            "Surface Ligand",
            [
                "PEG (Polyethylene Glycol)",
                "PEG2000",
                "Cholesterol",
                "Citrate",
                "Thiol-PEG",
                "Antibody (mAb)",
                "RGD Peptide",
                "Folate",
                "Transferrin",
                "Hyaluronic Acid",
                "None"
            ],
            index=[
                "PEG (Polyethylene Glycol)", "PEG2000", "Cholesterol", "Citrate",
                "Thiol-PEG", "Antibody (mAb)", "RGD Peptide", "Folate",
                "Transferrin", "Hyaluronic Acid", "None"
            ].index("PEG (Polyethylene Glycol)") if "PEG" in st.session_state.design.get('Ligand', 'GalNAc') else 0,
            help="Surface coating for stealth effect and targeting"
        )
        
        # Store payload name (not in core design dict for simulation)
        payload_name = st.selectbox(
            "Therapeutic Payload",
            [
                "mRNA",
                "siRNA",
                "DNA (plasmid)",
                "Small molecule drug",
                "Protein/Peptide",
                "Antibody",
                "CRISPR-Cas9 RNP",
                "Imaging agent",
                "Combination (drug + RNA)",
                "None"
            ],
            index=[
                "mRNA", "siRNA", "DNA (plasmid)", "Small molecule drug",
                "Protein/Peptide", "Antibody", "CRISPR-Cas9 RNP",
                "Imaging agent", "Combination (drug + RNA)", "None"
            ].index(st.session_state.design.get('payload_type', 'mRNA')) if st.session_state.design.get('payload_type', 'mRNA') in [
                "mRNA", "siRNA", "DNA (plasmid)", "Small molecule drug",
                "Protein/Peptide", "Antibody", "CRISPR-Cas9 RNP",
                "Imaging agent", "Combination (drug + RNA)", "None"
            ] else 0,
            help="Therapeutic or diagnostic cargo"
        )
        if payload_name:
            st.session_state.design['payload_type'] = payload_name
        
        st.session_state.design['Encapsulation'] = st.number_input(
            "Payload Loading (%w/w)",
            min_value=0.1,
            max_value=100.0,
            value=float(st.session_state.design.get('Encapsulation', 70)),
            step=0.1,
            format="%.1f",
            help="Weight percentage of payload relative to total nanoparticle"
        )
        
        st.session_state.design['Target'] = st.selectbox(
            "Biological Target",
            [
                "Tumor Tissue (Solid)",
                "Liver Hepatocytes",
                "Brain (Blood-Brain Barrier)",
                "Lung Endothelium",
                "Kidney Glomeruli",
                "Spleen (RES)",
                "Lymph Nodes",
                "Inflamed Tissue",
                "Cardiovascular Plaques",
                "Bone Marrow",
                "Skin (Dermal)",
                "Ocular Tissue (Eye)"
            ],
            index=[
                "Tumor Tissue (Solid)", "Liver Hepatocytes", "Brain (Blood-Brain Barrier)",
                "Lung Endothelium", "Kidney Glomeruli", "Spleen (RES)",
                "Lymph Nodes", "Inflamed Tissue", "Cardiovascular Plaques",
                "Bone Marrow", "Skin (Dermal)", "Ocular Tissue (Eye)"
            ].index(st.session_state.design['target']) if st.session_state.design['target'] in [
                "Tumor Tissue (Solid)", "Liver Hepatocytes", "Brain (Blood-Brain Barrier)",
                "Lung Endothelium", "Kidney Glomeruli", "Spleen (RES)",
                "Lymph Nodes", "Inflamed Tissue", "Cardiovascular Plaques",
                "Bone Marrow", "Skin (Dermal)", "Ocular Tissue (Eye)"
            ] else 0,
            help="Intended tissue or cell target"
        )
        
        st.session_state.design['dose'] = st.number_input(
            "Dose (mg/kg)",
            min_value=0.1,
            max_value=100.0,
            value=float(st.session_state.design['dose']),
            step=0.1,
            help="Intended dosage per kilogram body weight"
        )
    
    st.markdown("---")
    
    # Pharmacokinetic parameters
    st.subheader("⚗️ Pharmacokinetic Parameters")
    st.markdown("Adjust absorption, elimination, and distribution rates for PK/PD simulation")
    
    col3, col4, col5, col6 = st.columns(4)
    
    with col3:
        st.session_state.design['kabs'] = st.number_input(
            "k_abs (h⁻¹)",
            min_value=0.01,
            max_value=5.0,
            value=float(st.session_state.design['kabs']),
            step=0.01,
            help="Absorption rate constant"
        )
    
    with col4:
        st.session_state.design['kel'] = st.number_input(
            "k_el (h⁻¹)",
            min_value=0.001,
            max_value=2.0,
            value=float(st.session_state.design['kel']),
            step=0.001,
            help="Elimination rate constant"
        )
    
    with col5:
        st.session_state.design['k12'] = st.number_input(
            "k_12 (h⁻¹)",
            min_value=0.01,
            max_value=2.0,
            value=float(st.session_state.design['k12']),
            step=0.01,
            help="Transfer rate: plasma → tissue"
        )
    
    with col6:
        st.session_state.design['k21'] = st.number_input(
            "k_21 (h⁻¹)",
            min_value=0.01,
            max_value=2.0,
            value=float(st.session_state.design['k21']),
            step=0.01,
            help="Transfer rate: tissue → plasma"
        )
    
    st.markdown("---")
    
    # Summary and actions
    st.subheader("📋 Design Summary")
    
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    
    with summary_col1:
        st.metric("Formulation", st.session_state.design['name'])
        st.metric("Material", st.session_state.design['material'].split('(')[0].strip())
        st.metric("Size", f"{st.session_state.design['size']:.1f} nm")
    
    with summary_col2:
        st.metric("Charge", f"{st.session_state.design['charge']:.1f} mV")
        st.metric("Payload", st.session_state.design['payload'])
        st.metric("Loading", f"{st.session_state.design['payload_amount']:.1f}%")
    
    with summary_col3:
        st.metric("Target", st.session_state.design['target'])
        st.metric("Dose", f"{st.session_state.design['dose']:.1f} mg/kg")
        st.metric("PDI", f"{st.session_state.design['pdi']:.2f}")
    
    st.markdown("---")
    
    # Suitability Score Meter
    st.markdown("### 🎯 Design Suitability Score")
    
    scorer = DesignScorer()
    scores = scorer.calculate_overall_score(st.session_state.design)
    
    # Display overall score with color-coded metric
    overall_score = scores['overall']
    
    # Determine color and rating
    if overall_score >= 85:
        color = "#00C851"  # Green
        rating = "Excellent"
        emoji = "🟢"
    elif overall_score >= 70:
        color = "#33B5E5"  # Blue
        rating = "Good"
        emoji = "🔵"
    elif overall_score >= 55:
        color = "#FFB300"  # Amber
        rating = "Fair"
        emoji = "🟡"
    else:
        color = "#FF4444"  # Red
        rating = "Needs Improvement"
        emoji = "🔴"
    
    # Display score meter
    col_score1, col_score2, col_score3 = st.columns([2, 1, 1])
    
    with col_score1:
        st.markdown(f"""
        <div style="padding: 1.5rem; border-radius: 10px; background: linear-gradient(135deg, {color}22 0%, {color}11 100%); border-left: 5px solid {color};">
            <h1 style="margin: 0; color: {color}; font-size: 3rem;">{emoji} {overall_score}/100</h1>
            <p style="margin: 0.5rem 0 0 0; font-size: 1.2rem; color: #666;">Overall Suitability: <strong>{rating}</strong></p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_score2:
        st.metric("Size Match", f"{scores['size']}/100", 
                 delta="Optimal" if scores['size'] >= 80 else "Check",
                 delta_color="normal" if scores['size'] >= 80 else "inverse")
        st.metric("Material-Payload", f"{scores['material']}/100",
                 delta="Good" if scores['material'] >= 70 else "Review",
                 delta_color="normal" if scores['material'] >= 70 else "inverse")
    
    with col_score3:
        st.metric("Charge Match", f"{scores['charge']}/100",
                 delta="Optimal" if scores['charge'] >= 80 else "Check",
                 delta_color="normal" if scores['charge'] >= 80 else "inverse")
        st.metric("Ligand-Target", f"{scores['ligand']}/100",
                 delta="Good" if scores['ligand'] >= 70 else "Review",
                 delta_color="normal" if scores['ligand'] >= 70 else "inverse")
    
    # Detailed breakdown
    with st.expander("📊 Detailed Score Breakdown"):
        col_d1, col_d2, col_d3 = st.columns(3)
        
        with col_d1:
            st.metric("Size Optimization", f"{scores['size']}/100")
            st.progress(scores['size'] / 100)
            
            st.metric("Charge Optimization", f"{scores['charge']}/100")
            st.progress(scores['charge'] / 100)
        
        with col_d2:
            st.metric("PDI Quality", f"{scores['pdi']}/100")
            st.progress(scores['pdi'] / 100)
            
            st.metric("Material-Payload Fit", f"{scores['material']}/100")
            st.progress(scores['material'] / 100)
        
        with col_d3:
            st.metric("Ligand-Target Fit", f"{scores['ligand']}/100")
            st.progress(scores['ligand'] / 100)
            
            st.metric("Payload Loading", f"{scores['loading']}/100")
            st.progress(scores['loading'] / 100)
    
    # Recommendations
    recommendations = scorer.get_recommendations(scores, st.session_state.design)
    
    if recommendations:
        st.markdown("### 💡 Recommendations")
        for rec in recommendations:
            if "✅" in rec:
                st.success(rec)
            else:
                st.warning(rec)
    
    # Scoring System Documentation
    with st.expander("📖 How is the Score Calculated? - View Detailed Explanation"):
        try:
            with open("docs/scoring_system.md", "r", encoding="utf-8") as f:
                scoring_doc = f.read()
            st.markdown(scoring_doc)
        except FileNotFoundError:
            st.error("Scoring system documentation not found.")
    
    st.markdown("---")
    
    # Action buttons
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        if st.button("🔄 Reset to Defaults", use_container_width=True):
            st.session_state.design = {
                'name': 'NP-001',
                'material': 'Lipid Nanoparticle',
                'size': 100.0,
                'charge': -10.0,
                'ligand': 'PEG',
                'payload': 'mRNA',
                'payload_amount': 50.0,
                'target': 'Tumor Tissue',
                'dose': 5.0,
                'pdi': 0.15,
                'kabs': 0.5,
                'kel': 0.1,
                'k12': 0.3,
                'k21': 0.2
            }
            st.rerun()
    
    with col_b:
        if st.button("📊 Run Simulation", type="primary", use_container_width=True):
            st.success("✅ Design saved! Navigate to **Delivery Simulation** to run PK/PD analysis")
            st.balloons()
    
    with col_c:
        if st.button("⚠️ Check Safety", use_container_width=True):
            st.success("✅ Design saved! Navigate to **Toxicity & Safety** for risk assessment")
    
    st.info("💡 **Next Steps:** Run delivery simulation to visualize pharmacokinetics, or check toxicity profile")
