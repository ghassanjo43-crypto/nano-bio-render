# ui/navbar.py
import streamlit as st

def render_navbar(tabs: list[str]):
    # Add CSS to reduce navigation button font size
    st.markdown("""
    <style>
    /* Reduce navbar button font size */
    [data-testid="stElementToolbar"] button {
        font-size: 0.75rem !important;
    }
    /* Target navigation buttons specifically */
    button[key^="nav__"] {
        font-size: 0.3rem !important;
        padding: 0.25rem 0.5rem !important;
        height: auto !important;
        min-height: 2.5rem;
    }
    /* Ensure text wraps properly */
    button {
        white-space: normal !important;
        word-break: break-word !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    cols = st.columns(len(tabs))
    for i, tab in enumerate(tabs):
        is_current = (st.session_state.current_tab == tab)
        with cols[i]:
            if st.button(
                tab,
                width='stretch',
                key=f"nav__{i}__{tab}",   # unique + stable
                type="primary" if is_current else "secondary",
            ):
                st.session_state.current_tab = tab
                st.rerun()
