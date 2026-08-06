"""
Sprint 2: Immune System Response Predictor
Models immune cell interactions and activation
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_immune_response(design_params):
    """
    Predict immune system response to nanoparticles
    
    Returns:
    {
        "innate_immunity_activation": float (0-100),
        "antibody_recognition": float (0-100),
        "complement_activation": float (0-100),
        "macrophage_recognition": float (0-100),
        "dendritic_cell_activation": float (0-100),
        "mps_capture": float (0-100),
        "immune_evasion_score": float (0-100),
        "optimal_peg_level": float,
        "immune_components": dict,
        "immune_activation_timeline": dict,
    }
    """
    
    size = design_params.get("Size", 100)
    charge = design_params.get("Charge", -5)
    material = design_params.get("Material", "Lipid NP")
    ligand = design_params.get("Ligand", "None")
    peg_density = design_params.get("PEGDensity") or design_params.get("PEG_Density") or 50
    if peg_density is None:
        peg_density = 50
    surface_coating = design_params.get("SurfaceCoating", [])
    
    # 1. Innate Immunity Activation (TLR signaling, pattern recognition)
    # Material immunogenicity
    material_immunogenicity = {
        "Lipid NP": {"pamp": 0.4, "danger": "Low"},  # Weak innate response
        "PLGA": {"pamp": 0.6, "danger": "Moderate"},
        "Gold NP": {"pamp": 0.3, "danger": "Very Low"},
        "Silica NP": {"pamp": 0.7, "danger": "High"},  # More immunogenic
        "DNA Origami": {"pamp": 0.8, "danger": "High"},  # Contains exposed DNA
        "Liposome": {"pamp": 0.5, "danger": "Low-Moderate"},
        "Polymeric NP": {"pamp": 0.65, "danger": "Moderate"},
        "Albumin NP": {"pamp": 0.2, "danger": "Very Low"},  # Natural protein
    }
    
    material_info = material_immunogenicity.get(material, {"pamp": 0.5, "danger": "Unknown"})
    
    # Size effect on innate response
    if 50 <= size <= 150:
        size_innate = 60
    elif size < 50:
        size_innate = 80  # Small particles more immunogenic
    else:
        size_innate = 70  # Large particles also trigger stronger response
    
    # Charge effect on innate response
    charge_abs = abs(charge)
    if charge_abs > 30:
        charge_innate = 90  # Highly charged = more immunogenic
    elif charge_abs > 10:
        charge_innate = 70
    else:
        charge_innate = 40  # Neutral = less immunogenic
    
    innate_immunity_activation = (material_info["pamp"] * 100 * 0.3 +
                                  size_innate * 0.35 +
                                  charge_innate * 0.35)
    
    # 2. Antibody Recognition (opsonization)
    # PEGylation reduces antibody binding
    peg_factor = 1 - (peg_density / 100) * 0.4  # 0-40% reduction
    
    # Charge affects opsonization
    antibody_recognition_base = 60 + (charge_abs / 50) * 30  # More charge = more recognized
    antibody_recognition = antibody_recognition_base * peg_factor
    
    # 3. Complement Activation (classical and alternative pathways)
    # Similar to antibody but less affected by PEG
    complement_base_activation = innate_immunity_activation
    
    # Complement cascade can be amplified
    if "Albumin NP" in material or material == "Albumin NP":
        complement_activation = 20  # Albumin is well-tolerated
    else:
        complement_activation = complement_base_activation * 0.7 * (1 - peg_density / 100 * 0.25)
    
    # 4. Macrophage Recognition (professional phagocytes)
    # Size critical for macrophage uptake (optimal 50-200nm)
    if 50 <= size <= 200:
        size_macro = 85
    elif size < 50:
        size_macro = 60
    else:
        size_macro = 30  # Too large for macrophages
    
    # Charge promotes macrophage uptake (scavenger receptors)
    macrophage_charge_factor = 1 + (charge_abs / 50) * 0.5  # Up to 150%
    
    macrophage_recognition = (size_macro * 0.5 +
                             innate_immunity_activation * 0.3 +
                             (charge_abs / 50 * 100) * 0.2) * macrophage_charge_factor
    macrophage_recognition = min(100, macrophage_recognition)
    
    # 5. Dendritic Cell Activation (antigen presentation, T-cell priming)
    # High for "danger" signals
    danger_levels = {"Very Low": 10, "Low": 25, "Low-Moderate": 40, "Moderate": 60, "High": 85}
    dc_activation_base = danger_levels.get(material_info["danger"], 50)
    
    # Size matters for DC uptake
    if 20 <= size <= 100:
        dc_size_factor = 1.0
    elif 100 < size <= 500:
        dc_size_factor = 0.8
    else:
        dc_size_factor = 0.5
    
    dendritic_cell_activation = dc_activation_base * dc_size_factor * (1 - peg_density / 100 * 0.3)
    
    # 6. MPS (Mononuclear Phagocyte System) Capture
    # Blood clearance by liver/spleen macrophages
    # Depends on opsonization, size, and charge
    
    if 20 <= size <= 100:
        size_mps = 95  # Optimal for capture
    elif 100 < size <= 200:
        size_mps = 80
    else:
        size_mps = max(30, 100 - abs(size - 150) * 0.3)
    
    # PEG provides longest stealth
    peg_stealth = 1 - (peg_density / 100) * 0.5  # 0-50% reduction in MPS capture
    
    # Albumin coating also provides stealth
    albumin_stealth = 0.7 if "Albumin" in str(surface_coating) else 1.0
    
    mps_capture = (size_mps * 0.4 +
                  antibody_recognition * 0.3 +
                  complement_activation * 0.2 +
                  macrophage_recognition * 0.1) * peg_stealth * albumin_stealth
    mps_capture = min(100, max(0, mps_capture))
    
    # 7. Immune Evasion Score (opposite of immune activation)
    immune_evasion_score = 100 - (
        (innate_immunity_activation * 0.25) +
        (antibody_recognition * 0.20) +
        (complement_activation * 0.15) +
        (macrophage_recognition * 0.20) +
        (dendritic_cell_activation * 0.20)
    )
    immune_evasion_score = max(0, min(100, immune_evasion_score))
    
    # 8. Optimal PEG Level for Immune Evasion
    # Sweet spot is usually 10-15% PEG
    # Too little = poor stealth
    # Too much = reduced targeting
    optimal_peg_level = 12  # % (typical optimal)
    
    # 9. Immune activation timeline (hours)
    timeline = {
        "Minutes 0-15": "Initial complement cascade",
        "Minutes 15-60": "Antibody opsonization",
        "Hours 1-2": "Macrophage recruitment & phagocytosis",
        "Hours 2-4": "Dendritic cell antigen presentation",
        "Hours 4+": "T-cell priming (if very immunogenic)",
    }
    
    # 10. Immune component breakdown
    immune_components = {
        "Innate Immunity": innate_immunity_activation,
        "Antibody Recognition": antibody_recognition,
        "Complement Activation": complement_activation,
        "Macrophage Recognition": macrophage_recognition,
        "DC Activation": dendritic_cell_activation,
    }
    
    return {
        "innate_immunity_activation": max(0, min(100, innate_immunity_activation)),
        "antibody_recognition": max(0, min(100, antibody_recognition)),
        "complement_activation": max(0, min(100, complement_activation)),
        "macrophage_recognition": max(0, min(100, macrophage_recognition)),
        "dendritic_cell_activation": max(0, min(100, dendritic_cell_activation)),
        "mps_capture": mps_capture,
        "immune_evasion_score": immune_evasion_score,
        "optimal_peg_level": optimal_peg_level,
        "immune_components": immune_components,
        "immune_activation_timeline": timeline,
        "material_danger_level": material_info["danger"],
        "current_peg_level": peg_density,
    }


def display_immune_response_widget(design_params):
    """Display immune system response analysis"""
    
    result = predict_immune_response(design_params)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "MPS Capture Risk",
            f"{result['mps_capture']:.1f}%",
            help="% capture by liver/spleen macrophages"
        )
    
    with col2:
        st.metric(
            "Immune Evasion",
            f"{result['immune_evasion_score']:.1f}%",
            help="Ability to evade immune system"
        )
    
    with col3:
        danger_color = "🟢" if "Low" in result['material_danger_level'] else "🟡" if "Moderate" in result['material_danger_level'] else "🔴"
        st.metric(
            "Danger Level",
            f"{danger_color} {result['material_danger_level']}",
            help="Innate immune trigger level"
        )
    
    with col4:
        peg_status = "✓ Optimal" if 10 <= result['current_peg_level'] <= 15 else "⚠️ Suboptimal" if result['current_peg_level'] < 5 else "⚠️ High"
        st.metric(
            "PEG Level",
            f"{peg_status} ({result['current_peg_level']}%)",
            help=f"Optimal: {result['optimal_peg_level']}%"
        )
    
    # Immune activation timeline
    st.markdown("**Immune Activation Timeline:**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Create timeline visualization
        timeline_text = ""
        for phase, description in result['immune_activation_timeline'].items():
            timeline_text += f"**{phase}**  \n{description}\n\n"
        
        st.markdown(timeline_text)
    
    with col2:
        # Immune activation radar chart
        categories = list(result['immune_components'].keys())
        values = list(result['immune_components'].values())
        values += values[:1]  # Complete the circle
        categories_complete = categories + [categories[0]]
        
        fig_radar = go.Figure()
        
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories_complete,
            fill='toself',
            name='Immune Activation',
            fillcolor='rgba(255, 107, 107, 0.3)',
            line=dict(color='#FF6B6B', width=2)
        ))
        
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False,
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        
        st.plotly_chart(fig_radar, use_container_width=True)
    
    # Detailed immune component breakdown
    st.markdown("**Immune Component Activation Levels:**")
    
    immune_data = []
    for component, level in result['immune_components'].items():
        status = "🟢 Low" if level < 33 else "🟡 Moderate" if level < 66 else "🔴 High"
        immune_data.append({
            "Immune Component": component,
            "Activation (%)": f"{level:.1f}%",
            "Status": status
        })
    
    df_immune = pd.DataFrame(immune_data)
    st.dataframe(df_immune, use_container_width=True, hide_index=True)
    
    # PEG Recommendation
    st.markdown("**PEG Optimization Recommendation:**")
    
    peg_current = result['current_peg_level']
    peg_optimal = result['optimal_peg_level']
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_peg = go.Figure()
        
        peg_levels = np.arange(0, 25, 1)
        # Simulate immune evasion vs PEG level (inverted U shape)
        immune_evasion_by_peg = 100 - np.abs(peg_levels - 12) * 3
        immune_evasion_by_peg = np.clip(immune_evasion_by_peg, 0, 100)
        
        fig_peg.add_trace(go.Scatter(
            x=peg_levels,
            y=immune_evasion_by_peg,
            mode='lines+markers',
            name='Immune Evasion',
            line=dict(color='#4ECDC4', width=3),
            fill='tozeroy',
            fillcolor='rgba(78, 205, 196, 0.2)'
        ))
        
        # Add current and optimal
        fig_peg.add_vline(
            x=peg_current,
            line_dash="solid",
            line_color="orange",
            annotation_text=f"Current: {peg_current}%"
        )
        
        fig_peg.add_vline(
            x=peg_optimal,
            line_dash="dash",
            line_color="green",
            annotation_text=f"Optimal: {peg_optimal}%"
        )
        
        fig_peg.update_layout(
            title="PEG Optimization Curve",
            xaxis_title="PEG Density (%)",
            yaxis_title="Immune Evasion Score",
            height=350,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        
        st.plotly_chart(fig_peg, use_container_width=True)
    
    with col2:
        if peg_current < peg_optimal - 2:
            st.warning(f"⚠️ **Increase PEG**: Current {peg_current}% < Optimal {peg_optimal}%")
            st.write("Higher PEG will improve immune evasion and circulation time.")
        elif peg_current > peg_optimal + 2:
            st.warning(f"⚠️ **Reduce PEG**: Current {peg_current}% > Optimal {peg_optimal}%")
            st.write("Lower PEG will improve cellular targeting and uptake.")
        else:
            st.success(f"✅ **PEG Level Optimized**: {peg_current}% ≈ Optimal {peg_optimal}%")
            st.write("PEG density is well-balanced for immune evasion and targeting.")


if __name__ == "__main__":
    test_design = {
        "Size": 100,
        "Charge": -5,
        "Material": "Lipid NP",
        "Ligand": "GalNAc",
        "PEGDensity": 12,
        "SurfaceCoating": ["PEG (Stealth)"],
    }
    
    result = predict_immune_response(test_design)
    print(f"MPS Capture: {result['mps_capture']:.1f}%")
    print(f"Immune Evasion: {result['immune_evasion_score']:.1f}%")
    print(f"Optimal PEG: {result['optimal_peg_level']}%")
