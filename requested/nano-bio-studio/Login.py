#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧬 NanoBio Studio — Main Entry Point
Connecting Nanotechnology & Biotechnology
Developed by Experts Group FZE

This file serves as the main Streamlit entry point for Streamlit Cloud deployment.
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import sys
from pathlib import Path

# Force UTF-8 on stdout/stderr. On Windows these default to the locale codepage
# (cp1252), which cannot encode the emoji used in status messages throughout the
# app -- a bare print() then raises UnicodeEncodeError and kills the page.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "biotech-lab-main"))

# ============================================================
# PAGE CONFIG - MUST BE FIRST
# ============================================================
st.set_page_config(
    page_title="NanoBio Studio Login",
    page_icon="🧬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============================================================
# DATABASE INITIALIZATION - Auto-create admin user on startup
# ============================================================
try:
    # DEFECT-D11 (Phase 2 Step 1): auth.py no longer initialises the database as
    # an import side effect. Startup initialisation is now explicit and
    # idempotent. This becomes a FastAPI lifespan / Alembic step after migration.
    from auth import initialize_database
    initialize_database()

    from db_init import ensure_admin_user_exists, ensure_admin_in_biotech_lab
    ensure_admin_user_exists()
    ensure_admin_in_biotech_lab()
except Exception as e:
    print(f"Database initialization warning: {e}")

# ============================================================
# IMPORT AND RUN LOGIN PAGE
# ============================================================

import logging
import time
from datetime import datetime
from streamlit_auth import StreamlitAuth, show_user_info, restore_session_from_persistent, check_session_timeout

logger = logging.getLogger(__name__)


def main():
    """Main login page"""

    st.title("🔐 NanoBio Studio Login")

    # Initialize session state
    StreamlitAuth.init_session_state()
    
    # ============================================================
    # TRY TO RESTORE SESSION FROM PERSISTENT STORAGE
    # ============================================================
    
    # SECURITY CONTAINMENT (2026-07-30)
    # -----------------------------------
    # The URL-query-parameter session restore was removed. It accepted a bearer
    # token from `?session_token=...`, and those tokens are both predictable
    # (`token_{username}_{unix_seconds}`) and leaked through browser history,
    # server logs and Referer headers. Any stale `session_token` still present in
    # a URL is now cleared and ignored rather than honoured.
    if "session_token" in st.query_params:
        st.query_params.clear()

    # Check if session token is in memory and still valid
    if st.session_state.get("session_token"):
        token = st.session_state.session_token
        if check_session_timeout(token):
            st.success("✅ You are already logged in!")
            show_user_info()
            st.divider()
            if st.button("→ Go to Disease Selection", type="primary", use_container_width=True):
                st.switch_page("pages/0_Disease_Selection.py")
            st.info("Or use the browser back button to continue")
            return
        else:
            # Session timed out
            st.warning("⏰ Your session has expired due to inactivity (30 minutes). Please log in again.")
            StreamlitAuth.logout()
            st.query_params.clear()

    # If already authenticated in memory, redirect to main app
    if StreamlitAuth.is_authenticated() or (st.session_state.get("logged_in") and st.session_state.get("username")):
        st.success("✅ You are already logged in!")
        
        show_user_info()
        
        st.divider()
        
        if st.button("→ Go to Disease Selection", type="primary", use_container_width=True):
            st.switch_page("pages/0_Disease_Selection.py")
        
        st.info("Or use the browser back button to continue")

        return

    # ============================================================
    # TABS FOR LOGIN AND SIGNUP
    # ============================================================
    tab1, tab2 = st.tabs(["🔓 Sign In", "📝 Sign Up"])
    
    with tab1:
        st.subheader("Sign In to Your Account")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # SECURITY CONTAINMENT (2026-07-30): the default admin credentials
            # were printed here for every visitor. Removed.
            st.markdown("### Research Use Only")
            st.warning(
                "This platform is for **research use only**. It does not provide "
                "clinical diagnoses or treatment decisions. Simulated and "
                "predicted outputs are not experimentally validated."
            )

        with col2:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("Sign In", type="primary", use_container_width=True, key="signin_btn"):
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    # Authenticate using the auth module
                    from auth import authenticate
                    
                    # authenticate returns (success: bool, role: Optional[str])
                    success, role = authenticate(username, password)
                    
                    if success:
                        # Set session state for both old and new systems
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role or "viewer"
                        
                        # Also set StreamlitAuth session (creates persistent session)
                        token = StreamlitAuth.login(
                            user_id=username,
                            username=username,
                            email="",
                            roles=[role or "viewer"]
                        )
                        
                        st.session_state.session_token = token
                        
                        st.success(f"✅ Welcome {username}!")
                        
                        # Show user info
                        show_user_info()
                        
                        time.sleep(0.5)

                        # SECURITY CONTAINMENT (2026-07-30): the token is no
                        # longer appended to the URL. st.session_state carries it
                        # across st.switch_page within the browser session.
                        st.switch_page("pages/0_Disease_Selection.py")
                    else:
                        st.error("❌ Invalid username or password")
    
    with tab2:
        st.subheader("Create a New Account")
        
        with st.form("signup_form", clear_on_submit=True):
            signup_username = st.text_input(
                "Username",
                help="Username must be unique and at least 3 characters",
                key="signup_user"
            )
            signup_email = st.text_input(
                "Email (Optional)",
                help="Your email address for account recovery",
                key="signup_email"
            )
            signup_password = st.text_input(
                "Password",
                type="password",
                help="Password must be at least 6 characters with letters and numbers",
                key="signup_pass"
            )
            signup_password_confirm = st.text_input(
                "Confirm Password",
                type="password",
                key="signup_pass_confirm"
            )
            
            submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
            
            if submitted:
                # Validate inputs
                if not signup_username or not signup_password:
                    st.error("❌ Please enter username and password")
                elif len(signup_username) < 3:
                    st.error("❌ Username must be at least 3 characters")
                elif len(signup_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                elif signup_password != signup_password_confirm:
                    st.error("❌ Passwords do not match")
                else:
                    # Register user
                    from auth import register_user
                    
                    success, message = register_user(
                        username=signup_username,
                        password=signup_password,
                        email=signup_email or "",
                        role="student"
                    )
                    
                    if success:
                        st.success(f"✅ Account created successfully! You can now sign in.")
                        st.info(f"Welcome, {signup_username}! Your account has been created as a Student. Go to the Sign In tab to log in.")
                    else:
                        st.error(f"❌ {message}")


if __name__ == "__main__":
    main()

