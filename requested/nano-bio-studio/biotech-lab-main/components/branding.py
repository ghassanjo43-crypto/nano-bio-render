"""
Branding components - Minimal stubs for Streamlit Cloud compatibility
"""
import streamlit as st

def render_brand_header():
    """Render brand header"""
    col1, col2 = st.columns([2, 1])
    with col1:
        st.title("🧬 NanoBio Studio")
        st.caption("Connecting Nanotechnology & Biotechnology")
    with col2:
        st.markdown("### © Experts Group FZE")
        st.caption("Confidential / Proprietary")

def render_brand_footer():
    """Render brand footer"""
    st.divider()
    st.markdown("---")
    st.caption("© 2024 Experts Group FZE. All rights reserved.")

def render_ip_notice():
    """Render IP notice"""
    st.info("⚠️ This application and all data are proprietary and confidential.")

def render_research_disclaimer():
    """Render research disclaimer"""
    st.warning("This is a research application not approved for clinical use.")

def render_sidebar_branding():
    """Render sidebar branding"""
    with st.sidebar:
        st.markdown("🧬 **NanoBio Studio**")
        st.caption("Experts Group FZE")

def render_licensing_contact():
    """Render licensing contact info"""
    st.info("For licensing inquiries, contact: info@expertsgroup.ae")

__all__ = [
    "render_brand_header",
    "render_brand_footer", 
    "render_ip_notice",
    "render_research_disclaimer",
    "render_sidebar_branding",
    "render_licensing_contact"
]

