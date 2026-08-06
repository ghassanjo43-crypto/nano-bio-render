"""
UI Components Module - Reusable UI components for all pages
Re-exported from biotech-lab-main with proper module path handling
"""

import streamlit as st
import sys
from pathlib import Path

# Ensure modules directory is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.trial_registry import get_trial_by_id


def render_trial_header():
    """
    Render persistent trial header bar
    Shows trial ID, disease, NP parameters, and drug info
    """
    if 'trial_id' in st.session_state and st.session_state.trial_id:
        trial_id = st.session_state.trial_id
        disease_name = st.session_state.get('trial_disease_name', 'Unknown')
        
        # Fetch trial details from registry
        trial_data = get_trial_by_id(trial_id)
        
        # Create header HTML
        header_html = f"""
        <div style="
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 5px solid #00d4ff;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin: 0; font-size: 1.2em;">Trial: {trial_id}</h3>
                    <p style="margin: 5px 0 0 0; font-size: 0.9em; opacity: 0.9;">Disease: {disease_name}</p>
                </div>
                <div style="text-align: right; font-size: 0.85em; opacity: 0.8;">
                    <p style="margin: 0;">Status: <strong>Active</strong></p>
                </div>
            </div>
        </div>
        """
        
        st.markdown(header_html, unsafe_allow_html=True)
