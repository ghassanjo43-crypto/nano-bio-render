"""
Sprint 2: Intracellular Trafficking Predictor
Models where nanoparticles go inside cells
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_intracellular_trafficking(design_params):
    """
    Predict intracellular localization and trafficking pathways
    
    Returns:
    {
        "primary_location": str,
        "location_distribution": dict,
        "endosomal_escape": float (0-100),
        "escape_mechanism": str,
        "cytoplasmic_access": float (0-100),
        "nuclear_localization": float (0-100),
        "trafficking_time": float (hours),
        "lysosomal_degradation": float (0-100),
        "retention_time": float (hours),
        "trafficking_score": float (0-100),
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
    surface_coating = design_params.get("SurfaceCoating", [])
    
    # Location distribution based on endocytic pathway
    # Most particles end up in endosomes initially
    
    # 1. Endosomal entrapment (negative for cytoplasmic delivery)
    # Cationic particles tend to escape better
    charge_abs = abs(charge)
    if charge > 5:
        endosomal_escape = 65 + min(25, charge_abs * 1.5)  # Up to 90%
        escape_mechanism = "Proton-sponge effect (cationic charge)"
    elif charge < -5:
        endosomal_escape = max(25, 50 - charge_abs * 0.5)  # 25-50%
        escape_mechanism = "Anionic lipid destabilization"
    else:
        endosomal_escape = 35
        escape_mechanism = "Neutral - limited escape"
    
    # Material effect on endosomal escape
    material_escape_rates = {
        "Lipid NP": {"base": 50, "mechanism": "Lipid bilayer disruption"},
        "PLGA": {"base": 35, "mechanism": "Polymer degradation"},
        "DNA Origami": {"base": 45, "mechanism": "pH-sensitive destabilization"},
        "Liposome": {"base": 55, "mechanism": "Membrane fusion"},
        "Gold NP": {"base": 20, "mechanism": "Limited escape"},
        "Silica NP": {"base": 15, "mechanism": "Minimal escape"},
        "Polymeric NP": {"base": 30, "mechanism": "Hydrolysis"},
        "Albumin NP": {"base": 40, "mechanism": "Protein dissociation"},
    }
    
    material_info = material_escape_rates.get(material, {"base": 30, "mechanism": "Unknown"})
    endosomal_escape = (endosomal_escape * 0.5 + material_info["base"] * 0.5)
    
    # PEGylation reduces escape (coating effect)
    if peg_density > 10:
        endosomal_escape *= (1 - (peg_density / 100) * 0.2)
    
    # Size effect on trafficking
    if 50 <= size <= 150:
        trafficking_efficiency = 85
    elif size < 50:
        trafficking_efficiency = 100 - (50 - size) * 0.5  # Small particles diffuse freely
    else:
        trafficking_efficiency = max(30, 100 - (size - 150) * 0.2)  # Large particles get stuck
    
    # 2. Cytoplasmic access (requires endosomal escape)
    cytoplasmic_access = endosomal_escape * 0.9  # Some loss to degradation
    
    # 3. Nuclear localization (very few particles achieve this)
    # Requires small size (<50nm) and specific NLS sequences
    nuclear_uptake_base = max(0, (50 - size) / 50 * 30) if size < 50 else 0
    
    # Ligand-targeted particles rarely reach nucleus
    if ligand != "None":
        nuclear_uptake_base *= 0.3
    
    nuclear_localization = nuclear_uptake_base
    
    # 4. Location distribution
    escaped_fraction = cytoplasmic_access / 100
    endosomal_fraction = (100 - cytoplasmic_access) * 0.7 / 100
    lysosomal_fraction = (100 - cytoplasmic_access) * 0.3 / 100
    
    location_distribution = {
        "Endosomes": max(0, 30 * (1 - escaped_fraction)),
        "Cytoplasm": cytoplasmic_access * 0.8,
        "Lysosomes": lysosomal_fraction * 100,
        "Nucleus": nuclear_localization,
        "Plasma Membrane": 5,
        "Other": max(0, 100 - (cytoplasmic_access * 0.8 + nuclear_localization + lysosomal_fraction * 100 + 35))
    }
    
    # Normalize
    total = sum(location_distribution.values())
    if total > 0:
        location_distribution = {k: v * 100 / total for k, v in location_distribution.items()}
    
    # Determine primary location
    primary_location = max(location_distribution, key=location_distribution.get)
    
    # 5. Trafficking time (minutes to hours)
    base_trafficking_time = 0.5 + (100 - trafficking_efficiency) / 50
    trafficking_time = base_trafficking_time + (size / 100) * 0.5  # Larger particles take longer
    
    # 6. Lysosomal degradation risk
    # High for anionic particles and polymers
    if charge < -10:
        lysosomal_degradation = 75
    elif charge > 5:
        lysosomal_degradation = 45
    else:
        lysosomal_degradation = 60
    
    # Material effect
    material_degradation = {
        "Lipid NP": 40,
        "PLGA": 65,
        "DNA Origami": 55,
        "Liposome": 35,
        "Gold NP": 5,
        "Silica NP": 10,
        "Polymeric NP": 70,
        "Albumin NP": 50,
    }
    
    lysosomal_degradation = (lysosomal_degradation * 0.4 + material_degradation.get(material, 50) * 0.6)
    
    # 7. Retention time (hours until clearance)
    if cytoplasmic_access > 70:
        retention_time = 12 + (nuclear_localization / 10)  # Longer if in nucleus/cytoplasm
    elif lysosomal_degradation > 70:
        retention_time = 2  # Quickly degraded
    else:
        retention_time = 4  # Moderate retention in endosomes
    
    # 8. Trafficking score
    trafficking_score = (
        (trafficking_efficiency * 0.25) +
        (cytoplasmic_access * 0.35) +
        (nuclear_localization * 0.15) +
        ((100 - lysosomal_degradation) * 0.25)
    )
    trafficking_score = min(100, max(0, trafficking_score))
    
    return {
        "primary_location": primary_location,
        "location_distribution": location_distribution,
        "endosomal_escape": endosomal_escape,
        "escape_mechanism": escape_mechanism,
        "cytoplasmic_access": cytoplasmic_access,
        "nuclear_localization": nuclear_localization,
        "trafficking_time": trafficking_time,
        "lysosomal_degradation": lysosomal_degradation,
        "retention_time": retention_time,
        "trafficking_score": trafficking_score,
        "trafficking_efficiency": trafficking_efficiency,
    }


def display_intracellular_trafficking_widget(design_params):
    """Display intracellular trafficking analysis"""
    
    result = predict_intracellular_trafficking(design_params)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Endosomal Escape",
            f"{result['endosomal_escape']:.1f}%",
            help="Ability to escape endosomal compartment"
        )
    
    with col2:
        st.metric(
            "Cytoplasmic Access",
            f"{result['cytoplasmic_access']:.1f}%",
            help="Fraction reaching cytoplasm"
        )
    
    with col3:
        st.metric(
            "Retention Time",
            f"{result['retention_time']:.1f} hrs",
            help="How long particles persist in cell"
        )
    
    with col4:
        st.metric(
            "Trafficking Score",
            f"{result['trafficking_score']:.0f}/100",
            help="Overall intracellular trafficking potential"
        )
    
    st.markdown("**Escape Mechanism:**")
    st.write(f"🔹 {result['escape_mechanism']}")
    
    # Location distribution pie chart
    st.markdown("**Predicted Intracellular Localization:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_location = go.Figure(data=[go.Pie(
            labels=list(result['location_distribution'].keys()),
            values=list(result['location_distribution'].values()),
            marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F']),
            hoverinfo="label+percent+value"
        )])
        fig_location.update_layout(
            height=350,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_location, use_container_width=True)
    
    with col2:
        st.markdown("**Key Trafficking Metrics:**")
        
        trafficking_data = {
            "Metric": ["Endosomal Escape", "Cytoplasmic Access", "Nuclear Access", "Lysosomal Risk"],
            "Value (%)": [
                f"{result['endosomal_escape']:.1f}",
                f"{result['cytoplasmic_access']:.1f}",
                f"{result['nuclear_localization']:.1f}",
                f"{result['lysosomal_degradation']:.1f}"
            ],
            "Status": [
                "🟢" if result['endosomal_escape'] > 60 else "🟡" if result['endosomal_escape'] > 40 else "🔴",
                "🟢" if result['cytoplasmic_access'] > 70 else "🟡" if result['cytoplasmic_access'] > 50 else "🔴",
                "🟢" if result['nuclear_localization'] > 20 else "🟡" if result['nuclear_localization'] > 5 else "⚪",
                "🟢" if result['lysosomal_degradation'] < 40 else "🟡" if result['lysosomal_degradation'] < 60 else "🔴"
            ]
        }
        
        df_trafficking = pd.DataFrame(trafficking_data)
        st.dataframe(df_trafficking, use_container_width=True, hide_index=True)
    
    # Timeline
    st.markdown("**Intracellular Journey Timeline:**")
    
    fig_timeline = go.Figure()
    
    stages = [
        ("Particle Uptake", 0, 0.2),
        ("Endosomal Trafficking", 0.2, result['endosomal_escape']/100 * 0.3),
        ("Escape/Degradation", 0.5, 0.2),
        ("Cytoplasmic/Lysosomal Fate", 0.7, 0.3),
    ]
    
    y_pos = 1
    for stage, x_start, width in stages:
        fig_timeline.add_trace(go.Bar(
            y=[stage],
            x=[width],
            orientation='h',
            marker=dict(color='#4ECDC4'),
            name=stage,
            hovertemplate=f"{stage}: %{{x:.1%}}<extra></extra>"
        ))
    
    fig_timeline.update_layout(
        barmode='stack',
        height=250,
        showlegend=False,
        xaxis_title="Relative Time",
        yaxis_title="Trafficking Stage",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    
    st.plotly_chart(fig_timeline, use_container_width=True)


if __name__ == "__main__":
    test_design = {
        "Size": 95,
        "Charge": 8,
        "Material": "Lipid NP",
        "Ligand": "GalNAc",
        "PEGDensity": 5,
        "Hydrophobicity": 1.5,
        "SurfaceCoating": []
    }
    
    result = predict_intracellular_trafficking(test_design)
    print(f"Primary Location: {result['primary_location']}")
    print(f"Endosomal Escape: {result['endosomal_escape']:.1f}%")
    print(f"Trafficking Score: {result['trafficking_score']:.0f}/100")
