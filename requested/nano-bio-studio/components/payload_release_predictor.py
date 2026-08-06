"""
Sprint 2: Payload Release & Bioavailability Predictor
Models drug release mechanisms and intracellular bioavailability
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np


def predict_payload_release(design_params):
    """
    Predict intracellular drug release and bioavailability
    
    Returns:
    {
        "release_mechanism": str,
        "burst_release": float (0-100),
        "sustained_release_24h": float (0-100),
        "sustained_release_72h": float (0-100),
        "intracellular_bioavailability": float (0-100),
        "time_to_50_release": float (hours),
        "release_location": dict,
        "bioavailability_score": float (0-100),
        "optimal_dosing_interval": str,
        "release_profile_data": dict  # time-series data
    }
    """
    
    material = design_params.get("Material", "Lipid NP")
    release_profile = design_params.get("ReleaseProfile", "Sustained (1 week)")
    encapsulation = design_params.get("Encapsulation", 85)
    charge = design_params.get("Charge", -5)
    hydrophobicity = design_params.get("Hydrophobicity") or 1.5
    size = design_params.get("Size", 100)
    drug_name = design_params.get("Drug", "Generic")
    
    # Base release mechanism by material
    material_release = {
        "Lipid NP": {"burst": 8, "mechanism": "Diffusion + lipid bilayer degradation", "t50": 6},
        "PLGA": {"burst": 12, "mechanism": "Polymer hydrolysis", "t50": 24},
        "DNA Origami": {"burst": 5, "mechanism": "pH-triggered strand displacement", "t50": 4},
        "Liposome": {"burst": 6, "mechanism": "Bilayer lipid exchange", "t50": 8},
        "Gold NP": {"burst": 3, "mechanism": "Surface desorption", "t50": 48},
        "Silica NP": {"burst": 10, "mechanism": "Pore-mediated diffusion", "t50": 36},
        "Polymeric NP": {"burst": 15, "mechanism": "Hydrolysis + swelling", "t50": 20},
        "Albumin NP": {"burst": 20, "mechanism": "Protein dissociation", "t50": 12},
    }
    
    material_info = material_release.get(material, {"burst": 10, "mechanism": "Unknown", "t50": 24})
    
    # Release profile adjustment
    release_params = {
        "Immediate": {"factor": 2.5, "duration": 1, "description": "Fast release"},
        "Sustained (1 week)": {"factor": 1.0, "duration": 7, "description": "1-week sustained"},
        "Sustained (2 weeks)": {"factor": 0.6, "duration": 14, "description": "2-week sustained"},
        "Sustained (1 month)": {"factor": 0.4, "duration": 30, "description": "1-month sustained"},
    }
    
    release_info = release_params.get(release_profile, {"factor": 1.0, "duration": 7})
    
    # Calculate burst release (initial rapid release)
    burst_release = material_info["burst"] * release_info["factor"]
    burst_release = min(40, burst_release)  # Cap at 40%
    
    # Calculate t50 (time to 50% release)
    t50_base = material_info["t50"] / release_info["factor"]
    t50_base *= (1 + (100 - encapsulation) / 100 * 0.5)  # Lower encapsulation = faster release
    
    # Charge effect on release
    if abs(charge) > 20:
        t50_base *= 1.2  # Electrostatic interactions slow release
    
    # Hydrophobicity effect
    if 1.0 <= hydrophobicity <= 3.0:
        t50_base *= 1.0
    elif hydrophobicity < 1.0:
        t50_base *= 0.8  # More hydrophilic = faster
    else:
        t50_base *= 1.3  # More hydrophobic = slower
    
    time_to_50_release = t50_base
    
    # Calculate 24h and 72h release
    # Using first-order kinetics
    k = np.log(2) / time_to_50_release
    
    release_24h = burst_release + (100 - burst_release) * (1 - np.exp(-k * 24))
    release_72h = burst_release + (100 - burst_release) * (1 - np.exp(-k * 72))
    
    cap_release_24h = min(100, release_24h)
    cap_release_72h = min(100, release_72h)
    
    # Release location (where drug becomes available)
    # Depends on trafficking
    endosomal_release = 40 * (encapsulation / 100)  # Some in acidic endosomes
    cytoplasmic_release = 35 * (encapsulation / 100)  # Some in cytoplasm
    lysosomal_release = 25 * (encapsulation / 100)  # Some degraded in lysosomes
    
    release_location = {
        "Endosomes (Acid Environment)": endosomal_release,
        "Cytoplasm": cytoplasmic_release,
        "Lysosomes (Degraded)": lysosomal_release,
        "Intact in NP": 100 - endosomal_release - cytoplasmic_release - lysosomal_release,
    }
    
    # Intracellular bioavailability (% of drug that's bioavailable for action)
    # Reduced by lysosomal degradation, improved by cytoplasmic release
    bioavail_factor = (
        (endosomal_release * 0.7) +  # 70% bioavailable in endosomes (pH effects)
        (cytoplasmic_release * 0.95) +  # 95% bioavailable in cytoplasm
        (lysosomal_release * 0.1)  # Only 10% survives lysosomal degradation
    ) / 100
    
    intracellular_bioavailability = cap_release_24h * bioavail_factor
    intracellular_bioavailability = min(100, max(0, intracellular_bioavailability))
    
    # Generate time-series release data (0-96 hours)
    times = np.linspace(0, 96, 50)
    releases = burst_release + (100 - burst_release) * (1 - np.exp(-k * times))
    releases = np.minimum(releases, 100)
    
    release_profile_data = {
        "time": times.tolist(),
        "release": releases.tolist(),
        "burst": burst_release,
        "t50": time_to_50_release,
    }
    
    # Bioavailability score combines:
    # - Fast onset (good for acute conditions)
    # - Sustained release (good for chronic)
    # - High bioavailability
    if "Immediate" in release_profile:
        bioavail_score = min(100, (cap_release_24h * 0.5 + intracellular_bioavailability * 0.5))
    else:
        bioavail_score = intracellular_bioavailability
    
    # Determine optimal dosing interval
    if cap_release_24h > 80:
        optimal_dosing = "Once daily (QD)"
        interval = 24
    elif cap_release_72h > 80:
        optimal_dosing = "Every 3 days"
        interval = 72
    elif time_to_50_release < 12:
        optimal_dosing = "Twice daily (BID)"
        interval = 12
    else:
        optimal_dosing = "Once daily or less frequent"
        interval = 24
    
    return {
        "release_mechanism": material_info["mechanism"],
        "burst_release": burst_release,
        "sustained_release_24h": cap_release_24h,
        "sustained_release_72h": cap_release_72h,
        "intracellular_bioavailability": intracellular_bioavailability,
        "time_to_50_release": time_to_50_release,
        "release_location": release_location,
        "bioavailability_score": bioavail_score,
        "optimal_dosing_interval": optimal_dosing,
        "release_profile_data": release_profile_data,
        "material_factor": material_info["burst"],
        "profile_type": release_profile,
        "encapsulation": encapsulation,
    }


def display_payload_release_widget(design_params):
    """Display payload release and bioavailability analysis"""
    
    result = predict_payload_release(design_params)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Bioavailability",
            f"{result['intracellular_bioavailability']:.1f}%",
            help="% of drug available for action inside cells"
        )
    
    with col2:
        st.metric(
            "24-Hour Release",
            f"{result['sustained_release_24h']:.1f}%",
            help="% released after 24 hours"
        )
    
    with col3:
        st.metric(
            "Time to 50%",
            f"{result['time_to_50_release']:.1f} hrs",
            help="Time for 50% drug release"
        )
    
    with col4:
        st.metric(
            "Bioavail. Score",
            f"{result['bioavailability_score']:.0f}/100",
            help="Overall bioavailability potential"
        )
    
    st.markdown("**Release Mechanism:**")
    st.write(f"🔹 {result['release_mechanism']}")
    st.write(f"📋 Profile: {result['profile_type']}")
    st.write(f"💊 Optimal Dosing: {result['optimal_dosing_interval']}")
    
    # Release kinetics chart
    st.markdown("**Release Kinetics Over Time:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        profile_data = result['release_profile_data']
        
        fig_release = go.Figure()
        
        fig_release.add_trace(go.Scatter(
            x=profile_data['time'],
            y=profile_data['release'],
            mode='lines+markers',
            name='Cumulative Release',
            line=dict(color='#4ECDC4', width=3),
            marker=dict(size=4),
            fill='tozeroy',
            fillcolor='rgba(78, 205, 196, 0.2)'
        ))
        
        # Add 50% reference line
        fig_release.add_hline(
            y=50,
            line_dash="dash",
            line_color="red",
            annotation_text=f"50% at {result['time_to_50_release']:.1f}h",
            annotation_position="right"
        )
        
        # Add burst release indicator
        fig_release.add_hline(
            y=result['burst_release'],
            line_dash="dot",
            line_color="orange",
            annotation_text=f"Burst: {result['burst_release']:.1f}%",
            annotation_position="left"
        )
        
        fig_release.update_layout(
            title="Intracellular Drug Release Profile",
            xaxis_title="Time (hours)",
            yaxis_title="Cumulative Release (%)",
            height=350,
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_range=[0, 105],
        )
        
        st.plotly_chart(fig_release, use_container_width=True)
    
    with col2:
        # Release location pie chart
        fig_location = go.Figure(data=[go.Pie(
            labels=list(result['release_location'].keys()),
            values=list(result['release_location'].values()),
            marker=dict(colors=['#FF6B6B', '#4ECDC4', '#F7DC6F', '#CCCCCC']),
            hoverinfo="label+percent+value",
            textposition="auto",
            textinfo="label+percent"
        )])
        
        fig_location.update_layout(
            title="Release Location Distribution",
            height=350,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        
        st.plotly_chart(fig_location, use_container_width=True)
    
    # Release metrics table
    st.markdown("**Release Metrics Summary:**")
    
    release_data = {
        "Timepoint": ["Burst", "24 Hours", "72 Hours", "Complete"],
        "Cumulative Release": [
            f"{result['burst_release']:.1f}%",
            f"{result['sustained_release_24h']:.1f}%",
            f"{result['sustained_release_72h']:.1f}%",
            "100%"
        ],
        "Status": [
            "⚡ Fast",
            "✓ Good" if result['sustained_release_24h'] > 60 else "⚠️ Slow",
            "✓ Good" if result['sustained_release_72h'] > 80 else "⚠️ Slow",
            "✓ Complete"
        ]
    }
    
    df_release = pd.DataFrame(release_data)
    st.dataframe(df_release, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    test_design = {
        "Material": "PLGA",
        "ReleaseProfile": "Sustained (1 week)",
        "Encapsulation": 85,
        "Charge": -5,
        "Hydrophobicity": 1.5,
        "Size": 100,
        "Drug": "Doxorubicin"
    }
    
    result = predict_payload_release(test_design)
    print(f"Mechanism: {result['release_mechanism']}")
    print(f"24h Release: {result['sustained_release_24h']:.1f}%")
    print(f"Bioavailability: {result['intracellular_bioavailability']:.1f}%")
    print(f"Optimal Dosing: {result['optimal_dosing_interval']}")
