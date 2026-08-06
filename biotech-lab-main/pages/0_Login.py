"""
Login Page

User authentication interface for the NanoBio Studio.

Development accounts come from the environment
--------------------------------------------------------------------------
This page previously compared the typed password against three short literals
and *printed all three on the form*. That is a working credential set committed
to source, displayed to every visitor, and shipped in every archive built from
the tree. The literals are gone rather than replaced, and are deliberately not
quoted here: a document that names a retired password keeps it searchable, and
these were reused widely enough to be worth burying.

The accounts are now defined by environment variables. If none is set, demo
sign-in is **unavailable** rather than falling back to a default — a fallback
default is the same defect with an extra step, and the whole point is that a
password should not be recoverable by reading the source.

    NANOBIO_DEMO_ADMIN_PASSWORD
    NANOBIO_DEMO_SCIENTIST_PASSWORD
    NANOBIO_DEMO_VIEWER_PASSWORD

Generate one with:

    python -c "import secrets; print(secrets.token_urlsafe(24))"

This is a legacy Streamlit surface. It performs string comparison against
environment values and is not the platform's authentication system; the FastAPI
backend under `nanobio_studio_backend/` is. It must not be exposed to anything
that is not a local development instance.
"""

import hmac
import logging
import os
import time
from datetime import datetime

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
from streamlit_auth import StreamlitAuth, show_user_info


logger = logging.getLogger(__name__)

#: Demo accounts: username -> (env var holding the password, user id, email,
#: roles). No password is stored here, and no default is supplied.
DEMO_ACCOUNTS = {
    "admin": ("NANOBIO_DEMO_ADMIN_PASSWORD", "user_001",
              "admin@nanobio.local", ["admin"]),
    "scientist": ("NANOBIO_DEMO_SCIENTIST_PASSWORD", "user_002",
                  "scientist@nanobio.local", ["scientist"]),
    "viewer": ("NANOBIO_DEMO_VIEWER_PASSWORD", "user_003",
               "viewer@nanobio.local", ["viewer"]),
}


def configured_accounts() -> dict[str, tuple[str, str, list[str]]]:
    """Accounts whose password variable is actually set.

    An account with no configured password is simply absent, so an unset
    variable cannot be signed in to with the empty string.
    """
    available = {}
    for username, (env_var, user_id, email, roles) in DEMO_ACCOUNTS.items():
        password = os.environ.get(env_var, "")
        if password.strip():
            available[username] = (password, user_id, email, roles)
    return available


def check_demo_password(username: str, password: str):
    """Return the account tuple on a match, or None.

    Compared with ``hmac.compare_digest`` so the check does not leak the
    password's length or its matching prefix through timing. The equality here
    is trivially cheap either way, but a plain ``==`` in an authentication path
    is a pattern worth not copying forward.
    """
    account = configured_accounts().get(username)
    if account is None:
        return None
    expected, user_id, email, roles = account
    if hmac.compare_digest(password, expected):
        return user_id, email, roles
    return None

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
        # Usernames are listed; passwords are not. A form that prints the
        # password next to the username is not a login form.
        available = configured_accounts()
        if available:
            st.write("Development accounts configured:")
            for name in DEMO_ACCOUNTS:
                if name in available:
                    st.write(f"- **{name}**")
            st.caption(
                "Passwords come from the environment and are not shown here. "
                "See the module docstring for the variable names.")
        else:
            st.warning(
                "No development account is configured, so sign-in is "
                "unavailable on this page.")
            st.caption(
                "Set NANOBIO_DEMO_ADMIN_PASSWORD (and optionally the "
                "SCIENTIST and VIEWER equivalents) to enable it. There is no "
                "built-in default password."
            )

    with col2:
        username = st.text_input("Username", placeholder="Enter username")

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
        )

        login_btn = st.button("Login", use_container_width=True, type="primary")

    if login_btn:
        # Development authentication against environment-supplied credentials.
        # Not the platform's authentication system — see the module docstring.
        matched = check_demo_password(username, password)
        auth_success = matched is not None
        user_id, email, roles = matched if matched else (None, None, [])

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
