"""
Sprint 3: Reproducibility Assessment Predictor
Assesses likelihood of reproducing design, critical parameters, and variability
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_reproducibility_assessment(design_params):
    """
    Predict reproducibility metrics for the design
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    peg_density = design_params.get("PEG_Density", 50)
    charge = design_params.get("Charge", -5)
    ligand = design_params.get("Ligand", "None")
    encapsulation = design_params.get("Encapsulation", "Passive Loading")
    
    # Material reproducibility difficulty
    material_reproducibility = {
        "Lipid NP": {
            "reproducibility_score": 82,
            "batch_to_batch_variation": 8,
            "critical_parameters": 4
        },
        "PLGA": {
            "reproducibility_score": 75,
            "batch_to_batch_variation": 12,
            "critical_parameters": 5
        },
        "Liposome": {
            "reproducibility_score": 78,
            "batch_to_batch_variation": 10,
            "critical_parameters": 4
        },
        "Gold NP": {
            "reproducibility_score": 88,
            "batch_to_batch_variation": 5,
            "critical_parameters": 3
        },
        "Albumin NP": {
            "reproducibility_score": 85,
            "batch_to_batch_variation": 6,
            "critical_parameters": 3
        },
        "Silica NP": {
            "reproducibility_score": 80,
            "batch_to_batch_variation": 7,
            "critical_parameters": 3
        },
        "DNA Origami": {
            "reproducibility_score": 50,
            "batch_to_batch_variation": 25,
            "critical_parameters": 8
        },
        "Polymeric NP": {
            "reproducibility_score": 70,
            "batch_to_batch_variation": 15,
            "critical_parameters": 6
        },
        "Exosomes": {
            "reproducibility_score": 45,
            "batch_to_batch_variation": 30,
            "critical_parameters": 7
        }
    }
    
    base_data = material_reproducibility.get(material, material_reproducibility["Lipid NP"])
    
    # Adjust for complexity
    complexity_factors = []
    
    # Ligand targeting adds complexity
    ligand_complexity = 0
    if ligand and ligand != "None":
        ligand_complexity = 5
        complexity_factors.append(f"Ligand attachment ({ligand})")
    
    # Size precision needed
    size_precision = 0
    if size < 50:
        size_precision = 8
        complexity_factors.append("Small size requires tight control")
    elif size > 150:
        size_precision = 4
        complexity_factors.append("Large size more stable")
    
    # Encapsulation method complexity
    encapsulation_complexity = {
        "Passive Loading": 0,
        "Active Loading": 5,
        "Electroporation": 8,
        "Hydrodynamic Injection": 10,
        "Microfluidic": 12,
        "Emulsification": 6
    }
    
    enc_complexity = encapsulation_complexity.get(encapsulation, 0)
    complexity_factors.append(f"{encapsulation} method")
    
    # Calculate reproducibility score
    total_reproducibility = max(20, base_data["reproducibility_score"] - ligand_complexity - size_precision - enc_complexity)
    batch_variation = base_data["batch_to_batch_variation"] + ligand_complexity + enc_complexity
    
    # Critical parameters definition
    critical_params = [
        "Material source and purity",
        "Temperature during synthesis",
        "pH and buffer concentration"
    ]
    
    if ligand != "None":
        critical_params.append(f"Ligand attachment efficiency")
    if size < 80:
        critical_params.append("Particle size distribution (tight range)")
    if abs(charge) > 20:
        critical_params.append("Charge stabilization conditions")
    
    # Reproducibility difficulty classification
    if total_reproducibility >= 80:
        difficulty_level = "🟢 High - Easily Reproducible"
        difficulty_desc = "Can be reliably reproduced across labs"
    elif total_reproducibility >= 60:
        difficulty_level = "🟡 Moderate - Reproducible with Care"
        difficulty_desc = "Requires careful protocol documentation"
    elif total_reproducibility >= 40:
        difficulty_level = "🟠 Challenging - Requires Expertise"
        difficulty_desc = "Need experienced team and controlled conditions"
    else:
        difficulty_level = "🔴 Very Difficult - Research Grade Only"
        difficulty_desc = "Limited reproducibility across different labs"
    
    # Troubleshooting guide for common issues
    troubleshooting = {
        "Size variation": {
            "cause": "Batch-to-batch material differences",
            "solution": "Standardize material sourcing and storage conditions"
        },
        "Encapsulation efficiency drift": {
            "cause": "pH and temperature fluctuations",
            "solution": "Implement precise environmental controls"
        },
        "Ligand loss during synthesis": {
            "cause": "Radical attack or hydrolysis",
            "solution": "Use antioxidants and pH buffers"
        },
        "Batch aggregation": {
            "cause": "Sub-optimal charge or ionic strength",
            "solution": "Optimize buffer composition and storage temperature"
        }
    }
    
    # Success probability by lab experience
    success_probabilities = {
        "Expert lab (100+ NP batches)": 92,
        "Experienced lab (10-100 batches)": 78,
        "New lab (< 10 batches)": 55,
        "Different institution": 42
    }
    
    return {
        "reproducibility_score": total_reproducibility,
        "batch_to_batch_variation": batch_variation,
        "difficulty_level": difficulty_level,
        "difficulty_description": difficulty_desc,
        "critical_parameters": critical_params,
        "complexity_factors": complexity_factors,
        "troubleshooting_guide": troubleshooting,
        "success_probabilities": success_probabilities,
        "protocol_complexity": len(critical_params) * 10
    }


def display_reproducibility_assessment_widget(design_params):
    """Display reproducibility assessment visualization"""
    
    result = predict_reproducibility_assessment(design_params)
    
    # Main reproducibility metrics
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Reproducibility gauge
        fig_gauge = go.Figure(data=[go.Indicator(
            mode="gauge+number+delta",
            value=result["reproducibility_score"],
            title="Reproducibility Score",
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 40], 'color': "lightcoral"},
                    {'range': [40, 60], 'color': "lightyellow"},
                    {'range': [60, 80], 'color': "lightgreen"},
                    {'range': [80, 100], 'color': "darkgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 70
                }
            }
        )])
        st.plotly_chart(fig_gauge, use_container_width=True, height=300)
    
    with col2:
        st.markdown("### Assessment")
        st.info(result["difficulty_level"])
        st.write(result["difficulty_description"])
        st.metric("Batch Variation (%)", f"±{result['batch_to_batch_variation']:.1f}%")
    
    st.divider()
    
    # Complexity factors
    st.markdown("### Design Complexity Factors")
    for factor in result["complexity_factors"]:
        st.write(f"• {factor}")
    
    st.divider()
    
    # Critical parameters
    col_crit, col_probs = st.columns(2)
    
    with col_crit:
        st.markdown("### Critical Parameters for Reproducibility")
        for i, param in enumerate(result["critical_parameters"], 1):
            st.write(f"{i}. {param}")
    
    with col_probs:
        st.markdown("### Success Probability by Lab Type")
        prob_df = pd.DataFrame([
            {"Lab Type": name, "Success Rate (%)": prob}
            for name, prob in result["success_probabilities"].items()
        ]).sort_values("Success Rate (%)", ascending=True)
        
        fig_prob = go.Figure(data=[go.Bar(
            x=prob_df["Success Rate (%)"],
            y=prob_df["Lab Type"],
            orientation="h",
            marker_color="lightblue"
        )])
        st.plotly_chart(fig_prob, use_container_width=True, height=280)
    
    st.divider()
    
    # Troubleshooting guide
    st.markdown("### Troubleshooting Guide for Common Issues")
    
    for issue, guidance in result["troubleshooting_guide"].items():
        with st.expander(f"❓ {issue}"):
            st.write(f"**Cause:** {guidance['cause']}")
            st.write(f"**Solution:** {guidance['solution']}")
    
    st.divider()
    
    # Protocol complexity
    st.markdown("### Protocol Documentation")
    st.metric("Estimated Protocol Complexity Score", f"{result['protocol_complexity']:.0f}/100")
    st.write("*Higher scores indicate more detailed documentation required*")
