# ui/disclaimer.py
import streamlit as st

def render_disclaimer():
    st.info("⚠️ Educational & research use only. Not for clinical diagnosis/treatment. Expand for full disclaimer.")
    with st.expander("⚠️ IMPORTANT DISCLAIMER — click to expand/collapse", expanded=False):
        st.markdown("""
<div style='background-color:#fff3cd; border-left:5px solid #ffc107; padding:15px; border-radius:5px;'>
  <h4 style='color:#856404; margin-top:0;'>⚠️ IMPORTANT NOTICE</h4>
  <ul style='color:#856404;'>
    <li>Not for medical diagnosis, treatment, or clinical decision-making.</li>
    <li>Computational outputs may not reflect real-world outcomes.</li>
    <li>Validate designs experimentally using proper lab procedures.</li>
    <li>Users assume responsibility for any decisions made using this tool.</li>
  </ul>
</div>
<div style='background-color:#f8f9fa; border:1px solid #dee2e6; padding:12px; margin-top:10px; border-radius:4px;'>
  <p style='margin:0; font-weight:bold;'>📋 INTELLECTUAL PROPERTY NOTICE</p>
  <p style='margin:5px 0 0 0;'>This application is the intellectual property of <b>Experts Group FZE</b></p>
  <p style='margin:2px 0;'>📞 <b>Mobile:</b> 00 971 50 6690381</p>
  <p style='margin:2px 0 0 0;'>📧 <b>Email:</b> info@expertsgroup.me</p>
</div>
        """, unsafe_allow_html=True)
