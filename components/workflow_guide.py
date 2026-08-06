"""
Workflow Guide - Minimal stub for Streamlit Cloud compatibility
"""
import streamlit as st

def render_workflow_progress():
    """Render workflow progress indicator"""
    st.info("📍 Workflow Progress Indicator")

def render_step_header(step_num: int, title: str):
    """Render step header"""
    st.markdown(f"## Step {step_num}: {title}")

def render_navigation_buttons(prev_page: str = None, next_page: str = None):
    """Render navigation buttons"""
    col1, col2 = st.columns(2)
    if prev_page:
        with col1:
            if st.button("← Previous"):
                st.switch_page(prev_page)
    if next_page:
        with col2:
            if st.button("Next →"):
                st.switch_page(next_page)

def render_quick_start_guide():
    """Render quick start guide"""
    with st.expander("📚 Quick Start Guide"):
        st.markdown("1. Select a disease\n2. Choose parameters\n3. Run analysis")

__all__ = [
    "render_workflow_progress",
    "render_step_header",
    "render_navigation_buttons",
    "render_quick_start_guide"
]
