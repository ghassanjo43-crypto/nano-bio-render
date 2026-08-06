# ui/readme_panel.py
import streamlit as st
from pathlib import Path

def render_readme():
    readme_path = Path(__file__).resolve().parents[1] / "README.md"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
        with st.expander("📘 About NanoBio Studio — Click to expand"):
            st.markdown(content, unsafe_allow_html=True)
    else:
        st.info("ℹ️ README.md not found.")
