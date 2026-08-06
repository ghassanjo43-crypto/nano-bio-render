"""
Sprint 2: Cellular Uptake & Internalization Predictor
Models how nanoparticles enter target cells
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_cellular_uptake(design_params):
    """
    Predict cellular uptake efficiency based on nanoparticle properties
    
    Returns:
    {
        "uptake_efficiency": float (0-100%),
        "uptake_mechanism": str,
        "uptake_pathway": str,
        "receptor_mediated": float,
        "nonspecific": float,
        "time_to_saturation": float (hours),
        "primary_drivers": list,
        "limiting_factors": list,
        "uptake_score": float (0-100)
    }
    """
    
    size = design_params.get("Size", 100)
    charge = design_params.get("Charge", -5)
    ligand = design_params.get("Ligand", "None")
    ligand_density = design_params.get("LigandDensity", 60)
    hydrophobicity = design_params.get("Hydrophobicity") or 1.5
    surface_coating = design_params.get("SurfaceCoating", [])
    if surface_coating is None:
        surface_coating = ["PEG (Stealth)"]
    material = design_params.get("Material", "Lipid NP")
    
    # Base uptake depends on size (optimal 50-150 nm)
    if 50 <= size <= 150:
        size_efficiency = 100 * np.exp(-((size - 100) ** 2) / (2 * 30 ** 2))
    elif size < 50:
        size_efficiency = 100 * (size / 50) * 0.8  # Too small
    else:
        size_efficiency = max(20, 100 - (size - 150) * 0.3)  # Decreases with size
    
    # Charge effect on uptake
    charge_abs = abs(charge)
    if charge_abs <= 10:
        charge_efficiency = 95  # Neutral is best
    elif charge_abs <= 30:
        charge_efficiency = 70 + (30 - charge_abs) * 0.5
    else:
        charge_efficiency = 40  # Too charged
    
    # Ligand-mediated uptake
    receptor_mediated = 0
    if ligand != "None":
        # Ligand increases receptor-mediated endocytosis
        receptor_mediated = 40 + (ligand_density / 100) * 50  # 40-90%
        nonspecific = 100 - receptor_mediated
    else:
        receptor_mediated = 0
        nonspecific = 60  # Pinocytosis, phagocytosis
    
    # Hydrophobicity affects membrane interactions
    if 0.5 <= hydrophobicity <= 2.5:
        hydro_efficiency = 90
    elif hydrophobicity < 0.5:
        hydro_efficiency = 60  # Too hydrophilic
    else:
        hydro_efficiency = max(50, 120 - hydrophobicity * 10)  # Too hydrophobic
    
    # PEGylation reduces uptake slightly (stealth effect)
    peg_reduction = 1.0
    if "PEG (Stealth)" in surface_coating:
        peg_density = design_params.get("PEGDensity") or design_params.get("PEG_Density", 50)
        if peg_density:
            peg_reduction = 1 - (peg_density / 100) * 0.25  # 0-25% reduction
    
    # Material-specific uptake rates
    material_uptake_rates = {
        "Lipid NP": 0.95,
        "PLGA": 0.88,
        "Gold NP": 0.75,
        "Silica NP": 0.70,
        "DNA Origami": 0.82,
        "Liposome": 0.92,
        "Polymeric NP": 0.85,
        "Albumin NP": 0.91,
    }
    material_factor = material_uptake_rates.get(material, 0.80)
    
    # Combine factors
    if receptor_mediated > 0:
        # Ligand-targeted: uses both receptor-mediated and some nonspecific
        total_efficiency = (receptor_mediated * 0.9 + nonspecific * 0.1) * (
            size_efficiency / 100 * charge_efficiency / 100 * hydro_efficiency / 100 * material_factor * peg_reduction
        )
        uptake_mechanism = f"Receptor-Mediated ({ligand})"
        primary_pathway = "Clathrin-coated pit endocytosis"
    else:
        # Non-targeted: mostly nonspecific
        total_efficiency = nonspecific * (
            size_efficiency / 100 * charge_efficiency / 100 * hydro_efficiency / 100 * material_factor * peg_reduction
        )
        uptake_mechanism = "Non-Specific Endocytosis"
        primary_pathway = "Macropinocytosis / Phagocytosis"
    
    total_efficiency = min(100, max(0, total_efficiency))
    
    # Time to saturation (in hours)
    # Faster for receptor-mediated uptake
    if receptor_mediated > 50:
        time_to_saturation = 1.5 + (100 - total_efficiency) / 30
    else:
        time_to_saturation = 3.0 + (100 - total_efficiency) / 20
    
    # Primary drivers
    primary_drivers = []
    if ligand != "None":
        primary_drivers.append(f"Strong ligand targeting ({ligand})")
    if 50 <= size <= 150:
        primary_drivers.append(f"Optimal size ({size} nm)")
    if abs(charge) <= 10:
        primary_drivers.append("Neutral charge balance")
    if 0.5 <= hydrophobicity <= 2.5:
        primary_drivers.append("Optimal hydrophobicity")
    
    if not primary_drivers:
        primary_drivers = ["Passive uptake mechanisms"]
    
    # Limiting factors
    limiting_factors = []
    if size < 50 or size > 200:
        limiting_factors.append(f"Suboptimal size ({size} nm)")
    if charge_abs > 30:
        limiting_factors.append("High surface charge inhibits uptake")
    if ligand == "None":
        limiting_factors.append("No active targeting ligand")
    if peg_reduction < 0.9:
        limiting_factors.append("PEGylation reduces cellular uptake")
    if hydrophobicity < 0.3 or hydrophobicity > 4:
        limiting_factors.append("Non-optimal hydrophobicity")
    
    # Calculate uptake score
    uptake_score = (
        (size_efficiency * 0.25) +
        (charge_efficiency * 0.20) +
        (hydro_efficiency * 0.15) +
        (receptor_mediated if ligand != "None" else nonspecific) * 0.3 +
        (material_factor * 0.10) * 100
    )
    uptake_score = min(100, max(0, uptake_score))
    
    return {
        "uptake_efficiency": total_efficiency,
        "uptake_mechanism": uptake_mechanism,
        "uptake_pathway": primary_pathway,
        "receptor_mediated": receptor_mediated,
        "nonspecific": nonspecific,
        "time_to_saturation": time_to_saturation,
        "primary_drivers": primary_drivers,
        "limiting_factors": limiting_factors,
        "uptake_score": uptake_score,
        "size_efficiency": size_efficiency,
        "charge_efficiency": charge_efficiency,
        "hydro_efficiency": hydro_efficiency,
        "material_factor": material_factor * 100,
    }


def display_cellular_uptake_widget(design_params):
    """Display cellular uptake analysis with visualizations"""
    
    result = predict_cellular_uptake(design_params)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Uptake Efficiency",
            f"{result['uptake_efficiency']:.1f}%",
            help="Percentage of cells that internalize the nanoparticle"
        )
    
    with col2:
        st.metric(
            "Uptake Score",
            f"{result['uptake_score']:.0f}/100",
            help="Overall cellular uptake potential"
        )
    
    with col3:
        st.metric(
            "Time to Saturation",
            f"{result['time_to_saturation']:.1f} hrs",
            help="Time for ~90% of target cells to internalize particles"
        )
    
    st.markdown("**Uptake Mechanism:**")
    st.write(f"🔹 {result['uptake_mechanism']}")
    st.write(f"📍 Pathway: {result['uptake_pathway']}")
    
    # Uptake pathway breakdown
    st.markdown("**Uptake Pathway Composition:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_uptake = go.Figure(data=[go.Pie(
            labels=["Receptor-Mediated", "Non-Specific"],
            values=[result['receptor_mediated'], result['nonspecific']],
            marker=dict(colors=['#2E86AB', '#A23B72']),
            hoverinfo="label+percent+value"
        )])
        fig_uptake.update_layout(
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_uptake, use_container_width=True)
    
    with col2:
        # Factor contribution chart
        factors = {
            "Size": result['size_efficiency'],
            "Charge": result['charge_efficiency'],
            "Hydrophobicity": result['hydro_efficiency'],
            "Material": result['material_factor'],
        }
        
        fig_factors = go.Figure(data=[go.Bar(
            x=list(factors.keys()),
            y=list(factors.values()),
            marker=dict(color=['#06A77D', '#D62828', '#F77F00', '#06A77D']),
            text=[f"{v:.0f}%" for v in factors.values()],
            textposition="auto"
        )])
        
        fig_factors.update_layout(
            height=300,
            yaxis_title="Efficiency (%)",
            yaxis_range=[0, 105],
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False
        )
        st.plotly_chart(fig_factors, use_container_width=True)
    
    # Drivers and limiting factors
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**✅ Primary Drivers:**")
        for driver in result['primary_drivers']:
            st.write(f"• {driver}")
    
    with col2:
        st.markdown("**⚠️ Limiting Factors:**")
        if result['limiting_factors']:
            for factor in result['limiting_factors']:
                st.write(f"• {factor}")
        else:
            st.success("No significant limitations detected!")


if __name__ == "__main__":
    # Test
    test_design = {
        "Size": 95,
        "Charge": -5,
        "Ligand": "GalNAc",
        "LigandDensity": 65,
        "Hydrophobicity": 1.5,
        "SurfaceCoating": ["PEG (Stealth)"],
        "Material": "Lipid NP",
    }
    
    result = predict_cellular_uptake(test_design)
    print(f"Uptake Efficiency: {result['uptake_efficiency']:.1f}%")
    print(f"Uptake Score: {result['uptake_score']:.0f}/100")
    print(f"Primary Drivers: {result['primary_drivers']}")
