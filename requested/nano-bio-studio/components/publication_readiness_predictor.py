"""
Sprint 3: Publication Readiness Predictor
Assesses data completeness, statistical power, and novelty for publication
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_publication_readiness(design_params):
    """
    Predict publication readiness metrics
    
    Returns:
    {
        "data_completeness": float (0-100),
        "statistical_power": float (0-100),
        "novelty_score": float (0-100),
        "readiness_score": float (0-100),
        "missing_data_areas": list,
        "recommendation": str,
        "publication_timeline": str,
        "target_journals": list,
        "readiness_level": str
    }
    """
    
    material = design_params.get("Material", "Lipid NP")
    size = design_params.get("Size", 100)
    ligand = design_params.get("Ligand", "None")
    disease = design_params.get("Target", "Liver Cells")
    
    # 1. Data Completeness (0-100%)
    # Assess how complete the characterization profile is
    data_completeness_factors = {
        "particle_characterization": 100,  # Size, PDI, charge, etc.
        "stability_data": 75,  # Shelf-life testing
        "efficacy_data": 85,  # In vitro/vivo results
        "safety_data": 70,  # Toxicity, hemolysis
        "biodistribution": 65,  # Animal study data
        "mechanism_of_action": 60,  # MOA clarity
        "reproducibility": 70,  # Protocol documentation
        "statistical_analysis": 75,  # Stats methods documented
        "manufacturing_protocol": 80,  # GMP readiness
        "regulatory_pathway": 50  # Planning stage
    }
    
    completeness_avg = np.mean(list(data_completeness_factors.values()))
    
    # Material- and design-specific adjustments
    if material in ["Lipid NP", "PLGA"]:
        completeness_avg += 5  # Well-characterized materials
    
    if size >= 50 and size <= 150:
        completeness_avg += 3  # Optimal size range = more published references
    
    if ligand != "None":
        completeness_avg += 5  # Targeted particles get more scrutiny
    
    data_completeness = min(100, completeness_avg)
    
    # 2. Statistical Power (0-100%)
    # Estimates adequacy of study design for statistical significance
    
    # Base power depends on expected effect size
    material_effect_sizes = {
        "Lipid NP": 0.8,
        "PLGA": 0.75,
        "Gold NP": 0.85,
        "Liposome": 0.70,
        "DNA Origami": 0.90,
        "Silica NP": 0.65,
        "Albumin NP": 0.72,
        "Polymeric NP": 0.78,
        "Exosomes": 0.88
    }
    
    effect_size = material_effect_sizes.get(material, 0.75)
    
    # Statistical power calculation (simplified)
    # P(success) = Φ(effect_size * sqrt(N/2) - Zα)
    # Assume typical N=30 for nanoparticle studies
    n_samples = 30
    alpha = 0.05  # 5% significance level
    z_alpha = 1.96  # Two-tailed
    
    # Simplified power calculation
    power = (effect_size * np.sqrt(n_samples / 2) - z_alpha) / z_alpha * 50 + 50
    statistical_power = min(100, max(30, power))
    
    # Adjust for targeting and complexity
    if ligand != "None":
        statistical_power += 10  # Targeted designs clearer signal
    
    if disease in ["Hepatocellular Carcinoma", "Breast Cancer"]:
        statistical_power += 5  # Well-established disease models
    
    statistical_power = min(100, statistical_power)
    
    # 3. Novelty Score (0-100%)
    # Assesses innovation and differentiation from literature
    
    novelty_base = 60  # Baseline for any nanoparticle design
    
    # Material novelty
    if material == "DNA Origami":
        novelty_base += 15  # Highly novel platform
    elif material in ["Lipid NP", "PLGA"]:
        novelty_base -= 10  # Well-established, lower novelty
    elif material == "Gold NP":
        novelty_base += 8   # Relatively novel for drug delivery
    else:
        novelty_base += 5
    
    # Targeting novelty
    if ligand == "None":
        novelty_base -= 5
    elif ligand in ["DNA", "Aptamers", "DNA Origami"]:
        novelty_base += 12  # High-tech targeting
    elif ligand in ["Transferrin", "Folic Acid"]:
        novelty_base += 3   # Well-published targets
    else:
        novelty_base += 7
    
    # Multi-parameter optimization novelty
    if size >= 50 and size <= 150 and ligand != "None":
        novelty_base += 8  # Holistic optimized design
    
    # Adjust for disease rarity
    if disease not in ["Hepatocellular Carcinoma", "Breast Cancer", "Pancreatic Cancer"]:
        novelty_base += 5  # Rare disease = more novel
    
    novelty_score = min(100, max(30, novelty_base))
    
    # 4. Calculate composite Readiness Score
    readiness_score = (
        data_completeness * 0.35 +
        statistical_power * 0.35 +
        novelty_score * 0.30
    )
    
    # Determine readiness level
    if readiness_score >= 85:
        readiness_level = "🟢 Ready for Publication"
        recommendation = "Excellent. Manuscript writing recommended."
        publication_timeline = "Ready within 2-4 weeks"
    elif readiness_score >= 70:
        readiness_level = "🟡 Near Ready"
        recommendation = "Complete gap analysis. Minor additional experiments may help."
        publication_timeline = "Ready within 2-3 months"
    elif readiness_score >= 50:
        readiness_level = "🟠 In Progress"
        recommendation = "Significant characterization gaps. Continue development."
        publication_timeline = "Ready within 4-6 months"
    else:
        readiness_level = "🔴 Early Stage"
        recommendation = "Pre-publication characterization needed. Focus on key metrics."
        publication_timeline = "Likely 6+ months away"
    
    # Identify missing data areas
    missing_data_areas = []
    if data_completeness_factors["statistical_analysis"] < 80:
        missing_data_areas.append("Detailed statistical analysis")
    if data_completeness_factors["biodistribution"] < 70:
        missing_data_areas.append("In vivo biodistribution data")
    if data_completeness_factors["regulatory_pathway"] < 60:
        missing_data_areas.append("Regulatory strategy documentation")
    if data_completeness_factors["mechanism_of_action"] < 70:
        missing_data_areas.append("Mechanism of action clarification")
    
    # Target journals based on novelty and material
    target_journals = []
    if novelty_score >= 75:
        target_journals = ["Nature Nanotechnology", "Advanced Materials", "ACS Nano"]
    elif novelty_score >= 60:
        target_journals = ["Journal of Controlled Release", "Biomaterials", "Nanomedicine"]
    else:
        target_journals = ["International Journal of Nanomedicine", "Journal of Drug Delivery"]
    
    return {
        "data_completeness": data_completeness,
        "statistical_power": statistical_power,
        "novelty_score": novelty_score,
        "readiness_score": readiness_score,
        "readiness_level": readiness_level,
        "recommendation": recommendation,
        "publication_timeline": publication_timeline,
        "missing_data_areas": missing_data_areas,
        "target_journals": target_journals,
        "data_factors": data_completeness_factors
    }


def display_publication_readiness_widget(design_params):
    """Display publication readiness visualization"""
    
    result = predict_publication_readiness(design_params)
    
    # Readiness gauge
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = go.Figure(data=[go.Indicator(
            mode="gauge+number+delta",
            value=result["readiness_score"],
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Publication Readiness Score"},
            delta={"reference": 70, "suffix": " vs threshold"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "darkblue"},
                "steps": [
                    {"range": [0, 50], "color": "rgba(255, 100, 100, 0.3)"},
                    {"range": [50, 70], "color": "rgba(255, 200, 0, 0.3)"},
                    {"range": [70, 85], "color": "rgba(150, 255, 100, 0.3)"},
                    {"range": [85, 100], "color": "rgba(100, 255, 100, 0.3)"}
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 70
                }
            }
        )])
        fig.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Readiness Components")
        st.metric("Completeness", f"{result['data_completeness']:.0f}%")
        st.metric("Statistical Power", f"{result['statistical_power']:.0f}%")
        st.metric("Novelty", f"{result['novelty_score']:.0f}%")
    
    st.divider()
    
    # Status and recommendation
    st.markdown(f"### {result['readiness_level']}")
    st.info(f"**{result['recommendation']}**\n\n⏱️ {result['publication_timeline']}")
    
    st.divider()
    
    # Data completeness breakdown
    st.markdown("### Data Completeness Breakdown")
    
    factors_df = pd.DataFrame({
        "Data Category": list(result["data_factors"].keys()),
        "Completeness (%)": list(result["data_factors"].values())
    }).sort_values("Completeness (%)", ascending=True)
    
    fig_bar = go.Figure(data=[
        go.Bar(
            x=factors_df["Completeness (%)"],
            y=factors_df["Data Category"],
            orientation="h",
            marker=dict(
                color=factors_df["Completeness (%)"],
                colorscale="RdYlGn",
                showscale=False
            )
        )
    ])
    fig_bar.update_layout(height=350, xaxis_range=[0, 100])
    st.plotly_chart(fig_bar, use_container_width=True)
    
    st.divider()
    
    # Missing areas and target journals
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("### Gap Analysis")
        if result["missing_data_areas"]:
            for area in result["missing_data_areas"]:
                st.write(f"• **{area}**")
        else:
            st.success("✅ No major gaps identified!")
    
    with col4:
        st.markdown("### Target Journals")
        for journal in result["target_journals"]:
            st.write(f"• {journal}")
