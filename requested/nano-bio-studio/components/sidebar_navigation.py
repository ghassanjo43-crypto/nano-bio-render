"""
Sidebar Navigation with Collapsible Menu
Provides hierarchical navigation with expandable sections
"""
import streamlit as st
from pathlib import Path

def render_sidebar_navigation():
    """Render main sidebar navigation"""
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 📍 Main Navigation")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("🏠 Home", use_container_width=True):
                # SECURITY CONTAINMENT (2026-07-30): the session token is no longer
                # written to the URL. Bearer tokens in query strings leak via
                # browser history, server logs and Referer headers. st.session_state
                # already carries the token across st.switch_page within a session.
                st.switch_page("pages/0_Disease_Selection.py")
        
        st.markdown("---")
        
        # ML Training Collapsible Menu
        render_ml_training_menu()
        
        st.markdown("---")
        
        # Sitemap Download
        render_sitemap_download()
        
        st.markdown("---")
        
        if st.button("🔐 Logout", use_container_width=True):
            from streamlit_auth import StreamlitAuth
            StreamlitAuth.logout()
            st.query_params.clear()
            st.rerun()


def render_ml_training_menu():
    """Render collapsible ML Training menu"""
    with st.sidebar:
        st.markdown("### 🤖 ML Training Section")
        
        # Create collapsible/expandable menu
        with st.expander("📚 Training Pages", expanded=False):
            
            ml_pages = [
                ("🧠 AI Architecture", "pages/13_ML Training/1_AI_Architecture.py"),
                ("📚 Model Training Process", "pages/13_ML Training/2_Model_Training_Process.py"),
                ("🔧 Feature Engineering", "pages/13_ML Training/3_Feature_Engineering.py"),
                ("✅ Validation & Testing", "pages/13_ML Training/4_Validation_Testing.py"),
                ("📊 Dataset Statistics", "pages/13_ML Training/5_Dataset_Statistics.py"),
            ]
            
            for page_label, page_path in ml_pages:
                if st.button(page_label, use_container_width=True, key=f"ml_{page_path}"):
                    # SECURITY CONTAINMENT (2026-07-30): no token in the URL.
                    # See the note in render_main_navigation above.
                    st.switch_page(page_path)


def render_sitemap_download():
    """Render sitemap download link"""
    with st.sidebar:
        st.markdown("### 📋 Site Resources")
        
        sitemap_path = Path(__file__).parent.parent / "SITEMAP.html"
        
        if sitemap_path.exists():
            with open(sitemap_path, "rb") as f:
                sitemap_content = f.read()
            
            st.download_button(
                label="📥 Download Sitemap",
                data=sitemap_content,
                file_name="SITEMAP.html",
                mime="text/html",
                use_container_width=True,
                key="sitemap_download"
            )
            
            st.caption("Complete site navigation map")
        else:
            st.warning("⚠️ Sitemap not available")


__all__ = ["render_sidebar_navigation", "render_ml_training_menu", "render_sitemap_download"]
