"""
Sprint 2: Tumor Microenvironment Interactions Predictor
Models nanoparticle behavior in the tumor microenvironment
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_tumor_microenvironment_interactions(design_params, disease_context="HCC"):
    """
    Predict nanoparticle behavior in tumor microenvironment
    
    Returns:
    {
        "extracellular_matrix_penetration": float (0-100),
        "hypoxia_stability": float (0-100),
        "acidic_microenv_stability": float (0-100),
        "ecm_degradation_risk": float (0-100),
        "vascular_permeability": float (0-100),
        "tumor_accumulation": float (0-100),
        "penetration_depth": float (micrometers),
        "interactions": dict,
        "tumor_score": float (0-100),
    }
    """
    
    size = design_params.get("Size", 100)
    charge = design_params.get("Charge", -5)
    material = design_params.get("Material", "Lipid NP")
    ligand = design_params.get("Ligand", "None")
    peg_density = design_params.get("PEGDensity") or design_params.get("PEG_Density") or 50
    if peg_density is None:
        peg_density = 50
    hydrophobicity = design_params.get("Hydrophobicity", 1.5)
    
    # Disease-specific microenvironment
    disease_params = {
        "HCC": {
            "ecm_density": "High",
            "fibrosis_level": "Moderate-High",
            "immune_infiltration": "Low-Moderate",
            "hypoxia_level": "Moderate",
            "ph": 6.8,
            "vessel_density": 0.8,
        },
        "PDAC": {
            "ecm_density": "Very High",
            "fibrosis_level": "High",
            "immune_infiltration": "Low",
            "hypoxia_level": "High",
            "ph": 6.5,
            "vessel_density": 0.3,
        },
        "Melanoma": {
            "ecm_density": "Moderate",
            "fibrosis_level": "Moderate",
            "immune_infiltration": "High",
            "hypoxia_level": "Low-Moderate",
            "ph": 6.9,
            "vessel_density": 1.0,
        },
        "Breast": {
            "ecm_density": "Moderate-High",
            "fibrosis_level": "Moderate",
            "immune_infiltration": "Moderate",
            "hypoxia_level": "Moderate",
            "ph": 7.0,
            "vessel_density": 0.9,
        }
    }
    
    disease_info = disease_params.get(disease_context, disease_params["HCC"])
    
    # 1. ECM Penetration (EPR effect optimization)
    # Optimal size 50-150nm for EPR effect
    if 50 <= size <= 150:
        epr_efficiency = 100 * np.exp(-((size - 100) ** 2) / (2 * 30 ** 2))
    elif size < 50:
        epr_efficiency = 60  # Too small, escapes through vasculature
    else:
        epr_efficiency = max(20, 100 - (size - 150) * 0.5)  # Too large, can't extravasate
    
    # PEGylation improves EPR effect
    if peg_density > 5:
        epr_efficiency *= (1 + (peg_density / 100) * 0.3)  # +30% max
    
    epr_efficiency = min(100, epr_efficiency)
    
    # ECM density effects
    ecm_penetration_base = {
        "High": 0.6,
        "Moderate-High": 0.75,
        "Moderate": 0.85,
        "Low-Moderate": 0.9,
        "Low": 0.95,
    }
    
    ecm_factor = ecm_penetration_base.get(disease_info["ecm_density"], 0.75)
    extracellular_matrix_penetration = epr_efficiency * ecm_factor
    
    # 2. Hypoxia Stability (low oxygen resistance)
    # Size effect on hypoxia tolerance
    if size < 150:
        hypoxia_base = 70
    else:
        hypoxia_base = 50
    
    # Material hypoxia resistance
    material_hypoxia = {
        "Lipid NP": 75,
        "PLGA": 65,
        "DNA Origami": 55,
        "Liposome": 70,
        "Gold NP": 95,
        "Silica NP": 90,
        "Polymeric NP": 60,
        "Albumin NP": 50,
    }
    
    hypoxia_stability = (hypoxia_base * 0.5 + material_hypoxia.get(material, 65) * 0.5)
    
    # Hypoxia level adjustment
    hypoxia_level_factor = {
        "High": 0.7,
        "High-Moderate": 0.8,
        "Moderate": 0.9,
        "Low-Moderate": 0.95,
        "Low": 1.0,
    }
    
    hypoxia_stability *= hypoxia_level_factor.get(disease_info["hypoxia_level"], 0.85)
    hypoxia_stability = min(100, max(0, hypoxia_stability))
    
    # 3. Acidic Microenvironment Stability
    tumor_ph = disease_info["ph"]
    
    # pH-dependent stability
    if 6.5 <= tumor_ph <= 7.2:
        ph_effect_base = 80
    elif tumor_ph < 6.5:
        ph_effect_base = max(50, 100 - (6.5 - tumor_ph) * 30)  # Very acidic = worse
    else:
        ph_effect_base = 70
    
    # Material pH resistance
    material_ph_resistance = {
        "Lipid NP": 75,
        "PLGA": 85,  # Good pH resistance
        "DNA Origami": 70,
        "Liposome": 60,
        "Gold NP": 98,
        "Silica NP": 92,
        "Polymeric NP": 80,
        "Albumin NP": 65,
    }
    
    acidic_microenv_stability = (ph_effect_base * 0.5 + material_ph_resistance.get(material, 75) * 0.5)
    acidic_microenv_stability = min(100, max(0, acidic_microenv_stability))
    
    # 4. ECM Degradation Risk (exposure to MMPs, collagenase)
    charge_abs = abs(charge)
    
    # Charged particles more likely degraded
    if charge_abs < 10:
        ecm_degrad_base = 50
    elif charge_abs < 30:
        ecm_degrad_base = 60
    else:
        ecm_degrad_base = 75  # High charge = higher degradation
    
    # Fibrosis increases degradation risk (more proteases)
    fibrosis_factor = {
        "Low": 0.8,
        "Moderate": 1.0,
        "Moderate-High": 1.2,
        "High": 1.5,
        "Very High": 1.8,
    }
    
    ecm_degradation_risk = ecm_degrad_base * fibrosis_factor.get(disease_info["fibrosis_level"], 1.0)
    ecm_degradation_risk = min(100, ecm_degradation_risk)
    
    # 5. Vascular Permeability & Accumulation
    # Vessel density affects accumulation
    vessel_factor = disease_info["vessel_density"]  # 0-1 scale
    
    vascular_permeability = 60 + (vessel_factor * 40)  # 60-100%
    
    # Tumor accumulation (combination of EPR, targeting, and retention)
    if ligand != "None":
        targeting_factor = 1.3
    else:
        targeting_factor = 1.0
    
    tumor_accumulation = (extracellular_matrix_penetration * 0.4 +
                         vascular_permeability * 0.3 +
                         acidic_microenv_stability * 0.2 +
                         targeting_factor * 0.1 * 100)
    
    tumor_accumulation = min(100, tumor_accumulation)
    
    # 6. Penetration Depth (micrometers into tumor)
    # Based on EPR and ECM penetration
    penetration_efficiency = extracellular_matrix_penetration / 100
    
    if 50 <= size <= 100:
        max_depth = 300  # micrometers
    elif 100 <= size <= 150:
        max_depth = 250
    elif size < 50:
        max_depth = 150  # Too small, doesn't penetrate well
    else:
        max_depth = 100  # Too large, can't penetrate
    
    penetration_depth = max_depth * penetration_efficiency
    
    # 7. Tumor microenvironment interactions
    interactions = {
        "ECM Matrix": f"{'Limited' if extracellular_matrix_penetration < 50 else 'Moderate' if extracellular_matrix_penetration < 75 else 'Good'} interaction",
        "Acidic pH": f"{'Poor' if acidic_microenv_stability < 50 else 'Moderate' if acidic_microenv_stability < 75 else 'Excellent'} stability",
        "Hypoxia": f"{'Poor' if hypoxia_stability < 50 else 'Moderate' if hypoxia_stability < 75 else 'Excellent'} tolerance",
        "Fibrosis": f"{'Very High' if ecm_degradation_risk > 75 else 'High' if ecm_degradation_risk > 50 else 'Moderate'} degradation risk",
        "Vessel Density": f"{disease_info['vessel_density']:.1f} (Disease-dependent)",
    }
    
    # 8. Overall tumor interaction score
    tumor_score = (
        (extracellular_matrix_penetration * 0.25) +
        (hypoxia_stability * 0.20) +
        (acidic_microenv_stability * 0.20) +
        ((100 - ecm_degradation_risk) * 0.15) +
        (vascular_permeability * 0.20)
    )
    
    tumor_score = min(100, max(0, tumor_score))
    
    return {
        "extracellular_matrix_penetration": extracellular_matrix_penetration,
        "hypoxia_stability": hypoxia_stability,
        "acidic_microenv_stability": acidic_microenv_stability,
        "ecm_degradation_risk": ecm_degradation_risk,
        "vascular_permeability": vascular_permeability,
        "tumor_accumulation": tumor_accumulation,
        "penetration_depth": penetration_depth,
        "interactions": interactions,
        "tumor_score": tumor_score,
        "disease_context": disease_context,
        "disease_info": disease_info,
    }


def display_tumor_microenvironment_widget(design_params, disease_context="HCC"):
    """Display tumor microenvironment interactions"""
    
    result = predict_tumor_microenvironment_interactions(design_params, disease_context)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "ECM Penetration",
            f"{result['extracellular_matrix_penetration']:.1f}%",
            help="Ability to penetrate extracellular matrix"
        )
    
    with col2:
        st.metric(
            "Tumor Accumulation",
            f"{result['tumor_accumulation']:.1f}%",
            help="Predicted accumulation at tumor site"
        )
    
    with col3:
        st.metric(
            "Penetration Depth",
            f"{result['penetration_depth']:.0f} μm",
            help="Depth of tumor penetration"
        )
    
    with col4:
        st.metric(
            "Tumor Score",
            f"{result['tumor_score']:.0f}/100",
            help="Overall tumor interaction potential"
        )
    
    st.markdown(f"**Disease Context:** {result['disease_context']}")
    
    # Stability metrics
    st.markdown("**Microenvironment Stability Metrics:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        stability_metrics = {
            "Hypoxia": result['hypoxia_stability'],
            "Acidic pH": result['acidic_microenv_stability'],
            "Anti-ECM Degradation": 100 - result['ecm_degradation_risk'],
        }
        
        fig_stability = go.Figure(data=[go.Bar(
            x=list(stability_metrics.keys()),
            y=list(stability_metrics.values()),
            marker=dict(color=['#FF6B6B', '#FFA07A', '#4ECDC4']),
            text=[f"{v:.0f}%" for v in stability_metrics.values()],
            textposition="auto"
        )])
        
        fig_stability.update_layout(
            height=300,
            yaxis_title="Stability (%)",
            yaxis_range=[0, 105],
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False
        )
        
        st.plotly_chart(fig_stability, use_container_width=True)
    
    with col2:
        # Interactions table
        st.markdown("**Microenvironment Interactions:**")
        
        interaction_data = []
        for component, interaction in result['interactions'].items():
            interaction_data.append({"Component": component, "Interaction": interaction})
        
        df_interactions = pd.DataFrame(interaction_data)
        st.dataframe(df_interactions, use_container_width=True, hide_index=True)
    
    # Penetration visualization
    st.markdown("**Tumor Penetration Profile:**")
    
    penetration_profile = {
        "Depth (μm)": [0, 50, 100, 200, 300, 400, 500],
        "Particle Concentration (%)": [
            100,
            100 * np.exp(-0.01 * result['penetration_depth']/100),
            100 * np.exp(-0.01 * 100),
            100 * np.exp(-0.01 * 200),
            100 * np.exp(-0.01 * 300),
            100 * np.exp(-0.01 * 400),
            100 * np.exp(-0.01 * 500),
        ]
    }
    
    fig_penetration = go.Figure()
    
    fig_penetration.add_trace(go.Scatter(
        x=penetration_profile["Depth (μm)"],
        y=penetration_profile["Particle Concentration (%)"],
        mode='lines+markers',
        fill='tozeroy',
        name='Particle Distribution',
        line=dict(color='#4ECDC4', width=3),
        fillcolor='rgba(78, 205, 196, 0.2)'
    ))
    
    # Add penetration depth marker
    fig_penetration.add_vline(
        x=result['penetration_depth'],
        line_dash="dash",
        line_color="red",
        annotation_text=f"Max: {result['penetration_depth']:.0f}μm",
        annotation_position="top right"
    )
    
    fig_penetration.update_layout(
        title="Tumor Penetration Profile",
        xaxis_title="Depth into Tumor (μm)",
        yaxis_title="Relative Particle Concentration (%)",
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    
    st.plotly_chart(fig_penetration, use_container_width=True)


if __name__ == "__main__":
    test_design = {
        "Size": 100,
        "Charge": -5,
        "Material": "Lipid NP",
        "Ligand": "GalNAc",
        "PEGDensity": 10,
        "Hydrophobicity": 1.5,
    }
    
    result = predict_tumor_microenvironment_interactions(test_design, "HCC")
    print(f"ECM Penetration: {result['extracellular_matrix_penetration']:.1f}%")
    print(f"Tumor Accumulation: {result['tumor_accumulation']:.1f}%")
    print(f"Penetration Depth: {result['penetration_depth']:.0f} μm")
