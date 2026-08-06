# tabs/home.py
import streamlit as st
import json
from datetime import datetime
import numpy as np

from core.scoring import compute_impact, validate_parameter, get_recommendations, overall_score_from_impact

#from core.scoring import compute_impact, validate_parameter, get_recommendations
from viz.dial import show_circular_dial



def render(plotly_ok: bool):
    st.header("🏠 NanoBio Studio Dashboard")

    d = st.session_state.design
    impact = compute_impact(d)

    overall = float(np.clip(
        (impact["Delivery"] * 0.6) + ((10 - impact["Toxicity"]) * 3) + ((100 - impact["Cost"]) * 0.1),
        0, 100
    ))

    st.markdown("### 📊 Current Design Summary")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Particle Size", f"{d['Size']} nm")
        st.caption(f"{validate_parameter('Size', d['Size'], [80, 120])} Optimal: 80–120nm")
    with c2:
        st.metric("Surface Charge", f"{d['Charge']} mV")
        st.caption(f"{validate_parameter('Charge', abs(d['Charge']), [0, 10])} Optimal: ±10mV")
    with c3:
        st.metric("Encapsulation", f"{d['Encapsulation']}%")
        st.caption(f"{validate_parameter('Encapsulation', d['Encapsulation'], [80, 100])} Target: >80%")

    st.markdown("### ⚡ Overall Score")
    show_circular_dial(overall)

    st.markdown("### 📤 Export Your Design")
    design_json = json.dumps(d, indent=2)
    st.download_button(
        "📥 Download Design as JSON",
        data=design_json,
        file_name=f"nanoparticle_design_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        key="dl_design_json_home",
    )

    st.markdown("### 💡 Recommendations")
    for rec in get_recommendations(d):
        st.write(rec)
