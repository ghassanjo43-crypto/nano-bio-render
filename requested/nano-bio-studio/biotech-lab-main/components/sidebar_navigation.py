"""
Sidebar Navigation - Minimal stub for Streamlit Cloud compatibility
"""
import streamlit as st

def render_sidebar_navigation():
    """Render sidebar navigation"""
    with st.sidebar:
        st.markdown("### Navigation")
        
        if st.button("🏠 Home"):
            st.switch_page("pages/00_Disease_Selection.py")
        
        if st.button("🔐 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

__all__ = ["render_sidebar_navigation"]
