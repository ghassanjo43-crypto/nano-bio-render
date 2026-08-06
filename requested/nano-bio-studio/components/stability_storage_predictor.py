"""
Sprint 3: Stability & Storage Predictor
Assesses shelf-life, storage conditions, and degradation pathways
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_stability_storage(design_params):
    """
    Predict stability and storage metrics
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    peg_density = design_params.get("PEGDensity") or design_params.get("PEG_Density") or 50
    if peg_density is None:
        peg_density = 50
    charge = design_params.get("Charge", -5)
    hydrophobicity = design_params.get("Hydrophobicity", 1.5)
    
    # Material-specific stability at 25°C/60% RH (standard condition)
    material_stability = {
        "Lipid NP": {"shelf_life_months": 12, "degradation_rate": 0.08},
        "PLGA": {"shelf_life_months": 18, "degradation_rate": 0.06},
        "Liposome": {"shelf_life_months": 10, "degradation_rate": 0.10},
        "Gold NP": {"shelf_life_months": 36, "degradation_rate": 0.02},
        "Albumin NP": {"shelf_life_months": 8, "degradation_rate": 0.12},
        "Silica NP": {"shelf_life_months": 24, "degradation_rate": 0.04},
        "DNA Origami": {"shelf_life_months": 3, "degradation_rate": 0.30},
        "Polymeric NP": {"shelf_life_months": 15, "degradation_rate": 0.07},
        "Exosomes": {"shelf_life_months": 6, "degradation_rate": 0.16}
    }
    
    stability_data = material_stability.get(material, {"shelf_life_months": 12, "degradation_rate": 0.10})
    base_shelf_life = stability_data["shelf_life_months"]
    
    # PEGylation improves stability
    if peg_density > 50:
        base_shelf_life *= 1.3
    elif peg_density > 30:
        base_shelf_life *= 1.15
    
    # Charge effect on aggregation
    charge_abs = abs(charge)
    if charge_abs <= 10:
        base_shelf_life *= 1.2  # Neutral particles more stable
    elif charge_abs > 30:
        base_shelf_life *= 0.8  # High charge causes aggregation
    
    # Size effect
    if size >= 80 and size <= 120:
        base_shelf_life *= 1.1  # Optimal size stability
    
    shelf_life_25c = min(36, base_shelf_life)  # Cap at 3 years
    
    # Storage condition improvements
    shelf_life_4c = shelf_life_25c * 2.5   # 2-4°C storage
    shelf_life_m20c = shelf_life_25c * 4.0  # -20°C storage
    shelf_life_m80c = shelf_life_25c * 8.0  # -80°C storage
    
    # Stability score
    stability_score = min(100, (shelf_life_25c / 36) * 100)
    
    # Degradation pathways
    degradation_pathways = []
    
    if material in ["Lipid NP", "Liposome"]:
        degradation_pathways = [
            "Lipid oxidation",
            "Hydrolysis of ester chains",
            "Oxidative degradation of PEG"
        ]
    elif material == "PLGA":
        degradation_pathways = [
            "Polymer backbone hydrolysis",
            "Acidic microclimate effect",
            "Burst release phenomenon"
        ]
    elif material == "DNA Origami":
        degradation_pathways = [
            "Nuclease degradation",
            "Heat denaturation",
            "Structural unwinding"
        ]
    else:
        degradation_pathways = [
            "Surface oxidation",
            "Particle aggregation",
            "Loss of surface functionality"
        ]
    
    # Recommended storage conditions
    if shelf_life_25c >= 12:
        recommended_storage = "2-8°C (Refrigerated)"
        storage_temp = 4
    elif shelf_life_m20c >= 18:
        recommended_storage = "-20°C (Freezer)"
        storage_temp = -20
    else:
        recommended_storage = "-80°C (Ultra-low freezer)"
        storage_temp = -80
    
    # Formulation stability score
    formulation_stability = {
        "osmolyte_protection": 70,
        "antioxidant_protection": 60,
        "surfactant_protection": 75,
        "pH_buffering": 65,
        "cryoprotection": 55
    }
    
    return {
        "shelf_life_25c_months": shelf_life_25c,
        "shelf_life_4c_months": shelf_life_4c,
        "shelf_life_m20c_months": shelf_life_m20c,
        "shelf_life_m80c_months": shelf_life_m80c,
        "stability_score": stability_score,
        "recommended_storage": recommended_storage,
        "storage_temperature_c": storage_temp,
        "degradation_pathways": degradation_pathways,
        "formulation_stability": formulation_stability,
        "degradation_rate": stability_data["degradation_rate"]
    }


def display_stability_storage_widget(design_params):
    """Display stability and storage visualization"""
    
    result = predict_stability_storage(design_params)
    
    # Stability gauge and shelf life comparison
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Shelf-life comparison chart
        temps = ["25°C\n(Room Temp)", "4°C\n(Fridge)", "-20°C\n(Freezer)", "-80°C\n(Ultra-low)"]
        shelf_lives = [
            result["shelf_life_25c_months"],
            result["shelf_life_4c_months"],
            result["shelf_life_m20c_months"],
            result["shelf_life_m80c_months"]
        ]
        
        fig = go.Figure(data=[
            go.Bar(x=temps, y=shelf_lives, marker_color=['red', 'orange', 'lightblue', 'blue'])
        ])
        fig.update_layout(
            yaxis_title="Shelf-Life (months)",
            height=300,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Recommended Storage")
        st.info(f"**{result['recommended_storage']}**")
        st.metric("Stability Score", f"{result['stability_score']:.0f}/100")
    
    st.divider()
    
    # Shelf-life breakdown
    col_sf1, col_sf2, col_sf3, col_sf4 = st.columns(4)
    
    with col_sf1:
        st.metric("Room Temp (25°C)", f"{result['shelf_life_25c_months']:.0f}m")
    with col_sf2:
        st.metric("Refrigerated (4°C)", f"{result['shelf_life_4c_months']:.0f}m")
    with col_sf3:
        st.metric("Frozen (-20°C)", f"{result['shelf_life_m20c_months']:.0f}m")
    with col_sf4:
        st.metric("Ultra-low (-80°C)", f"{result['shelf_life_m80c_months']:.0f}m")
    
    st.divider()
    
    # Degradation mechanisms and formulation
    col_deg, col_form = st.columns(2)
    
    with col_deg:
        st.markdown("### Primary Degradation Pathways")
        for i, pathway in enumerate(result["degradation_pathways"], 1):
            st.write(f"{i}. {pathway}")
    
    with col_form:
        st.markdown("### Formulation Stability Score")
        form_df = pd.DataFrame({
            "Component": list(result["formulation_stability"].keys()),
            "Protection (%)": list(result["formulation_stability"].values())
        }).sort_values("Protection (%)", ascending=True)
        
        fig_form = go.Figure(data=[go.Bar(
            x=form_df["Protection (%)"],
            y=form_df["Component"],
            orientation="h",
            marker_color="lightblue"
        )])
        st.plotly_chart(fig_form, use_container_width=True, height=250)
