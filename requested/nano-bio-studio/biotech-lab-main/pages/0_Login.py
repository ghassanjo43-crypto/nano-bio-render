"""
Login Page

User authentication interface for the NanoBio Studio.
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import logging
import time
from datetime import datetime
from streamlit_auth import StreamlitAuth, show_user_info


logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Login",
    page_icon="🔐",
    layout="centered",
)


def main():
    """Main login page"""

    st.title("🔐 NanoBio Studio Login")

    # Initialize session state
    StreamlitAuth.init_session_state()

    # If already authenticated, check for logged_in as well and redirect to main app
    if StreamlitAuth.is_authenticated() or (st.session_state.get("logged_in") and st.session_state.get("username")):
        st.success("✅ You are already logged in!")
        
        show_user_info()
        
        st.divider()
        
        if st.button("→ Go to Main App", type="primary", use_container_width=True):
            st.rerun()
        
        st.info("You are logged in. Refresh the page or navigate to another section.")

        return

    # Login form
    st.subheader("Sign In")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("Demo Accounts:")
        st.write("**Admin**")
        st.code("user: admin\npass: admin123")

        st.write("**Scientist**")
        st.code("user: scientist\npass: science123")

        st.write("**Viewer**")
        st.code("user: viewer\npass: view123")

    with col2:
        username = st.text_input("Username", placeholder="Enter username")

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
        )

        login_btn = st.button("Login", use_container_width=True, type="primary")

    if login_btn:
        # Demo authentication (in production, use real database/auth service)
        auth_success = False
        user_id = None
        email = None
        roles = []

        if username == "admin" and password == "admin123":
            auth_success = True
            user_id = "user_001"
            email = "admin@nanobio.com"
            roles = ["admin"]

        elif username == "scientist" and password == "science123":
            auth_success = True
            user_id = "user_002"
            email = "scientist@nanobio.com"
            roles = ["scientist"]

        elif username == "viewer" and password == "view123":
            auth_success = True
            user_id = "user_003"
            email = "viewer@nanobio.com"
            roles = ["viewer"]

        if auth_success:
            # Create login
            token = StreamlitAuth.login(
                user_id=user_id,
                username=username,
                email=email,
                roles=roles,
            )
            
            # Also set the App.py session state for compatibility
            st.session_state.logged_in = True
            st.session_state.username = username

            st.success(f"✅ Welcome, {username}!")
            st.balloons()

            logger.info(f"User logged in: {username}")
            
            # Redirect to main app
            time.sleep(0.5)  # Brief delay to show success message
            st.rerun()

        else:
            st.error("❌ Invalid username or password")
            logger.warning(f"Failed login attempt for user: {username}")

    # Info section
    st.divider()

    st.subheader("About NanoBio Studio")

    st.markdown("""
    **NanoBio Studio** is an integrated platform for biotech research and analysis.

    ### Features:
    - 🤖 **ML Training** - Build and train machine learning models
    - 🏆 **Candidate Ranking** - Rank formulations by multiple criteria
    - 📦 **Model Management** - Monitor and manage trained models
    - 📊 **Data Analysis** - Explore and analyze biotech data
    - 📋 **Workflow Management** - Manage research workflows

    ### Getting Started:
    1. Login with your credentials
    2. Navigate to desired feature using the sidebar
    3. Follow the guided workflows

    ### Need Help?
    - Check the tutorials page
    - Read the documentation
    - Contact support

    ---

    **Version**: 3.0 (Phase 3 - ML Integration)
    **Last Updated**: March 2026
    """)


if __name__ == "__main__":
    main()
