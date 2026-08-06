"""
Design Parameters - ⏸️ Middle of 3-Step Workflow (Step 2 of 3)
Configure nanoparticle design parameters with real-time scoring
"""
import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import sys
from pathlib import Path
import plotly.graph_objects as go
import importlib

from pathlib import Path
import sys

# Ensure parent directory is on path for module imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scoring import compute_impact, get_recommendations, overall_score_from_impact
from data.drug_material_mapping import (
    get_recommended_materials,
    get_recommendation_level,
    get_material_info,
    order_materials_by_recommendation,
    AVAILABLE_MATERIALS
)

# Import new critical parameter modules
from data.surface_functionalization_mapping import (
    get_targeting_options_for_disease,
    get_targeting_options_for_drug,
    get_ligand_details,
    get_combined_targeting_recommendation,
    get_all_ligands
)

from data.immunogenicity_pegylation_mapping import (
    get_material_immunogenicity_profile,
    get_disease_immunogenicity_requirements,
    get_drug_immunogenicity_considerations,
    get_peg_recommendation,
    get_all_materials_ranked_by_immunogenicity
)

from data.stability_profile_mapping import (
    get_material_stability_profile,
    get_drug_stability_requirements,
    get_combined_stability_recommendation,
    get_stability_testing_protocol,
    get_shelf_life_estimate
)

from data.clearance_mechanism_mapping import (
    get_clearance_by_size,
    get_clearance_by_charge,
    get_disease_clearance_optimization,
    get_material_clearance_profile,
    get_predicted_organ_accumulation,
    get_clearance_optimization_for_disease_drug_material,
    DISEASE_CLEARANCE_PREFERENCES
)

# Force reload to ensure latest version is used
import core.scoring
importlib.reload(core.scoring)
from core.scoring import compute_impact, get_recommendations, overall_score_from_impact

# ============================================================
# SPRINT 1: Import blood safety & charge predictors
# ============================================================
from components.osmolarity_calculator import calculate_osmolarity, display_osmolarity_widget
from components.blood_safety_assessor import calculate_hemolysis_risk, display_hemolysis_widget
from components.charge_predictors import (
    predict_improved_blood_half_life,
    calculate_isoelectric_point,
    display_halflife_widget,
    display_pI_widget
)

# ============================================================
# SPRINT 2: Import cellular & tumor predictors
# ============================================================
from components.cellular_uptake_predictor import predict_cellular_uptake, display_cellular_uptake_widget
from components.intracellular_trafficking_predictor import predict_intracellular_trafficking, display_intracellular_trafficking_widget
from components.payload_release_predictor import predict_payload_release, display_payload_release_widget
from components.tumor_microenvironment_predictor import predict_tumor_microenvironment_interactions, display_tumor_microenvironment_widget
from components.immune_response_predictor import predict_immune_response, display_immune_response_widget

# ============================================================
# SPRINT 3: Import research grade predictors
# ============================================================
from components.publication_readiness_predictor import predict_publication_readiness, display_publication_readiness_widget
from components.manufacturing_scalability_predictor import predict_manufacturing_scalability, display_manufacturing_scalability_widget
from components.stability_storage_predictor import predict_stability_storage, display_stability_storage_widget
from components.batch_quality_control_predictor import predict_batch_quality_control, display_batch_quality_control_widget
from components.environmental_impact_predictor import predict_environmental_impact, display_environmental_impact_widget
from components.reproducibility_assessment_predictor import predict_reproducibility_assessment, display_reproducibility_assessment_widget
from components.cost_analysis_predictor import predict_cost_analysis, display_cost_analysis_widget
from components.literature_comparison_predictor import predict_literature_comparison, display_literature_comparison_widget
from components.intellectual_property_predictor import predict_intellectual_property, display_intellectual_property_widget

st.set_page_config(page_title="Design Parameters", layout="wide")

# ============================================================
# SESSION RESTORATION & TIMEOUT CHECK
# ============================================================

from streamlit_auth import restore_session_from_persistent, check_session_timeout, StreamlitAuth

# Initialize session state
StreamlitAuth.init_session_state()

# SECURITY CONTAINMENT (2026-07-30): URL-supplied session tokens are no longer
# accepted. Honouring `?session_token=...` let anyone authenticate by supplying a
# token, and tokens are predictable (`token_{username}_{unix_seconds}`).
# Stale values are cleared rather than trusted.
if "session_token" in st.query_params:
    st.query_params.clear()

# Check if user is logged in or session is valid
logged_in = st.session_state.get("logged_in") or st.session_state.get("authenticated")

if not logged_in:
    st.warning("⚠️ Please log in first")
    st.info("You need to be logged in to access this page.")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔐 Go to Login", type="primary", use_container_width=True):
            st.query_params.clear()
            st.switch_page("Login.py")
    
    st.stop()

# Check for session timeout
if st.session_state.get("session_token"):
    token = st.session_state.session_token
    if not check_session_timeout(token):
        st.warning("⏰ Your session has expired due to inactivity (30 minutes). Please log in again.")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔐 Go to Login", type="primary", use_container_width=True):
                st.query_params.clear()
                st.switch_page("Login.py")
        
        StreamlitAuth.logout()
        st.stop()

# Check if disease was selected
if not st.session_state.get("disease_selected"):
    st.warning("⚠️ Please select a disease first")
    st.info("Redirecting to disease selection...")
    from streamlit_auth import switch_page_with_token
    switch_page_with_token("pages/0_Disease_Selection.py")

# Initialize design dictionary in session state
if "design" not in st.session_state:
    st.session_state.design = {
        "Material": "Lipid NP",
        "Target": "Liver Cells",
        "Size": 100,
        "PDI": 0.15,
        "HydrodynamicSize": 120,
        "Encapsulation": 85,
        "EncapsulationMethod": "Passive Loading",
        "Charge": -5,
        "SurfaceArea": 250,
        "Stability": 85,
        "DegradationTime": 30,
        "CrystallinityIndex": 65,
        "PorosityLevel": "Mesoporous (2-50nm)",
        "PoreSize": 5.0,
        "SurfaceCoating": ["PEG (Stealth)"],
        "CoatingThickness": 2.5,
        "FunctionalGroups": ["-COOH (Carboxyl)"],
        "Hydrophobicity": 1.5,
        "Ligand": "GalNAc",
        "LigandDensity": 60,
        "Receptor": "ASGPR",
        "ReceptorBinding": 10.0,
        "ReleaseProfile": "Sustained (1 week)",
        "ReleasePredictability": 85,
    }

d = st.session_state.design

st.title("🎨 Design Parameters")
st.caption("⏸️ Step 2 of 3: Configure nanoparticle design parameters")

# ============================================================
# IN VIVO SIMULATION CONTEXT
# ============================================================

with st.container():
    col_info1, col_info2, col_info3 = st.columns([1, 3, 1])
    with col_info2:
        st.info(
            "🧬 **IN VIVO SIMULATION MODE**\n\n"
            "The parameters you configure here will be used to simulate how your nanoparticle "
            "will behave **in the body** (in vivo environment). Each parameter affects:\n\n"
            "**Size & Charge** → Blood half-life, tissue penetration, clearance rate\n"
            "**Material & Surface** → Immune evasion, targeting specificity, biodegradation\n"
            "**Ligand & Payload** → Cellular uptake, intracellular trafficking, drug release\n\n"
            "✅ **Next Step:** Run simulation in Step 3 to evaluate in vivo performance"
        )

st.markdown("---")

# Workflow progress indicator
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("### 🟢 STEP 1 - START")
    st.info("Complete")
with col2:
    st.markdown("### ⏸️ STEP 2")
    st.success("✅ You are here")
with col3:
    st.markdown("### 🔴 STEP 3 - END")
    st.info("Next")

st.divider()

# ============================================================
# SIMPLE EXPLANATION FOR LAYMAN
# ============================================================

with st.expander("❓ What are Design Parameters? (Simple Explanation)", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🛠️ What are you designing?
        
        A **nanoparticle** is a tiny drug carrier. You need to decide:
        - How big should it be? (Size in nm)
        - What charge should it have? (Charge in mV)
        - What material? (Lipid, gold, polymer)
        - How much drug inside? (Encapsulation %)
        
        **Think of it like building a tiny medicine package.**
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 Why does each parameter matter?
        
        ✅ **Size** → Affects how it travels in the body  
        ✅ **Charge** → Controls where it sticks and how safe it is  
        ✅ **Material** → Determines cost and biocompatibility  
        ✅ **Drug Loading** → How much medicine gets delivered
        """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📊 What are the 4 tabs?
        
        **Tab 1: Core Properties**  
        Size, charge, encapsulation basics
        
        **Tab 2: Surface Chemistry**  
        Coating, hydrophobicity, crystal structure
        """)
    
    with col2:
        st.markdown("""
        **Tab 3: Targeting**  
        How to make it find the right cells
        
        **Tab 4: Scoring**  
        See real-time score & adjust weights
        """)
    
    st.success("**Your goal:** Find a design that's safe, effective, affordable, and works well for your target disease.")

st.divider()

# Show disease selection context
context_col1, context_col2 = st.columns(2)
with context_col1:
    st.info(f"""
    **Disease:** {st.session_state.get('selected_disease', 'Not selected')}
    
    **Drug:** {st.session_state.get('selected_drug', 'Not selected')}
    """)

with context_col2:
    st.info(f"""
    **HCC Subtype:** {st.session_state.get('hcc_subtype', 'N/A')}
    """)

st.divider()

# ============================================================
# TABS FOR DIFFERENT PARAMETER GROUPS
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["🧬 Core Properties", "🎨 Surface & Chemistry", "🎯 Targeting", "📊 Scoring", "🩸 Blood Safety (Sprint 1)", "💊 Cellular & Immune (Sprint 2)", "🚀 Research Grade (Sprint 3)"])

# Function to display gauge chart
def display_score_gauge(key="gauge"):
    """Display the real-time design scoring gauge"""
    impact = compute_impact(d)
    overall = overall_score_from_impact(impact)
    
    fig = go.Figure(data=[go.Indicator(
        mode="gauge+number+delta",
        value=overall,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Design Success Score"},
        delta={"reference": 80, "suffix": " vs target"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkblue"},
            "steps": [
                {"range": [0, 30], "color": "rgba(255, 100, 100, 0.3)"},
                {"range": [30, 60], "color": "rgba(255, 200, 0, 0.3)"},
                {"range": [60, 85], "color": "rgba(150, 255, 100, 0.3)"},
                {"range": [85, 100], "color": "rgba(100, 255, 100, 0.3)"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 85
            }
        }
    )])
    
    fig.update_layout(
        height=350,
        font={"size": 14},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig, use_container_width=True, key=key)
    with col2:
        st.markdown("### 📊 Score Metrics")
        st.metric("Overall Score", f"{overall:.1f}/100")
        st.metric("Delivery", f"{impact['Delivery']:.1f}/100")
        st.metric("Toxicity", f"{impact['Toxicity']:.1f}/10")
        st.metric("Cost Index", f"{impact['Cost']:.1f}/100")

# TAB 1: CORE PROPERTIES
with tab1:
    st.subheader("🧬 Core Material Properties")
    
    material_properties = {
        "Lipid NP": {"biodegradation": 7, "cost_base": 50, "density": 0.95},
        "PLGA": {"biodegradation": 30, "cost_base": 40, "density": 1.22},
        "Gold NP": {"biodegradation": 180, "cost_base": 80, "density": 19.3},
        "Silica NP": {"biodegradation": 365, "cost_base": 30, "density": 2.2},
        "DNA Origami": {"biodegradation": 1, "cost_base": 120, "density": 1.65},
        "Liposome": {"biodegradation": 14, "cost_base": 60, "density": 1.0},
        "Polymeric NP": {"biodegradation": 45, "cost_base": 35, "density": 1.15},
        "Albumin NP": {"biodegradation": 10, "cost_base": 70, "density": 1.35},
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**💬 Recommended Materials for Your Drug**")
        
        # Get drug recommendation context
        selected_drug = st.session_state.get("selected_drug", "")
        mapping = get_recommended_materials(selected_drug)
        
        if mapping:
            optimal_mats, suitable_mats, not_rec_mats = order_materials_by_recommendation(selected_drug)
            
            # Show recommendations
            st.caption(f"**Drug:** {selected_drug}")
            st.caption("**Optimal carriers:** " + ", ".join(optimal_mats))
            if suitable_mats:
                st.caption("**Suitable alternatives:** " + ", ".join(suitable_mats))
            
            # Create sorted material list: optimal first, then suitable, then others
            sorted_materials = optimal_mats + suitable_mats + not_rec_mats
            
            # Find current selection in sorted list
            current_material = d.get("Material", "Lipid NP")
            try:
                current_index = sorted_materials.index(current_material)
            except ValueError:
                current_index = 0
            
            d["Material"] = st.selectbox(
                "Select Material",
                sorted_materials,
                index=current_index,
                help="Reordered by recommendation for selected drug"
            )
            
            # Show recommendation level for selected material
            rec_level = get_recommendation_level(selected_drug, d["Material"])
            if rec_level == "optimal":
                st.success(f"✅ **Optimal** choice for {selected_drug}")
            elif rec_level == "suitable":
                st.info(f"ℹ️ **Suitable** alternative for {selected_drug}")
            else:
                st.warning(f"⚠️ **Not typically recommended** for {selected_drug}. Consider changing material.")
        else:
            # Fallback if no drug selected
            material_keys = list(material_properties.keys())
            current_material = d.get("Material", "Lipid NP")
            try:
                material_index = material_keys.index(current_material)
            except ValueError:
                material_index = 0
            
            d["Material"] = st.selectbox(
                "Select Material",
                material_keys,
                index=material_index
            )
        
        material_info = material_properties.get(d["Material"], {})
        st.caption(f"🔄 **Biodegradation**: {material_info.get('biodegradation', 'N/A')} days")
        st.caption(f"💰 **Cost Base**: ${material_info.get('cost_base', 'N/A')}")
        
        # Show material characteristics
        with st.expander("📋 Material Details", expanded=False):
            mat_desc = get_material_info(d["Material"])
            if mat_desc:
                st.markdown(f"**Description:** {mat_desc.get('description', 'N/A')}")
                st.markdown(f"**Best Payload:** {mat_desc.get('best_payload', 'N/A')}")
    
    with col2:
        # Get disease-specific target organ
        selected_disease = st.session_state.get("selected_disease", "")
        disease_prefs = DISEASE_CLEARANCE_PREFERENCES.get(selected_disease, {})
        disease_target_organ = disease_prefs.get("target_organ", "Liver Cells")
        
        # Map target organ names to standard format for backward compatibility
        target_organ_mapping = {
            "Liver": "Liver Cells",
            "Pancreas": "Tumor",
            "Mammary gland": "Tumor",
            "Lung": "Lung",
            "Colon": "Tumor"
        }
        
        # Get the standardized target option
        standard_target = target_organ_mapping.get(disease_target_organ, disease_target_organ)
        
        # Set and display target organ automatically based on disease selection
        d["Target"] = standard_target
        
        st.info(f"""
        ✅ **Target Organ/Tissue:** {disease_target_organ}
        
        *Automatically set based on your disease selection ({selected_disease})*
        """)
        
        st.caption(f"⚡ **Density**: {material_info.get('density', 'N/A')} g/cm³")
        
        # Show disease-drug context
        with st.expander("🏥 Current Context", expanded=False):
            st.markdown(f"**Disease:** {st.session_state.get('selected_disease', 'Not selected')}")
            st.markdown(f"**Drug:** {st.session_state.get('selected_drug', 'Not selected')}")
            st.markdown(f"**HCC Subtype:** {st.session_state.get('hcc_subtype', 'N/A')}")
    
    st.markdown("### 📏 Physical Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["Size"] = st.number_input(
            "Core Particle Size (nm)",
            min_value=10,
            max_value=500,
            value=int(d.get("Size", 100)),
            step=5,
            help="Optimal range: 80-120 nm"
        )
    
    with col2:
        d["PDI"] = st.number_input(
            "Polydispersity Index",
            min_value=0.05,
            max_value=0.5,
            value=float(d.get("PDI", 0.15)),
            step=0.02,
            format="%.3f",
            help="<0.1 = very uniform"
        )
    
    with col3:
        d["HydrodynamicSize"] = st.number_input(
            "Hydrodynamic Size (nm)",
            min_value=20,
            max_value=600,
            value=int(d.get("HydrodynamicSize", 120)),
            step=5,
        )
    
    st.markdown("### ⚛️ Encapsulation & Stability")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Ensure Encapsulation is numeric (fix for legacy "Passive Loading" string values)
        current_encap = d.get("Encapsulation", 85)
        if isinstance(current_encap, str):
            current_encap = 85  # Reset to default if string
        
        d["Encapsulation"] = st.number_input(
            "Drug Encapsulation (%)",
            min_value=10,
            max_value=100,
            value=int(current_encap),
            step=5,
        )
    
    with col2:
        d["Stability"] = st.number_input(
            "Stability (%)",
            min_value=20,
            max_value=100,
            value=int(d.get("Stability", 85)),
            step=5,
        )
    
    with col3:
        d["DegradationTime"] = st.number_input(
            "Degradation Time (days)",
            min_value=1,
            max_value=365,
            value=int(d.get("DegradationTime", 30)),
            step=5,
        )    
    st.divider()
    st.markdown("### 🎯 Parameter Impact on Score")
    display_score_gauge("gauge_core")
# TAB 2: SURFACE & CHEMISTRY
with tab2:
    st.subheader("🎨 Surface Modification & Chemistry")
    
    # Initialize session state for toggles if not exists
    if "toggle_surface_area" not in st.session_state:
        st.session_state.toggle_surface_area = True
    if "toggle_hydrophobicity" not in st.session_state:
        st.session_state.toggle_hydrophobicity = True
    if "toggle_crystallinity" not in st.session_state:
        st.session_state.toggle_crystallinity = True
    if "toggle_coating_functional" not in st.session_state:
        st.session_state.toggle_coating_functional = True
    
    # Mandatory Section
    st.markdown("#### 🔴 Mandatory Parameters")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Surface Charge**")
        d["Charge"] = st.number_input(
            "Surface Charge (mV)",
            min_value=-50,
            max_value=50,
            value=int(d.get("Charge", -5)),
            step=2,
            help="Optimal: ±10 mV"
        )
    
    st.markdown("#### 🟡 Optional Parameters")
    
    # Surface Area Toggle
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        st.session_state.toggle_surface_area = st.checkbox("", value=st.session_state.toggle_surface_area, key="surface_area_toggle")
    with col2:
        st.write("**Surface Area**")
    
    if st.session_state.toggle_surface_area:
        d["SurfaceArea"] = st.number_input(
            "Surface Area (nm²)",
            min_value=50,
            max_value=2000,
            value=int(d.get("SurfaceArea") or 250),
            step=50,
            label_visibility="collapsed"
        )
    else:
        d["SurfaceArea"] = None
    
    # Hydrophobicity Toggle
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        st.session_state.toggle_hydrophobicity = st.checkbox("", value=st.session_state.toggle_hydrophobicity, key="hydrophobicity_toggle")
    with col2:
        st.write("**Hydrophobicity**")
    
    if st.session_state.toggle_hydrophobicity:
        d["Hydrophobicity"] = st.number_input(
            "Surface Hydrophobicity (LogP)",
            min_value=-5.0,
            max_value=5.0,
            value=float(d.get("Hydrophobicity") or 1.5),
            step=0.2,
            format="%.2f",
            label_visibility="collapsed"
        )
    else:
        d["Hydrophobicity"] = None
    
    # Crystallinity Toggle
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        st.session_state.toggle_crystallinity = st.checkbox("", value=st.session_state.toggle_crystallinity, key="crystallinity_toggle")
    with col2:
        st.write("**Crystallinity**")
    
    if st.session_state.toggle_crystallinity:
        d["CrystallinityIndex"] = st.number_input(
            "Crystallinity Index (%)",
            min_value=0,
            max_value=100,
            value=int(d.get("CrystallinityIndex") or 65),
            step=5,
            label_visibility="collapsed"
        )
    else:
        d["CrystallinityIndex"] = None
    
    st.divider()
    st.markdown("### 🎯 Parameter Impact on Score")
    display_score_gauge("gauge_surface")

# TAB 3: TARGETING & CRITICAL PARAMETERS
with tab3:
    st.subheader("🎯 Targeting, Stability, Immunogenicity & Clearance")
    st.caption("Critical parameters that directly impact nanoparticle efficiency, viability, and disease suitability")
    
    # Get context information
    selected_disease = st.session_state.get("selected_disease", "")
    selected_drug = st.session_state.get("selected_drug", "")
    selected_material = d.get("Material", "Lipid NP")
    
    # ============================================================
    # SUB-TAB 1: SURFACE FUNCTIONALIZATION/TARGETING
    # ============================================================
    
    st.divider()
    st.markdown("### 1️⃣ Surface Functionalization (Targeting Ligands)")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.info(f"**Disease Context:** {selected_disease} | **Drug:** {selected_drug}")
        
        # Get smart recommendations
        targeting_rec = get_combined_targeting_recommendation(selected_disease, selected_drug)
        optimal_ligands = targeting_rec.get("optimal", [])
        all_options = targeting_rec.get("all_options", [])
        
        # If we have recommendations, prioritize them
        if optimal_ligands:
            ligand_options = optimal_ligands + [x for x in all_options if x not in optimal_ligands] + ["None"]
        else:
            ligand_options = get_all_ligands() + ["None"]
        
        # Get current ligand, with safe fallback
        current_ligand = d.get("Ligand", optimal_ligands[0] if optimal_ligands else "GalNAc")
        try:
            ligand_index = ligand_options.index(current_ligand)
        except ValueError:
            ligand_index = 0  # Default to first option if not found
        
        d["Ligand"] = st.selectbox(
            "🎯 Primary Targeting Ligand",
            ligand_options,
            index=ligand_index
        )
        
        # Always render the input to persist values in session state
        ligand_density_disabled = d["Ligand"] == "None"
        d["LigandDensity"] = st.number_input(
            "Ligand Surface Density (%)",
            min_value=5,
            max_value=100,
            value=int(d.get("LigandDensity", 60)),
            step=5,
            disabled=ligand_density_disabled,
            help="Only active when a ligand is selected" if ligand_density_disabled else "Higher density = better targeting, but may increase immunogenicity"
        )
    
    with col2:
        if d["Ligand"] != "None":
            ligand_info = get_ligand_details(d["Ligand"])
            st.metric("Target Receptor", ligand_info.get("target_receptors", ["N/A"])[0])
            st.metric("Binding Strength", ligand_info.get("binding_strength", "N/A"))
            st.metric("Immunogenicity", ligand_info.get("immunogenicity", "N/A"))
    
    # Show ligand explanation
    if d["Ligand"] != "None":
        ligand_details = get_ligand_details(d["Ligand"])
        with st.expander(f"📖 About {d['Ligand']} Targeting", expanded=False):
            st.write(f"**Mechanism:** {ligand_details.get('mechanism', 'N/A')}")
            st.write(f"**Best for:** {', '.join(ligand_details.get('suitable_diseases', []))}")
            st.write(f"**Approval Status:** {ligand_details.get('approval_status', 'Unknown')}")
    
    st.divider()
    
    # ============================================================
    # COATING & FUNCTIONAL GROUPS
    # ============================================================
    
    st.markdown("### 🧪 Coating & Functional Groups")
    
    # Initialize toggle if not exists
    if "toggle_coating_functional" not in st.session_state:
        st.session_state.toggle_coating_functional = True
    
    # Coating & Functional Groups Toggle
    col1, col2 = st.columns([0.2, 0.8])
    with col1:
        st.session_state.toggle_coating_functional = st.checkbox("", value=st.session_state.toggle_coating_functional, key="coating_functional_toggle_targeting")
    with col2:
        st.markdown("**Enable Coating & Functional Groups Customization**")
    
    if st.session_state.toggle_coating_functional:
        col1, col2 = st.columns(2)
        
        with col1:
            d["SurfaceCoating"] = st.multiselect(
                "Surface Coating Layers",
                ["PEG (Stealth)", "Chitosan", "Hyaluronic Acid", "Albumin"],
                default=d.get("SurfaceCoating", ["PEG (Stealth)"]),
                label_visibility="collapsed"
            )
            
            if d["SurfaceCoating"]:
                d["CoatingThickness"] = st.number_input(
                    "Coating Thickness (nm)",
                    min_value=0.5,
                    max_value=20.0,
                    value=float(d.get("CoatingThickness") or 2.5),
                    step=0.5,
                    format="%.1f",
                    label_visibility="collapsed"
                )
        
        with col2:
            d["FunctionalGroups"] = st.multiselect(
                "Functional Groups",
                ["-OH (Hydroxyl)", "-COOH (Carboxyl)", "-NH2 (Amino)", "-SH (Thiol)"],
                default=d.get("FunctionalGroups", ["-COOH (Carboxyl)"]),
                label_visibility="collapsed"
            )
    else:
        d["SurfaceCoating"] = None
        d["CoatingThickness"] = None
        d["FunctionalGroups"] = None
    
    st.divider()
    
    # ============================================================
    # SUB-TAB 2: IMMUNOGENICITY & PEGylation
    # ============================================================
    
    st.markdown("### 2️⃣ Immunogenicity & PEGylation Strategy")
    
    col1, col2 = st.columns(2)
    
    with col1:
        material_immuno = get_material_immunogenicity_profile(selected_material)
        st.metric("Base Immunogenicity", material_immuno.get("base_immunogenicity", "Unknown"))
        st.metric("MPS Recognition", material_immuno.get("mps_recognition", "Unknown"))
        st.metric("Requires PEGylation", "Yes" if material_immuno.get("peg_responsive") else "No")
    
    with col2:
        peg_rec = get_peg_recommendation(selected_material, selected_disease, selected_drug)
        st.metric("Optimal PEG Density", peg_rec.get("peg_density", "N/A"))
        st.metric("Expected Circulation", peg_rec.get("expected_circulation_time", "N/A"))
        st.metric("MPS Reduction", peg_rec.get("mps_reduction", "N/A"))
    
    # ============================================================
    # INTERACTIVE CONTROLS FOR IMMUNOGENICITY
    # ============================================================
    
    st.markdown("**⚙️ Adjust PEGylation Parameters:**")
    
    # Initialize PEG Density toggle if not exists
    if "toggle_peg_density" not in st.session_state:
        st.session_state.toggle_peg_density = True
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if material_immuno.get("peg_responsive"):
            # PEG Density Toggle
            col_toggle, col_label = st.columns([0.15, 0.85])
            with col_toggle:
                st.session_state.toggle_peg_density = st.checkbox("", value=st.session_state.toggle_peg_density, key="peg_density_toggle")
            with col_label:
                st.write("**PEG Density (%)**")
            
            if st.session_state.toggle_peg_density:
                d["PEGDensity"] = st.number_input(
                    "PEG Density (%)",
                    min_value=0,
                    max_value=20,
                    value=int(d.get("PEGDensity") or 5),
                    step=1,
                    help="Higher PEG density = better stealth, slower targeting",
                    label_visibility="collapsed"
                )
            else:
                d["PEGDensity"] = None
        else:
            st.info("ℹ️ PEGylation not needed for this material")
            d["PEGDensity"] = 0
    
    with col2:
        d["PEGChainLength"] = st.number_input(
            "PEG Chain Length (Da)",
            min_value=500,
            max_value=20000,
            value=int(d.get("PEGChainLength", 2000)),
            step=100,
            help="Molecular weight of PEG chain in Daltons. Higher = longer circulation time but slower diffusion"
        )
    
    # Initialize Coating Thickness toggle if not exists
    if "toggle_coating_thickness" not in st.session_state:
        st.session_state.toggle_coating_thickness = True
    
    with col3:
        # Coating Thickness Toggle
        col_toggle, col_label = st.columns([0.15, 0.85])
        with col_toggle:
            st.session_state.toggle_coating_thickness = st.checkbox("", value=st.session_state.toggle_coating_thickness, key="coating_thickness_toggle")
        with col_label:
            st.write("**Coating Thickness (nm)**")
        
        if st.session_state.toggle_coating_thickness:
            d["CoatingThickness"] = st.number_input(
                "Coating Thickness (nm)",
                min_value=0.5,
                max_value=20.0,
                value=float(d.get("CoatingThickness") or 2.5),
                step=0.5,
                format="%.1f",
                help="Thicker coating = better stealth but slower cell uptake",
                label_visibility="collapsed"
            )
        else:
            d["CoatingThickness"] = None
    
    # PEGylation details
    with st.expander("📖 PEGylation Strategy & Rationale", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Why PEGylation?**")
            st.write(peg_rec.get("rationale", "No rationale available"))
        with col2:
            disease_immuno = get_disease_immunogenicity_requirements(selected_disease)
            st.write("**Disease-Specific Considerations:**")
            st.write(disease_immuno.get("optimal_approach", "No special considerations"))
    
    st.divider()
    
    # ============================================================
    # SUB-TAB 3: STABILITY PROFILE
    # ============================================================
    
    st.markdown("### 3️⃣ Stability Testing & Storage")
    
    col1, col2 = st.columns(2)
    
    with col1:
        stability_material = get_material_stability_profile(selected_material)
        st.metric("pH Stability Range", stability_material.get("pH_stability_range", "N/A"))
        st.metric("Optimal pH", stability_material.get("optimal_pH", "N/A"))
        st.metric("Temperature Stability", stability_material.get("temperature_stability", "N/A"))
    
    with col2:
        stability_drug = get_drug_stability_requirements(selected_drug)
        st.metric("Drug pH Sensitivity", stability_drug.get("pH_sensitivity", "N/A"))
        st.metric("Drug Temperature Sens.", stability_drug.get("temperature_sensitivity", "N/A"))
        st.metric("Light Sensitive", stability_drug.get("light_sensitivity", "No"))
    
    # ============================================================
    # INTERACTIVE CONTROLS FOR STABILITY
    # ============================================================
    
    st.markdown("**⚙️ Adjust Storage & Testing Parameters:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["StoragePH"] = st.number_input(
            "Storage pH",
            min_value=3.0,
            max_value=11.0,
            value=float(d.get("StoragePH", 7.4)),
            step=0.5,
            format="%.1f",
            help="Select optimal pH for storage conditions"
        )
    
    with col2:
        d["StorageTemperature"] = st.selectbox(
            "Storage Temperature",
            ["-80°C (Ultra-cold)", "-20°C (Freezer)", "2-8°C (Refrigerated)", "25°C (Room Temp)"],
            index=["-80°C (Ultra-cold)", "-20°C (Freezer)", "2-8°C (Refrigerated)", "25°C (Room Temp)"].index(d.get("StorageTemperature", "2-8°C (Refrigerated)"))
        )
    
    with col3:
        d["FreezethawCycles"] = st.number_input(
            "Freeze-Thaw Cycles",
            min_value=0,
            max_value=10,
            value=int(d.get("FreezethawCycles", 3)),
            step=1,
            help="Number of freeze-thaw cycles to test"
        )
    
    combined_stability = get_combined_stability_recommendation(selected_material, selected_drug)
    
    with st.expander("📖 Critical Stability Concerns & Testing", expanded=False):
        st.write("**Critical Concerns:**")
        for concern in combined_stability.get("critical_concerns", []):
            st.write(f"• {concern}")
        
        st.write("\n**Required Stability Tests:**")
        for test in combined_stability.get("required_tests", []):
            st.write(f"• {test}")
    
    st.divider()
    
    # ============================================================
    # SUB-TAB 4: CLEARANCE MECHANISM
    # ============================================================
    
    st.markdown("### 4️⃣ Clearance Mechanism & Organ Accumulation")
    
    # Get size for clearance calculations
    particle_size = int(d.get("Size", 100))
    charge_val = int(d.get("Charge", -5))
    
    # Determine charge type
    if charge_val > 5:
        charge_type = "Cationic (+ charge)"
    elif charge_val < -5:
        charge_type = "Anionic (- charge)"
    else:
        charge_type = "Neutral (no charge)"
    
    col1, col2 = st.columns(2)
    
    with col1:
        clearance_material = get_material_clearance_profile(selected_material)
        st.metric("Half-Life (Circulation)", clearance_material.get("half_life", "N/A"))
        st.metric("Primary Route", clearance_material.get("primary_route", "N/A"))
        st.metric("Liver Accumulation", clearance_material.get("liver_accumulation", "N/A"))
    
    with col2:
        disease_clear = get_disease_clearance_optimization(selected_disease)
        st.metric("Target Organ", disease_clear.get("target_organ", "N/A"))
        st.metric("Recommended Size", disease_clear.get("recommended_size", "N/A"))
        st.metric("Spleen Concern", clearance_material.get("spleen_accumulation", "N/A"))
    
    # ============================================================
    # INTERACTIVE CONTROLS FOR CLEARANCE
    # ============================================================
    
    st.markdown("**⚙️ Adjust Clearance Parameters:**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["ClearanceSize"] = st.number_input(
            "Particle Size (nm)",
            min_value=10,
            max_value=300,
            value=int(d.get("ClearanceSize", particle_size)),
            step=10,
            help="Affects MPS recognition and tissue penetration"
        )
    
    with col2:
        d["ClearanceCharge"] = st.number_input(
            "Surface Charge (mV)",
            min_value=-50,
            max_value=50,
            value=int(d.get("ClearanceCharge", charge_val)),
            step=5,
            help="Affects protein corona and clearance pathway"
        )
    
    with col3:
        clearance_target_options = ["Liver", "Pancreas", "Breast", "Lung", "Colon"]
        current_target = d.get("ClearanceTarget", disease_clear.get("target_organ", "Liver"))
        try:
            clearance_target_idx = clearance_target_options.index(current_target)
        except ValueError:
            clearance_target_idx = 0
        
        d["ClearanceTarget"] = st.selectbox(
            "Target Organ for Clearance",
            clearance_target_options,
            index=clearance_target_idx,
            help="Optimize clearance pathway for target organ"
        )
    
    with st.expander("📖 Predicted Organ Accumulation & Optimization", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Particle Size:** {d.get('ClearanceSize', particle_size)} nm")
            st.write(f"**Surface Charge:** {d.get('ClearanceCharge', charge_val)} mV")
            
            # Determine new charge type
            new_charge = int(d.get('ClearanceCharge', charge_val))
            if new_charge > 5:
                new_charge_type = "Cationic (+ charge)"
            elif new_charge < -5:
                new_charge_type = "Anionic (- charge)"
            else:
                new_charge_type = "Neutral (no charge)"
            
            st.write(f"**Charge Type:** {new_charge_type}")
            st.write(f"**Material:** {selected_material}")
        
        with col2:
            clearance_opt = get_clearance_optimization_for_disease_drug_material(
                selected_disease, selected_drug, selected_material
            )
            st.write(f"**Liver Accumulation:** {clearance_opt.get('liver_concern', 'N/A')}")
            st.write(f"**Spleen Accumulation:** {clearance_opt.get('spleen_concern', 'N/A')}")
            st.write(f"**Circulation Half-Life:** {clearance_opt.get('half_life', 'N/A')}")
            st.write(f"**Recommendations:**")
            for rec in clearance_opt.get('recommendations', []):
                st.write(f"• {rec}")
    
    st.divider()
    
    # ============================================================
    # RELEASE PROFILE
    # ============================================================
    
    st.markdown("### 💊 Release Profile")
    
    release_options = ["Immediate", "Sustained (1 week)", "Sustained (2 weeks)", "Sustained (1 month)"]
    current_release = d.get("ReleaseProfile", "Sustained (1 week)")
    try:
        release_index = release_options.index(current_release)
    except ValueError:
        release_index = 1  # Default to "Sustained (1 week)"
    
    d["ReleaseProfile"] = st.selectbox(
        "Release Profile",
        release_options,
        index=release_index
    )
    
    d["ReleasePredictability"] = st.number_input(
        "Release Predictability (%)",
        min_value=50,
        max_value=100,
        value=int(d.get("ReleasePredictability", 85)),
        step=5,
        help="Higher predictability = more controlled drug release"
    )
    
    # SYNC design changes to session state immediately
    st.session_state.design = d
    
    st.divider()
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Targeting Ligand", d.get("Ligand", "None"))
    with col2:
        st.metric("Ligand Density", f"{d.get('LigandDensity', 0)}%")
    with col3:
        st.metric("Release Profile", d.get("ReleaseProfile", "N/A")[:10] + "...")
    with col4:
        st.metric("Predictability", f"{d.get('ReleasePredictability', 0)}%")
    
    st.divider()
    st.markdown("### 🎯 Parameter Impact on Score")
    
    # Recompute impact with current synced values
    current_impact = compute_impact(st.session_state.design)
    current_score = overall_score_from_impact(current_impact)
    
    fig = go.Figure(data=[go.Indicator(
        mode="gauge+number+delta",
        value=current_score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Design Success Score"},
        delta={"reference": 80, "suffix": " vs target"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkblue"},
            "steps": [
                {"range": [0, 30], "color": "rgba(255, 100, 100, 0.3)"},
                {"range": [30, 60], "color": "rgba(255, 200, 0, 0.3)"},
                {"range": [60, 85], "color": "rgba(150, 255, 100, 0.3)"},
                {"range": [85, 100], "color": "rgba(100, 255, 100, 0.3)"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 85
            }
        }
    )])
    
    fig.update_layout(
        height=350,
        font={"size": 14},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig, use_container_width=True, key=f"gauge_targeting_{current_score:.1f}")
    with col2:
        st.markdown("### 📊 Score Metrics")
        st.metric("Overall Score", f"{current_score:.1f}/100")
        st.metric("Delivery", f"{current_impact['Delivery']:.1f}/100")
        st.metric("Toxicity", f"{current_impact['Toxicity']:.1f}/10")
        st.metric("Cost Index", f"{current_impact['Cost']:.1f}/100")

# TAB 4: SCORING & ANALYSIS
with tab4:
    st.subheader("📊 Design Performance Analysis")
    
    # Initialize weight settings in session state
    if "weight_presets" not in st.session_state:
        st.session_state.weight_presets = {
            "Balanced": {"size": 0.18, "charge": 0.14, "encap": 0.18, "pdi": 0.10, "hydro": 0.06, "stability": 0.04, "targeting": 0.08, "release": 0.04, "surface_area": 0.04, "hydrophobicity": 0.05, "crystallinity": 0.05, "coating": 0.05},
            "Targeting-Focused": {"size": 0.12, "charge": 0.10, "encap": 0.12, "pdi": 0.08, "hydro": 0.04, "stability": 0.03, "targeting": 0.20, "release": 0.10, "surface_area": 0.03, "hydrophobicity": 0.04, "crystallinity": 0.04, "coating": 0.10},
            "Core-Physics-Focus": {"size": 0.25, "charge": 0.20, "encap": 0.25, "pdi": 0.15, "hydro": 0.08, "stability": 0.06, "targeting": 0.01, "release": 0.00, "surface_area": 0.00, "hydrophobicity": 0.00, "crystallinity": 0.00, "coating": 0.00},
            "Surface-Chemistry-Focus": {"size": 0.10, "charge": 0.10, "encap": 0.10, "pdi": 0.08, "hydro": 0.05, "stability": 0.03, "targeting": 0.06, "release": 0.03, "surface_area": 0.10, "hydrophobicity": 0.15, "crystallinity": 0.10, "coating": 0.10},
        }
    
    if "custom_weights" not in st.session_state:
        st.session_state.custom_weights = st.session_state.weight_presets["Balanced"].copy()
    
    # Preset selector
    st.markdown("### ⚖️ Weight Configuration")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        preset_name = st.selectbox(
            "📋 Weight Preset",
            list(st.session_state.weight_presets.keys()),
            help="Select a preset weight distribution"
        )
        
        if preset_name:
            st.session_state.custom_weights = st.session_state.weight_presets[preset_name].copy()
    
    with col2:
        st.info(f"**Active:** {preset_name}")
    
    st.divider()
    
    # Weight adjustment sliders
    st.markdown("### 🎚️ Fine-Tune Weights")
    st.caption("Drag sliders to adjust importance of each parameter (will auto-normalize)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.session_state.custom_weights["size"] = st.number_input("Size", 0.0, 30.0, float(st.session_state.custom_weights["size"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["charge"] = st.number_input("Charge", 0.0, 30.0, float(st.session_state.custom_weights["charge"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["encap"] = st.number_input("Encapsulation", 0.0, 30.0, float(st.session_state.custom_weights["encap"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["pdi"] = st.number_input("PDI", 0.0, 20.0, float(st.session_state.custom_weights["pdi"]), 0.01, format="%.2f") / 100
    
    with col2:
        st.session_state.custom_weights["targeting"] = st.number_input("Targeting", 0.0, 30.0, float(st.session_state.custom_weights["targeting"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["release"] = st.number_input("Release Predict", 0.0, 20.0, float(st.session_state.custom_weights["release"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["hydrophobicity"] = st.number_input("Hydrophobicity", 0.0, 20.0, float(st.session_state.custom_weights["hydrophobicity"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["crystallinity"] = st.number_input("Crystallinity", 0.0, 20.0, float(st.session_state.custom_weights["crystallinity"]), 0.01, format="%.2f") / 100
    
    with col3:
        st.session_state.custom_weights["coating"] = st.number_input("Coating", 0.0, 20.0, float(st.session_state.custom_weights["coating"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["hydro"] = st.number_input("Hydrodynamic", 0.0, 20.0, float(st.session_state.custom_weights["hydro"]), 0.01, format="%.2f") / 100
        st.session_state.custom_weights["stability"] = st.slider("Stability", 0, 20, int(st.session_state.custom_weights["stability"] * 100), 1) / 100
        st.session_state.custom_weights["surface_area"] = st.slider("Surface Area", 0, 20, int(st.session_state.custom_weights["surface_area"] * 100), 1) / 100
    
    st.divider()
    
    # Display weight distribution
    st.markdown("### 📊 Weight Distribution")
    
    # Create pie chart of weights
    import plotly.graph_objects as go
    weights_dict = st.session_state.custom_weights
    
    # Group small weights
    labels = []
    values = []
    for k, v in weights_dict.items():
        if v > 0.02:  # Only show > 2%
            labels.append(k.replace('_', ' ').title())
            values.append(v)
    
    fig_weights = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hoverinfo="label+percent+value",
        textposition="auto",
        textinfo="label+percent"
    )])
    
    fig_weights.update_layout(
        height=400,
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    st.plotly_chart(fig_weights, use_container_width=True)
    
    st.divider()
    
    # Calculate score with custom weights
    current_impact_custom = compute_impact(d, st.session_state.custom_weights)
    current_score_custom = overall_score_from_impact(current_impact_custom)
    
    st.markdown("### 🎯 Impact on Score (with Custom Weights)")
    
    fig_gauge = go.Figure(data=[go.Indicator(
        mode="gauge+number+delta",
        value=current_score_custom,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Design Success Score"},
        delta={"reference": 80, "suffix": " vs target"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkblue"},
            "steps": [
                {"range": [0, 30], "color": "rgba(255, 100, 100, 0.3)"},
                {"range": [30, 60], "color": "rgba(255, 200, 0, 0.3)"},
                {"range": [60, 85], "color": "rgba(150, 255, 100, 0.3)"},
                {"range": [85, 100], "color": "rgba(100, 255, 100, 0.3)"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 85
            }
        }
    )])
    
    fig_gauge.update_layout(
        height=350,
        font={"size": 14},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.plotly_chart(fig_gauge, use_container_width=True, key=f"gauge_custom_{current_score_custom:.1f}")
    with col2:
        st.markdown("### 📊 Score Breakdown")
        st.metric("Overall Score", f"{current_score_custom:.1f}/100")
        st.metric("Delivery", f"{current_impact_custom['Delivery']:.1f}/100")
        st.metric("Toxicity", f"{current_impact_custom['Toxicity']:.1f}/10")
        st.metric("Cost Index", f"{current_impact_custom['Cost']:.1f}/100")


# ============================================================================
# TAB 5: SPRINT 1 BLOOD SAFETY & ADVANCED PARAMETERS
# ============================================================================

with tab5:
    st.subheader("🩸 Sprint 1: Blood Safety & Physiological Parameters")
    
    st.markdown("""
    **Advanced safety assessment** for in vivo performance.
    
    These parameters predict behavior in the bloodstream and help catch 
    potentially problematic designs early.
    """)
    
    st.divider()
    
    # ========================================
    # INTERACTIVE SLIDERS FOR OPTIMIZATION (MOVED TO TOP)
    # ========================================
    st.markdown("### 🎚️ Optimize Parameters for Blood Safety")
    st.caption("✨ Adjust key parameters below - metrics update automatically in real-time")
    
    # Main optimization controls - 3 columns for primary parameters
    opt_col1, opt_col2, opt_col3 = st.columns(3)
    
    with opt_col1:
        st.markdown("#### 🔴 Charge (Affects Hemolysis & pI)")
        d["Charge"] = st.slider(
            "Charge (mV)",
            min_value=-50,
            max_value=50,
            value=int(d.get("Charge", -30)),
            step=5,
            key="sprint1_charge_opt",
            help="Positive charges → hemolysis & protein binding. Neutral (±5) = best"
        )
        st.caption("💡 Keep near 0 mV for safety")
    
    with opt_col2:
        st.markdown("#### 💛 PEG Density (Affects Osmolarity & Half-Life)")
        d["PEG_Density"] = st.slider(
            "PEG Density (%)",
            min_value=0,
            max_value=100,
            value=int(d.get("PEG_Density", 50)),
            step=5,
            key="sprint1_peg_opt",
            help="Higher PEG = stealth coat + longer circulation, but increases osmolarity"
        )
        st.caption("💡 30-60% optimal for most applications")
    
    with opt_col3:
        st.markdown("#### 🔵 Drug Loading (Affects Osmolarity)")
        d["Drug"] = st.slider(
            "Drug Loading (%)",
            min_value=0,
            max_value=100,
            value=int(d.get("Drug", 50)),
            step=5,
            key="sprint1_drug_opt",
            help="Higher loading increases osmotic activity"
        )
        st.caption("💡 70-90% loading is typical target")
    
    # Secondary parameters (hidden in expander)
    with st.expander("⚙️ Advanced Fine-Tuning (Optional)"):
        adv_col1, adv_col2 = st.columns(2)
        
        with adv_col1:
            st.markdown("**Hydrophobicity** (Affects Hemolysis)")
            d["Hydrophobicity"] = st.slider(
                "Hydrophobicity (LogP)",
                min_value=0.0,
                max_value=5.0,
                value=float(d.get("Hydrophobicity") or 1.5),
                step=0.1,
                key="sprint1_hydro_opt",
                help="Optimal: 0.5-2.5 LogP. Higher = membrane penetration risk"
            )
        
        with adv_col2:
            st.markdown("**Encapsulation %** (Affects Osmolarity)")
            # Ensure Encapsulation is numeric (fix for legacy "Passive Loading" string values)
            current_encap2 = d.get("Encapsulation", 85)
            if isinstance(current_encap2, str):
                current_encap2 = 85  # Reset to default if string
            
            d["Encapsulation"] = st.slider(
                "Encapsulation Efficiency (%)",
                min_value=50,
                max_value=100,
                value=int(current_encap2),
                step=5,
                key="sprint1_encap_opt",
                help="Lower efficiency = more water = higher osmolarity"
            )
    
    # Sync design changes
    st.session_state.design = d
    
    st.divider()
    
    # ========================================
    # REAL-TIME ASSESSMENT (NOW AFTER SLIDERS)
    # ========================================
    st.markdown("### 📊 Real-Time Blood Safety Assessment")
    
    # Recalculate metrics with current slider values
    osmolarity_result = calculate_osmolarity(d)
    hemolysis_result = calculate_hemolysis_risk(d)
    halflife_result = predict_improved_blood_half_life(d)
    pI_result = calculate_isoelectric_point(d)
    
    # Quick status cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        osmo_status = "✅" if 250 <= osmolarity_result['osmolarity_mosm_kg'] <= 350 else "⚠️"
        st.metric(
            f"{osmo_status} Osmolarity",
            f"{osmolarity_result['osmolarity_mosm_kg']:.0f} mOsm/kg",
            help="Safe range: 250-350"
        )
    
    with col2:
        hemolysis_status = "✅" if hemolysis_result['hemolysis_score'] < 35 else "⚠️" if hemolysis_result['hemolysis_score'] < 50 else "❌"
        st.metric(
            f"{hemolysis_status} Hemolysis",
            f"{hemolysis_result['hemolysis_score']:.0f}/100",
            help="Lower is better (0 = no hemolysis)"
        )
    
    with col3:
        st.metric(
            "⏱️ Half-Life",
            f"{halflife_result['blood_half_life_hours']:.2f} hrs",
            help=f"Mechanism: {halflife_result['clearance_mechanism']}"
        )
    
    with col4:
        pI_risk = "✅ Low" if "Low" in pI_result['aggregation_concern'] else "🟡 Moderate" if "Moderate" in pI_result['aggregation_concern'] else "⚠️ High"
        st.metric(
            "📌 Aggregation",
            pI_risk,
            help=f"pI: {pI_result['isoelectric_point_pH']:.1f}"
        )
    
    st.divider()
    
    # ========================================
    # 1. OSMOLARITY DETAILS
    # ========================================
    with st.expander("📍 Osmolarity Details (Cellular Toxicity)", expanded=False):
        st.markdown("**Determines osmotic stress on cells**")
        display_osmolarity_widget(d)
    
    # ========================================
    # 2. HEMOLYTIC ACTIVITY DETAILS
    # ========================================
    with st.expander("🩸 Hemolytic Activity Details (Blood Compatibility)", expanded=False):
        st.markdown("**Predicts red blood cell (RBC) lysis risk**")
        display_hemolysis_widget(d)
    
    # ========================================
    # 3. BLOOD HALF-LIFE DETAILS
    # ========================================
    with st.expander("⏱️ Blood Half-Life Details (Circulation Time)", expanded=False):
        st.markdown("**Multi-factor prediction: Size + PEG + Charge + Material**")
        display_halflife_widget(d)
    
    # ========================================
    # 4. ISOELECTRIC POINT DETAILS
    # ========================================
    with st.expander("📌 Isoelectric Point Details (pH Behavior)", expanded=False):
        st.markdown("**Predicts charge at different pH environments**")
        display_pI_widget(d)
    
    st.divider()
    
    # ========================================
    # OVERALL BLOOD SAFETY SCORE
    # ========================================
    st.markdown("### 🎯 Overall Blood Safety Score")
    
    # Calculate composite blood safety score (0-100)
    safety_components = {
        "osmolarity": 100 if 250 <= osmolarity_result['osmolarity_mosm_kg'] <= 350 else osmolarity_result.get('safety_score', 50),
        "hemolysis": 100 - hemolysis_result['hemolysis_score'],  # Invert: high score is bad
        "halflife": min(100, halflife_result['blood_half_life_hours'] * 20),  # 5 hrs = 100
        "aggregation": 100 if "Low" in pI_result['aggregation_concern'] else 70 if "Moderate" in pI_result['aggregation_concern'] else 40,
    }
    
    overall_blood_safety = sum(safety_components.values()) / len(safety_components)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_safety = go.Figure(data=[go.Indicator(
            mode="gauge+number+delta",
            value=overall_blood_safety,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Blood Safety Score"},
            delta={"reference": 80, "suffix": " vs target"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "darkgreen"},
                "steps": [
                    {"range": [0, 30], "color": "rgba(255, 100, 100, 0.3)"},
                    {"range": [30, 60], "color": "rgba(255, 200, 0, 0.3)"},
                    {"range": [60, 80], "color": "rgba(150, 255, 100, 0.3)"},
                    {"range": [80, 100], "color": "rgba(100, 255, 100, 0.3)"}
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 80
                }
            }
        )])
        
        fig_safety.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_safety, use_container_width=True, key=f"blood_safety_score_{overall_blood_safety:.1f}")
    
    with col2:
        st.markdown("### 📊 Component Scores")
        st.metric("Osmolarity", f"{safety_components['osmolarity']:.0f}/100")
        st.metric("Hemolysis", f"{safety_components['hemolysis']:.0f}/100")
        st.metric("Half-Life", f"{safety_components['halflife']:.0f}/100")
        st.metric("Aggregation", f"{safety_components['aggregation']:.0f}/100")
    
    st.divider()

# ============================================================================
# TAB 6: SPRINT 2 - CELLULAR & IMMUNE ASSESSMENT
# ============================================================================

with tab6:
    st.subheader("💊 Sprint 2: Cellular Uptake, Trafficking, & Immune Response")
    
    st.markdown("""
    **Comprehensive cellular and immune assessment** for in vitro efficacy.
    
    Sprint 2 predicts how nanoparticles interact with target cells, move inside cells, 
    release their payload, navigate the tumor microenvironment, and evade the immune system.
    """)
    
    st.divider()
    
    # ========================================
    # INTERACTIVE SLIDERS FOR OPTIMIZATION (SPRINT 2)
    # ========================================
    st.markdown("### 🎚️ Optimize Parameters for Cellular & Immune Response")
    st.caption("✨ Adjust key parameters below - all 5 metrics update automatically in real-time")
    
    # Main optimization controls - 3 columns for primary parameters
    opt_col1, opt_col2, opt_col3 = st.columns(3)
    
    with opt_col1:
        st.markdown("#### 📏 Size (Affects All Components)")
        d["Size"] = st.slider(
            "Size (nm)",
            min_value=20,
            max_value=300,
            value=int(d.get("Size", 100)),
            step=10,
            key="sprint2_size_opt",
            help="Optimal 50-150nm for cellular uptake. Smaller = better for trafficking. Larger = better for tumor penetration"
        )
        st.caption("💡 100 nm is ideal for most applications")
    
    with opt_col2:
        st.markdown("#### 🔴 Charge (Affects Uptake & Immune)")
        d["Charge"] = st.slider(
            "Charge (mV)",
            min_value=-50,
            max_value=50,
            value=int(d.get("Charge", -5)),
            step=5,
            key="sprint2_charge_opt",
            help="Positive charges → better uptake but more immune activation. Negative → immune evasion"
        )
        st.caption("💡 -5 to +5 is optimal")
    
    with opt_col3:
        st.markdown("#### 🧬 Material Type (Affects All Components)")
        material_options = list(AVAILABLE_MATERIALS)  # Convert to list
        current_material = d.get("Material", "Lipid NP")
        try:
            material_index = material_options.index(current_material)
        except ValueError:
            material_index = 0  # Default to first option if not found
        
        d["Material"] = st.selectbox(
            "Material",
            material_options,
            index=material_index,
            key="sprint2_material_opt",
            help="Different materials have different cellular uptake and immune profiles"
        )
    
    # Secondary parameters (hidden in expander)
    with st.expander("⚙️ Advanced Fine-Tuning (Optional)"):
        adv_col1, adv_col2, adv_col3 = st.columns(3)
        
        with adv_col1:
            st.markdown("**Ligand Targeting**")
            ligand_options = get_all_ligands() + ["None"]
            current_ligand = d.get("Ligand", "None")
            try:
                ligand_index = ligand_options.index(current_ligand)
            except ValueError:
                ligand_index = ligand_options.index("None")  # Fallback to None if not found
            
            d["Ligand"] = st.selectbox(
                "Ligand",
                ligand_options,
                index=ligand_index,
                key="sprint2_ligand_opt",
                help="Targeting ligands increase specific cell uptake"
            )
        
        with adv_col2:
            st.markdown("**PEG Density** (Stealth Coating)")
            d["PEG_Density"] = st.slider(
                "PEG Density (%)",
                min_value=0,
                max_value=100,
                value=int(d.get("PEG_Density", 50)),
                step=5,
                key="sprint2_peg_opt",
                help="Higher PEG = better immune evasion but reduced cellular uptake"
            )
        
        with adv_col3:
            st.markdown("**Hydrophobicity**")
            d["Hydrophobicity"] = st.slider(
                "Hydrophobicity (LogP)",
                min_value=0.0,
                max_value=5.0,
                value=float(d.get("Hydrophobicity") or 1.5),
                step=0.1,
                key="sprint2_hydro_opt",
                help="Optimal: 0.5-2.5 LogP. Affects membrane interaction"
            )
    
    # Sync design changes
    st.session_state.design = d
    
    st.divider()
    
    # Sprint 2 has 5 major assessment areas
    sprint2_tabs = st.tabs([
        "🔵 Cellular Uptake",
        "📍 Intracellular Trafficking", 
        "💊 Payload Release",
        "🏥 Tumor Microenvironment",
        "🛡️ Immune Response"
    ])
    
    # Get disease context for tumor microenvironment
    selected_disease = st.session_state.get("selected_disease", "Hepatocellular Carcinoma")
    disease_mapping = {
        "Hepatocellular Carcinoma": "HCC",
        "Pancreatic Cancer": "PDAC",
        "Melanoma": "Melanoma",
        "Breast Cancer": "Breast"
    }
    disease_context = disease_mapping.get(selected_disease, "HCC")
    
    # ========================================
    # SPRINT 2.1: CELLULAR UPTAKE
    # ========================================
    with sprint2_tabs[0]:
        st.markdown("### 🔵 Cellular Uptake & Internalization")
        st.caption("Predict how efficiently nanoparticles enter target cells")
        
        if st.checkbox("Show detailed cellular uptake analysis", key="uptake_detail"):
            display_cellular_uptake_widget(d)
        else:
            uptake_result = predict_cellular_uptake(d)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Uptake Efficiency", f"{uptake_result['uptake_efficiency']:.1f}%")
            with col2:
                st.metric("Uptake Score", f"{uptake_result['uptake_score']:.0f}/100")
            with col3:
                st.metric("Time to Saturation", f"{uptake_result['time_to_saturation']:.1f} hrs")
            
            st.markdown(f"**Mechanism:** {uptake_result['uptake_mechanism']}")
            st.markdown(f"**Pathway:** {uptake_result['uptake_pathway']}")
    
    # ========================================
    # SPRINT 2.2: INTRACELLULAR TRAFFICKING
    # ========================================
    with sprint2_tabs[1]:
        st.markdown("### 📍 Intracellular Trafficking & Localization")
        st.caption("Predict where particles go inside cells")
        
        if st.checkbox("Show detailed trafficking analysis", key="trafficking_detail"):
            display_intracellular_trafficking_widget(d)
        else:
            trafficking_result = predict_intracellular_trafficking(d)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Endosomal Escape", f"{trafficking_result['endosomal_escape']:.1f}%")
            with col2:
                st.metric("Cytoplasmic Access", f"{trafficking_result['cytoplasmic_access']:.1f}%")
            with col3:
                st.metric("Retention Time", f"{trafficking_result['retention_time']:.1f} hrs")
            
            st.markdown(f"**Primary Location:** {trafficking_result['primary_location']}")
            st.markdown(f"**Escape Mechanism:** {trafficking_result['escape_mechanism']}")
    
    # ========================================
    # SPRINT 2.3: PAYLOAD RELEASE
    # ========================================
    with sprint2_tabs[2]:
        st.markdown("### 💊 Payload Release & Bioavailability")
        st.caption("Predict drug release kinetics and intracellular bioavailability")
        
        if st.checkbox("Show detailed release analysis", key="release_detail"):
            display_payload_release_widget(d)
        else:
            release_result = predict_payload_release(d)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Bioavailability", f"{release_result['intracellular_bioavailability']:.1f}%")
            with col2:
                st.metric("24-Hour Release", f"{release_result['sustained_release_24h']:.1f}%")
            with col3:
                st.metric("Time to 50%", f"{release_result['time_to_50_release']:.1f} hrs")
            
            st.markdown(f"**Mechanism:** {release_result['release_mechanism']}")
            st.markdown(f"**Optimal Dosing:** {release_result['optimal_dosing_interval']}")
    
    # ========================================
    # SPRINT 2.4: TUMOR MICROENVIRONMENT
    # ========================================
    with sprint2_tabs[3]:
        st.markdown("### 🏥 Tumor Microenvironment Interactions")
        st.caption(f"Predict behavior in {selected_disease} tumor microenvironment")
        
        if st.checkbox("Show detailed tumor analysis", key="tumor_detail"):
            display_tumor_microenvironment_widget(d, disease_context)
        else:
            tumor_result = predict_tumor_microenvironment_interactions(d, disease_context)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("ECM Penetration", f"{tumor_result['extracellular_matrix_penetration']:.1f}%")
            with col2:
                st.metric("Tumor Accumulation", f"{tumor_result['tumor_accumulation']:.1f}%")
            with col3:
                st.metric("Penetration Depth", f"{tumor_result['penetration_depth']:.0f} μm")
            
            st.markdown("**Microenvironment Challenges:**")
            for component, interaction in tumor_result['interactions'].items():
                st.write(f"• **{component}**: {interaction}")
    
    # ========================================
    # SPRINT 2.5: IMMUNE RESPONSE
    # ========================================
    with sprint2_tabs[4]:
        st.markdown("### 🛡️ Immune System Response")
        st.caption("Predict immune recognition and activation")
        
        if st.checkbox("Show detailed immune analysis", key="immune_detail"):
            display_immune_response_widget(d)
        else:
            immune_result = predict_immune_response(d)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("MPS Capture Risk", f"{immune_result['mps_capture']:.1f}%")
            with col2:
                st.metric("Immune Evasion", f"{immune_result['immune_evasion_score']:.1f}%")
            with col3:
                st.metric("Danger Level", immune_result['material_danger_level'])
            
            st.markdown("**Immune Components:**")
            for component, level in immune_result['immune_components'].items():
                st.write(f"• **{component}**: {level:.1f}%")
    
    st.divider()
    
    # ========================================
    # SPRINT 2 OVERALL SCORE
    # ========================================
    st.markdown("### 🎯 Sprint 2 Cellular & Immune Score")
    
    # Recalculate all Sprint 2 metrics
    uptake = predict_cellular_uptake(d)
    trafficking = predict_intracellular_trafficking(d)
    release = predict_payload_release(d)
    tumor = predict_tumor_microenvironment_interactions(d, disease_context)
    immune = predict_immune_response(d)
    
    # Calculate composite score
    sprint2_score = (
        uptake['uptake_score'] * 0.15 +
        trafficking['trafficking_score'] * 0.15 +
        release['bioavailability_score'] * 0.20 +
        tumor['tumor_score'] * 0.30 +
        immune['immune_evasion_score'] * 0.20
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_sprint2 = go.Figure(data=[go.Indicator(
            mode="gauge+number+delta",
            value=sprint2_score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Sprint 2 Score"},
            delta={"reference": 75, "suffix": " vs target"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "darkgreen"},
                "steps": [
                    {"range": [0, 30], "color": "rgba(255, 100, 100, 0.3)"},
                    {"range": [30, 60], "color": "rgba(255, 200, 0, 0.3)"},
                    {"range": [60, 80], "color": "rgba(150, 255, 100, 0.3)"},
                    {"range": [80, 100], "color": "rgba(100, 255, 100, 0.3)"}
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 75
                }
            }
        )])
        
        fig_sprint2.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_sprint2, use_container_width=True, key=f"sprint2_score_{sprint2_score:.1f}")
    
    with col2:
        st.markdown("### 📊 Component Scores")
        st.metric("Uptake", f"{uptake['uptake_score']:.0f}/100")
        st.metric("Trafficking", f"{trafficking['trafficking_score']:.0f}/100")
        st.metric("Release", f"{release['bioavailability_score']:.0f}/100")
        st.metric("Tumor", f"{tumor['tumor_score']:.0f}/100")
        st.metric("Immune", f"{immune['immune_evasion_score']:.0f}/100")
    
    st.divider()

# ============================================================================
# TAB 7: SPRINT 3 - RESEARCH GRADE ASSESSMENT
# ============================================================================

with tab7:
    st.subheader("🚀 Sprint 3: Research Grade & Commercial Readiness")
    
    st.markdown("""
    **Comprehensive research-to-market readiness assessment** for next-generation studies.
    
    Sprint 3 evaluates publication potential, manufacturing feasibility, stability infrastructure, 
    quality control requirements, environmental impact, reproducibility, cost projections, 
    literature positioning, and intellectual property landscape.
    """)
    
    st.divider()
    
    # ========================================
    # INTERACTIVE CONTROLS FOR SPRINT 3 OPTIMIZATION
    # ========================================
    st.markdown("### 🎚️ Optimize Parameters for Research Grade")
    st.caption("✨ Adjust key parameters below - all 9 research metrics update automatically")
    
    # Main optimization controls
    opt_col1, opt_col2, opt_col3 = st.columns(3)
    
    with opt_col1:
        st.markdown("#### 📏 Size Optimization")
        d["Size"] = st.slider(
            "Size (nm) for Research Grade",
            min_value=20,
            max_value=300,
            value=int(d.get("Size", 100)),
            step=10,
            key="sprint3_size_opt",
            help="Optimal 80-150nm for publication and manufacturing"
        )
        st.caption("💡 100nm = Gold standard")
    
    with opt_col2:
        st.markdown("#### 🔴 Charge for Stability")
        d["Charge"] = st.slider(
            "Charge (mV) for Stability",
            min_value=-50,
            max_value=50,
            value=int(d.get("Charge", -5)),
            step=5,
            key="sprint3_charge_opt",
            help="More stable around ±5 to ±20 mV"
        )
        st.caption("💡 Balance between uptake & safety")
    
    with opt_col3:
        st.markdown("#### 🧬 Material Selection")
        material_options = list(AVAILABLE_MATERIALS)
        current_material = d.get("Material", "Lipid NP")
        try:
            material_index = material_options.index(current_material)
        except ValueError:
            material_index = 0
        
        d["Material"] = st.selectbox(
            "Material for Manufacturability",
            material_options,
            index=material_index,
            key="sprint3_material_opt",
            help="Affects scalability, cost, environmental impact"
        )
    
    # Advanced controls for research optimization
    with st.expander("⚙️ Research Optimization (Advanced)", expanded=False):
        adv_col1, adv_col2, adv_col3 = st.columns(3)
        
        with adv_col1:
            st.markdown("**PEG Density** (Publication impact)")
            d["PEG_Density"] = st.slider(
                "PEG Density for Publication",
                min_value=0,
                max_value=100,
                value=int(d.get("PEG_Density", 50)),
                step=5,
                key="sprint3_peg_opt",
                help="Higher PEG = more novel publication + better stability"
            )
        
        with adv_col2:
            st.markdown("**Ligand for Novelty**")
            ligand_options = get_all_ligands() + ["None"]
            current_ligand = d.get("Ligand", "None")
            try:
                ligand_index = ligand_options.index(current_ligand)
            except ValueError:
                ligand_index = ligand_options.index("None")
            
            d["Ligand"] = st.selectbox(
                "Targeting Ligand (Increases Novelty)",
                ligand_options,
                index=ligand_index,
                key="sprint3_ligand_opt",
                help="Specific ligand targeting enhances publication novelty"
            )
        
        with adv_col3:
            st.markdown("**Encapsulation Method**")
            encapsulation_options = ["Passive Loading", "Active Loading", "Electroporation", 
                                   "Hydrodynamic Injection", "Microfluidic", "Emulsification"]
            current_encaps = d.get("EncapsulationMethod", "Passive Loading")
            try:
                encaps_index = encapsulation_options.index(current_encaps)
            except ValueError:
                encaps_index = 0
            
            d["EncapsulationMethod"] = st.selectbox(
                "Encapsulation Method (Manufacturing Impact)",
                encapsulation_options,
                index=encaps_index,
                key="sprint3_encaps_opt",
                help="Advanced methods increase complexity but provide novelty"
            )
    
    # Sync design changes
    st.session_state.design = d
    
    st.divider()
    
    # Create 9 sub-tabs for Sprint 3 components
    sprint3_tabs = st.tabs([
        "📚 Publication Readiness",
        "🏭 Manufacturing Scalability",
        "📦 Stability & Storage",
        "✅ Batch QC",
        "🌍 Environmental Impact",
        "🔄 Reproducibility",
        "💰 Cost Analysis",
        "📖 Literature Comparison",
        "⚖️ Intellectual Property"
    ])
    
    # ========================================
    # SPRINT 3.1: PUBLICATION READINESS
    # ========================================
    with sprint3_tabs[0]:
        st.markdown("### 📚 Publication Readiness Assessment")
        st.caption("Evaluate data completeness and publication potential")
        
        if st.checkbox("Show detailed analysis##pub", key="pub_detail"):
            display_publication_readiness_widget(d)
        else:
            pub_result = predict_publication_readiness(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Data Completeness", f"{pub_result['data_completeness']:.0f}%")
            with col2:
                st.metric("Statistical Power", f"{pub_result['statistical_power']:.0f}%")
            with col3:
                st.metric("Novelty Score", f"{pub_result['novelty_score']:.0f}%")
            with col4:
                st.metric("Readiness", pub_result['readiness_level'])
    
    # ========================================
    # SPRINT 3.2: MANUFACTURING SCALABILITY
    # ========================================
    with sprint3_tabs[1]:
        st.markdown("### 🏭 Manufacturing Scalability")
        st.caption("Assess production feasibility and scaling potential")
        
        if st.checkbox("Show detailed analysis##mfg", key="mfg_detail"):
            display_manufacturing_scalability_widget(d)
        else:
            mfg_result = predict_manufacturing_scalability(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Production Feasibility", f"{mfg_result['production_feasibility']:.0f}%")
            with col2:
                st.metric("GMP Readiness", f"{mfg_result['gmp_readiness']:.0f}%")
            with col3:
                st.metric("Cost/Dose", f"${mfg_result['cost_per_dose_usd']:.2f}")
            with col4:
                st.metric("Scalability", mfg_result['scalability_level'])
    
    # ========================================
    # SPRINT 3.3: STABILITY & STORAGE
    # ========================================
    with sprint3_tabs[2]:
        st.markdown("### 📦 Stability & Storage")
        st.caption("Predict shelf-life and storage requirements")
        
        if st.checkbox("Show detailed analysis##stab", key="stab_detail"):
            display_stability_storage_widget(d)
        else:
            stab_result = predict_stability_storage(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Shelf-Life (25°C)", f"{stab_result['shelf_life_25c_months']:.0f}m")
            with col2:
                st.metric("Shelf-Life (4°C)", f"{stab_result['shelf_life_4c_months']:.0f}m")
            with col3:
                st.metric("Stability Score", f"{stab_result['stability_score']:.0f}/100")
            with col4:
                st.metric("Recommended", stab_result['recommended_storage'])
    
    # ========================================
    # SPRINT 3.4: BATCH QUALITY CONTROL
    # ========================================
    with sprint3_tabs[3]:
        st.markdown("### ✅ Batch Quality Control")
        st.caption("Define QC parameters and release criteria")
        
        if st.checkbox("Show detailed analysis##qc", key="qc_detail"):
            display_batch_quality_control_widget(d)
        else:
            qc_result = predict_batch_quality_control(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("QC Score", f"{qc_result['total_qc_score']:.0f}/100")
            with col2:
                st.metric("Release Rate", f"{qc_result['total_release_rate']:.0f}%")
            with col3:
                st.metric("Batch Consistency", f"{qc_result['batch_consistency_score']:.1f}%")
            with col4:
                st.metric("GMP Compliance", f"{qc_result['gmp_compliance_level']:.0f}%")
    
    # ========================================
    # SPRINT 3.5: ENVIRONMENTAL IMPACT
    # ========================================
    with sprint3_tabs[4]:
        st.markdown("### 🌍 Environmental Impact")
        st.caption("Assess biodegradability and sustainability")
        
        if st.checkbox("Show detailed analysis##env", key="env_detail"):
            display_environmental_impact_widget(d)
        else:
            env_result = predict_environmental_impact(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Sustainability", f"{env_result['sustainability_score']:.0f}/100")
            with col2:
                st.metric("Biodegradability", f"{env_result['biodegradability']:.0f}%")
            with col3:
                st.metric("Carbon Footprint", f"{env_result['carbon_footprint_kg']:.2f}kg")
            with col4:
                st.metric("Classification", env_result['environmental_classification'][:5])
    
    # ========================================
    # SPRINT 3.6: REPRODUCIBILITY
    # ========================================
    with sprint3_tabs[5]:
        st.markdown("### 🔄 Reproducibility Assessment")
        st.caption("Evaluate design reproducibility across labs")
        
        if st.checkbox("Show detailed analysis##repro", key="repro_detail"):
            display_reproducibility_assessment_widget(d)
        else:
            repro_result = predict_reproducibility_assessment(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Reproducibility", f"{repro_result['reproducibility_score']:.0f}/100")
            with col2:
                st.metric("Batch Variation", f"±{repro_result['batch_to_batch_variation']:.1f}%")
            with col3:
                st.metric("Critical Params", len(repro_result['critical_parameters']))
            with col4:
                st.metric("Difficulty", repro_result['difficulty_level'][:5])
    
    # ========================================
    # SPRINT 3.7: COST ANALYSIS
    # ========================================
    with sprint3_tabs[6]:
        st.markdown("### 💰 Cost Analysis")
        st.caption("Project manufacturing and development costs")
        
        if st.checkbox("Show detailed analysis##cost", key="cost_detail"):
            display_cost_analysis_widget(d)
        else:
            cost_result = predict_cost_analysis(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("COGS (10mg)", f"${cost_result['cost_per_dose_10mg_usd']:.2f}")
            with col2:
                st.metric("Dev Cost", f"${cost_result['development_cost_total']:,.0f}")
            with col3:
                st.metric("Gross Margin", f"{cost_result['gross_margin_percent']:.1f}%")
            with col4:
                st.metric("Timeline", f"{cost_result['total_timeline_months']}mo")
    
    # ========================================
    # SPRINT 3.8: LITERATURE COMPARISON
    # ========================================
    with sprint3_tabs[7]:
        st.markdown("### 📖 Literature Comparison")
        st.caption("Compare design against published benchmarks")
        
        if st.checkbox("Show detailed analysis##lit", key="lit_detail"):
            display_literature_comparison_widget(d)
        else:
            lit_result = predict_literature_comparison(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Novelty Score", f"{lit_result['novelty_score']:.0f}/100")
            with col2:
                st.metric("Predicted Citations", f"{lit_result['predicted_citations']:,}")
            with col3:
                st.metric("Size Deviation", f"{lit_result['size_deviation_percent']:.1f}%")
            with col4:
                st.metric("Applications", len(lit_result['typical_applications']))
    
    # ========================================
    # SPRINT 3.9: INTELLECTUAL PROPERTY
    # ========================================
    with sprint3_tabs[8]:
        st.markdown("### ⚖️ Intellectual Property")
        st.caption("Assess patent landscape and novelty")
        
        if st.checkbox("Show detailed analysis##ip", key="ip_detail"):
            display_intellectual_property_widget(d)
        else:
            ip_result = predict_intellectual_property(d)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Novelty Score", f"{ip_result['novelty_score']:.0f}/100")
            with col2:
                st.metric("Patent Likelihood", f"{ip_result['patent_likelihood_percent']}%")
            with col3:
                st.metric("Freedom to Operate", f"{ip_result['freedom_to_operate']}/100")
            with col4:
                st.metric("Threat Level", ip_result['threat_level'][:7])
    
    st.divider()
    
    # ========================================
    # SPRINT 3 OVERALL SCORE
    # ========================================
    st.markdown("### 🎯 Sprint 3 Research Grade Overall Score")
    
    # Recalculate all Sprint 3 metrics
    pub = predict_publication_readiness(d)
    mfg = predict_manufacturing_scalability(d)
    stab = predict_stability_storage(d)
    qc = predict_batch_quality_control(d)
    env = predict_environmental_impact(d)
    repro = predict_reproducibility_assessment(d)
    cost = predict_cost_analysis(d)
    lit = predict_literature_comparison(d)
    ip = predict_intellectual_property(d)
    
    # Calculate composite score
    sprint3_score = (
        pub['readiness_score'] * 0.12 +
        mfg['scalability_score'] * 0.13 +
        stab['stability_score'] * 0.11 +
        qc['total_qc_score'] * 0.12 +
        env['sustainability_score'] * 0.10 +
        repro['reproducibility_score'] * 0.12 +
        (100 - (cost['payback_period_months'] / 120 * 100)) * 0.10 +  # Cost factor
        lit['novelty_score'] * 0.10 +
        ip['novelty_score'] * 0.10
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_sprint3 = go.Figure(data=[go.Indicator(
            mode="gauge+number+delta",
            value=sprint3_score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Sprint 3 Research Grade Score"},
            delta={"reference": 75, "suffix": " vs target"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "darkblue"},
                "steps": [
                    {"range": [0, 30], "color": "rgba(255, 100, 100, 0.3)"},
                    {"range": [30, 60], "color": "rgba(255, 200, 0, 0.3)"},
                    {"range": [60, 80], "color": "rgba(150, 255, 100, 0.3)"},
                    {"range": [80, 100], "color": "rgba(100, 255, 100, 0.3)"}
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 75
                }
            }
        )])
        
        fig_sprint3.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_sprint3, use_container_width=True, key=f"sprint3_score_{sprint3_score:.1f}")
    
    with col2:
        st.markdown("### 📊 Component Scores")
        st.metric("Publication", f"{pub['readiness_score']:.0f}/100")
        st.metric("Manufacturing", f"{mfg['scalability_score']:.0f}/100")
        st.metric("Stability", f"{stab['stability_score']:.0f}/100")
        st.metric("QC", f"{qc['total_qc_score']:.0f}/100")


# Ensure all changes to 'd' are saved back to session state
st.session_state.design = d

st.divider()

# Navigation buttons
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Disease Selection", use_container_width=True):
        from streamlit_auth import switch_page_with_token
        switch_page_with_token("pages/0_Disease_Selection.py")

with col2:
    if st.button("Next: Run Simulation →", type="primary", use_container_width=True):
        st.session_state.parameters_configured = True
        from streamlit_auth import switch_page_with_token
        switch_page_with_token("pages/2_Run_Simulation.py")

with col3:
    if st.button("Save Design", use_container_width=True):
        st.session_state.design_saved = True
        st.success("✅ Design saved to your profile")

