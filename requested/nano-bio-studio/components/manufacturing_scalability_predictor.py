"""
Sprint 3: Manufacturing Scalability Predictor
Assesses production feasibility, GMP requirements, and cost per dose
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_manufacturing_scalability(design_params):
    """
    Predict manufacturing scalability metrics
    
    Returns:
    {
        "production_feasibility": float (0-100),
        "gmp_readiness": float (0-100),
        "cost_per_dose_usd": float,
        "scalability_score": float (0-100),
        "current_batch_size_mg": float,
        "target_batch_size_g": float,
        "scale_factor": float,
        "gmp_requirements": list,
        "scalability_challenges": list,
        "scalability_level": str
    }
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    charge = design_params.get("Charge", -5)
    peg_density = design_params.get("PEG_Density", 50)
    
    # Map encapsulation method to numeric score
    encapsulation_method = design_params.get("Encapsulation", "Passive Loading")
    encapsulation_scores = {
        "Passive Loading": 85,
        "Active Loading": 75,
        "Electroporation": 65,
        "Hydrodynamic Injection": 55,
        "Microfluidic": 70,
        "Emulsification": 80
    }
    encapsulation = encapsulation_scores.get(encapsulation_method, 85)
    
    # 1. Production Feasibility (0-100%)
    # Based on manufacturing method stability and scalability
    
    material_feasibility = {
        "Lipid NP": 95,      # Gold standard, well-established
        "PLGA": 90,          # Matured technology
        "Liposome": 92,      # Established process
        "Albumin NP": 88,    # Growing scale-up success
        "Gold NP": 75,       # Complex synthesis
        "Silica NP": 85,     # Established but QC challenges
        "DNA Origami": 40,   # Very challenging to scale
        "Polymeric NP": 80,  # Moderate challenges
        "Exosomes": 60       # Biological variability issues
    }
    
    feasibility_base = material_feasibility.get(material, 75)
    
    # Size effect on feasibility
    if 50 <= size <= 150:
        feasibility_base += 5  # Optimal size range
    elif size > 200:
        feasibility_base -= 10  # Large particles harder to manufacture uniformly
    elif size < 30:
        feasibility_base -= 15  # Very small particles require specialized equipment
    
    # Charge complexity
    charge_abs = abs(charge)
    if charge_abs <= 10:
        feasibility_base += 3
    else:
        feasibility_base -= 5  # Very charged particles harder to scale
    
    # PEGylation adds complexity
    if peg_density > 50:
        feasibility_base -= 5
    
    production_feasibility = min(100, feasibility_base)
    
    # 2. GMP Readiness (0-100%)
    # Assess regulatory compliance readiness
    
    gmp_readiness_base = 50  # Most nanoparticles not yet GMP-ready
    
    # Established material platforms get higher GMP readiness
    if material in ["Lipid NP", "Liposome", "PLGA"]:
        gmp_readiness_base += 25  # Existing GMP guidance
    else:
        gmp_readiness_base += 10
    
    # Charge standardization helps GMP
    if charge_abs <= 15:
        gmp_readiness_base += 5
    
    # Encapsulation consistency critical for GMP
    if encapsulation >= 85:
        gmp_readiness_base += 10
    else:
        gmp_readiness_base -= 5
    
    # Size uniformity critical
    if size >= 80 and size <= 120:
        gmp_readiness_base += 10  # PDI typically lower
    
    gmp_readiness = min(100, gmp_readiness_base)
    
    # 3. Cost per Dose Analysis
    # Based on material costs, synthesis complexity, yields
    
    material_costs = {
        "Lipid NP": 8,              # $/dose, high volume established
        "PLGA": 12,                 # More expensive polymers
        "Liposome": 10,
        "Albumin NP": 15,           # Protein sourcing costs
        "Gold NP": 25,              # Expensive material
        "Silica NP": 20,
        "DNA Origami": 150,         # Very expensive synthesis
        "Polymeric NP": 18,
        "Exosomes": 40              # Complex isolation
    }
    
    base_cost = material_costs.get(material, 15)
    
    # Manufacturing complexity adders
    complexity_factor = 1.0
    
    if production_feasibility < 60:
        complexity_factor += 0.3
    elif production_feasibility < 75:
        complexity_factor += 0.15
    
    # Targeting adds cost
    ligand = design_params.get("Ligand", "None")
    if ligand != "None":
        complexity_factor += 0.2
    
    # PEGylation adds cost
    if peg_density > 30:
        complexity_factor += 0.15
    
    cost_per_dose = base_cost * complexity_factor
    
    # Current batch vs target production
    current_batch_size_mg = 50  # Typical lab scale
    target_batch_size_g = 1000  # 1 kg target batch
    scale_factor = target_batch_size_g * 1000 / current_batch_size_mg
    
    # 4. Calculate composite Scalability Score
    scalability_score = (
        production_feasibility * 0.40 +
        (100 - (cost_per_dose / 200) * 100) * 0.30 +  # Cost efficiency
        gmp_readiness * 0.30
    )
    
    # Determine scalability level
    if scalability_score >= 80:
        scalability_level = "🟢 Highly Scalable"
    elif scalability_score >= 60:
        scalability_level = "🟡 Moderately Scalable"
    elif scalability_score >= 40:
        scalability_level = "🟠 Challenging to Scale"
    else:
        scalability_level = "🔴 Not Currently Scalable"
    
    # GMP requirements
    gmp_requirements = [
        "Quality by Design (QbD) documentation",
        "Process Parameter Mapping (PPM)",
        "Control strategy development"
    ]
    
    if material == "DNA Origami":
        gmp_requirements.extend(["Custom equipment validation", "In-process testing protocols"])
    elif material in ["Exosomes"]:
        gmp_requirements.extend(["Bioreactor process validation", "Batch-to-batch consistency study"])
    else:
        gmp_requirements.extend(["Standard equipment qualification", "Three-batch IQ/OQ/PQ"])
    
    # Scalability challenges
    scalability_challenges = []
    
    if production_feasibility < 70:
        scalability_challenges.append("Production process not mature")
    if cost_per_dose > 50:
        scalability_challenges.append("High manufacturing cost")
    if gmp_readiness < 60:
        scalability_challenges.append("Limited regulatory guidance")
    if scale_factor > 10000:
        scalability_challenges.append("Large scale-up factor may cause issues")
    
    if not scalability_challenges:
        scalability_challenges = ["No major challenges identified"]
    
    return {
        "production_feasibility": production_feasibility,
        "gmp_readiness": gmp_readiness,
        "cost_per_dose_usd": cost_per_dose,
        "scalability_score": scalability_score,
        "scalability_level": scalability_level,
        "current_batch_size_mg": current_batch_size_mg,
        "target_batch_size_g": target_batch_size_g,
        "scale_factor": scale_factor,
        "gmp_requirements": gmp_requirements,
        "scalability_challenges": scalability_challenges,
        "material_cost_factor": material_costs.get(material, 15)
    }


def display_manufacturing_scalability_widget(design_params):
    """Display manufacturing scalability visualization"""
    
    result = predict_manufacturing_scalability(design_params)
    
    # Main scalability gauge
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = go.Figure(data=[go.Indicator(
            mode="gauge+number+delta",
            value=result["scalability_score"],
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Manufacturing Scalability"},
            delta={"reference": 70},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "darkGreen"},
                "steps": [
                    {"range": [0, 40], "color": "rgba(255, 100, 100, 0.3)"},
                    {"range": [40, 60], "color": "rgba(255, 200, 0, 0.3)"},
                    {"range": [60, 80], "color": "rgba(150, 255, 100, 0.3)"},
                    {"range": [80, 100], "color": "rgba(100, 255, 100, 0.3)"}
                ]
            }
        )])
        fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Key Metrics")
        st.metric("Feasibility", f"{result['production_feasibility']:.0f}%")
        st.metric("GMP Ready", f"{result['gmp_readiness']:.0f}%")
        st.metric("Cost/Dose", f"${result['cost_per_dose_usd']:.2f}")
    
    st.divider()
    
    # Scalability status
    st.markdown(f"### {result['scalability_level']}")
    
    # Cost analysis
    st.markdown("### Cost Analysis")
    col_cost1, col_cost2, col_cost3 = st.columns(3)
    
    with col_cost1:
        st.metric("Material Cost", f"${result['material_cost_factor']:.2f}/dose")
    with col_cost2:
        st.metric("Current Batch", f"{result['current_batch_size_mg']:.0f} mg")
    with col_cost3:
        st.metric("Target Batch", f"{result['target_batch_size_g']:.0f} g")
    
    st.info(f"⬆️ **Scale-up Factor:** {result['scale_factor']:.0f}x (from mg → g scale)")
    
    st.divider()
    
    # Challenges and requirements
    col_req, col_chal = st.columns(2)
    
    with col_req:
        st.markdown("### GMP Requirements")
        for req in result["gmp_requirements"]:
            st.write(f"✓ {req}")
    
    with col_chal:
        st.markdown("### Scalability Challenges")
        for challenge in result["scalability_challenges"]:
            st.write(f"⚠️ {challenge}")
