"""
Sprint 3: Environmental Impact Predictor
Assesses biodegradability, toxicity, and sustainability metrics
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_environmental_impact(design_params):
    """
    Predict environmental impact metrics
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    peg_density = design_params.get("PEG_Density", 50)
    charge = design_params.get("Charge", -5)
    
    # Material environmental profiles
    material_profiles = {
        "Lipid NP": {
            "biodegradability": 85,
            "bioaccumulation_potential": 25,
            "aquatic_toxicity": 30,
            "soil_persistence": 15,
            "carbon_footprint_kg": 0.5
        },
        "PLGA": {
            "biodegradability": 90,
            "bioaccumulation_potential": 15,
            "aquatic_toxicity": 20,
            "soil_persistence": 10,
            "carbon_footprint_kg": 0.8
        },
        "Liposome": {
            "biodegradability": 80,
            "bioaccumulation_potential": 30,
            "aquatic_toxicity": 35,
            "soil_persistence": 20,
            "carbon_footprint_kg": 0.6
        },
        "Gold NP": {
            "biodegradability": 20,
            "bioaccumulation_potential": 75,
            "aquatic_toxicity": 60,
            "soil_persistence": 95,
            "carbon_footprint_kg": 2.0
        },
        "Albumin NP": {
            "biodegradability": 95,
            "bioaccumulation_potential": 5,
            "aquatic_toxicity": 10,
            "soil_persistence": 5,
            "carbon_footprint_kg": 0.4
        },
        "Silica NP": {
            "biodegradability": 40,
            "bioaccumulation_potential": 50,
            "aquatic_toxicity": 45,
            "soil_persistence": 85,
            "carbon_footprint_kg": 1.2
        },
        "DNA Origami": {
            "biodegradability": 95,
            "bioaccumulation_potential": 10,
            "aquatic_toxicity": 15,
            "soil_persistence": 8,
            "carbon_footprint_kg": 0.3
        },
        "Polymeric NP": {
            "biodegradability": 75,
            "bioaccumulation_potential": 35,
            "aquatic_toxicity": 40,
            "soil_persistence": 30,
            "carbon_footprint_kg": 0.9
        },
        "Exosomes": {
            "biodegradability": 98,
            "bioaccumulation_potential": 2,
            "aquatic_toxicity": 5,
            "soil_persistence": 2,
            "carbon_footprint_kg": 1.5
        }
    }
    
    profile = material_profiles.get(material, material_profiles["Lipid NP"])
    
    # Size effects on environmental behavior
    size_factor = 1.0
    if size < 10:
        size_factor = 1.1  # Small NPs higher toxicity risk
    elif size > 200:
        size_factor = 0.9  # Large NPs less bioavailable
    
    # PEG effects (generally protective environmentally)
    peg_factor = 1.0 + (peg_density / 100) * 0.15
    
    # Calculate metrics
    biodegradability = min(100, profile["biodegradability"] * peg_factor)
    bioaccumulation = max(0, profile["bioaccumulation_potential"] / size_factor)
    aquatic_toxicity = max(0, profile["aquatic_toxicity"] / peg_factor)
    soil_persistence = profile["soil_persistence"] / peg_factor
    carbon_footprint = profile["carbon_footprint_kg"]
    
    # Sustainability score (0-100, higher is better)
    sustainability_score = (
        biodegradability * 0.35 +
        (100 - bioaccumulation) * 0.25 +
        (100 - aquatic_toxicity) * 0.25 +
        (100 - soil_persistence) * 0.15
    )
    
    # Environmental classification
    if sustainability_score >= 75:
        env_class = "🟢 Environmentally Friendly"
    elif sustainability_score >= 50:
        env_class = "🟡 Moderate Impact"
    elif sustainability_score >= 25:
        env_class = "🟠 High Impact"
    else:
        env_class = "🔴 Very High Impact"
    
    # Fate in environment
    if biodegradability >= 80:
        fate = "Rapid biodegradation (weeks-months)"
    elif biodegradability >= 50:
        fate = "Moderate degradation (months-years)"
    else:
        fate = "Persistent in environment (years-decades)"
    
    # Risk assessment
    risks = []
    if bioaccumulation > 50:
        risks.append("Potential bioaccumulation in aquatic organisms")
    if aquatic_toxicity > 40:
        risks.append("Aquatic toxicity concern")
    if soil_persistence > 50:
        risks.append("Soil contamination risk")
    
    # Manufacturing footprint
    manufacturing_impact = {
        "water_usage_liters": 50 + (material == "Exosomes") * 150,
        "waste_generated_kg": 0.3 + (material == "Gold NP") * 1.0,
        "energy_kwh": 2.5 + (biodegradability < 50) * 1.5
    }
    
    # Recycling potential
    recycling_score = {
        "Lipid NP": 60,
        "PLGA": 70,
        "Liposome": 60,
        "Gold NP": 90,
        "Albumin NP": 75,
        "Silica NP": 85,
        "DNA Origami": 50,
        "Polymeric NP": 65,
        "Exosomes": 40
    }.get(material, 60)
    
    return {
        "sustainability_score": sustainability_score,
        "environmental_classification": env_class,
        "biodegradability": biodegradability,
        "bioaccumulation_potential": bioaccumulation,
        "aquatic_toxicity": aquatic_toxicity,
        "soil_persistence": soil_persistence,
        "carbon_footprint_kg": carbon_footprint,
        "environmental_fate": fate,
        "risks": risks,
        "manufacturing_impact": manufacturing_impact,
        "recycling_score": recycling_score
    }


def display_environmental_impact_widget(design_params):
    """Display environmental impact visualization"""
    
    result = predict_environmental_impact(design_params)
    
    # Main sustainability overview
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Radar chart for environmental metrics
        categories = ["Biodegradability", "Low Bioaccumulation", "Low Toxicity", 
                      "Low Soil Persistence"]
        values = [
            result["biodegradability"],
            100 - result["bioaccumulation_potential"],
            100 - result["aquatic_toxicity"],
            100 - result["soil_persistence"]
        ]
        
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            marker_color='lightblue'
        ))
        fig_radar.update_layout(height=350)
        st.plotly_chart(fig_radar, use_container_width=True)
    
    with col2:
        st.markdown("### Sustainability Score")
        score = result["sustainability_score"]
        st.metric("Score", f"{score:.0f}/100")
        st.info(result["environmental_classification"])
        st.markdown(f"**Fate:** {result['environmental_fate']}")
    
    st.divider()
    
    # Environmental metrics
    col_met1, col_met2, col_met3, col_met4 = st.columns(4)
    
    with col_met1:
        st.metric("Biodegradability", f"{result['biodegradability']:.0f}%")
    with col_met2:
        st.metric("Bioaccumulation Risk", f"{result['bioaccumulation_potential']:.1f}/100")
    with col_met3:
        st.metric("Aquatic Toxicity", f"{result['aquatic_toxicity']:.1f}/100")
    with col_met4:
        st.metric("Soil Persistence", f"{result['soil_persistence']:.1f} years")
    
    st.divider()
    
    # Carbon footprint and manufacturing impact
    col_cf, col_mfg = st.columns(2)
    
    with col_cf:
        st.markdown("### Carbon Footprint")
        st.metric("CO₂ Equivalent", f"{result['carbon_footprint_kg']:.2f} kg/batch")
        
        fig_cf = go.Figure(data=[go.Indicator(
            mode="gauge+number",
            value=result['carbon_footprint_kg'],
            title="kg CO₂",
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 3]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 1], 'color': "lightgray"},
                    {'range': [1, 2], 'color': "gray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 2
                }
            }
        )])
        st.plotly_chart(fig_cf, use_container_width=True, height=250)
    
    with col_mfg:
        st.markdown("### Manufacturing Footprint")
        mfg = result["manufacturing_impact"]
        mfg_df = pd.DataFrame({
            "Impact": ["Water Usage", "Waste Generated", "Energy Use"],
            "Value": [f"{mfg['water_usage_liters']}L", f"{mfg['waste_generated_kg']}kg", f"{mfg['energy_kwh']}kWh"]
        })
        st.table(mfg_df)
        
        st.metric("Recycling Potential", f"{result['recycling_score']}/100")
    
    st.divider()
    
    # Environmental risks
    if result["risks"]:
        st.markdown("### Identified Environmental Risks")
        for risk in result["risks"]:
            st.warning(f"⚠️ {risk}")
    else:
        st.success("✅ No significant environmental risks identified")
