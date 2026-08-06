"""
Streamlit Authentication Module

Session management and auth UI for Streamlit pages.
Simplified version without complex JWT/RBAC dependencies.
Includes persistent session storage and idle timeout (15 minutes).
"""

import streamlit as st
import logging
import json
import os
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Session storage file
SESSIONS_FILE = Path(__file__).parent / "sessions.json"

# Idle timeout in seconds (15 minutes)
IDLE_TIMEOUT_SECONDS = 900

# Explicit exports for clarity and Cloud compatibility
__all__ = [
    'StreamlitAuth',
    'show_user_info',
    'restore_session_from_persistent',
    'check_session_timeout',
    'switch_page_with_token',
    'require_login',
    'require_permission',
    'load_persistent_sessions',
    'save_persistent_sessions',
    'create_persistent_session',
    'get_persistent_session',
    'update_last_activity',
    'clear_persistent_session',
]


# ============================================================
# PERSISTENT SESSION MANAGEMENT
# ============================================================

def load_persistent_sessions() -> dict:
    """Load all persistent sessions from file"""
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            return {}
    return {}


def save_persistent_sessions(sessions: dict):
    """Save persistent sessions to file"""
    try:
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(sessions, f, default=str, indent=2)
    except Exception as e:
        logger.error(f"Error saving sessions: {e}")


def create_persistent_session(username: str, user_id: str, email: str, roles: list) -> str:
    """Create and persist a new session"""
    sessions = load_persistent_sessions()
    
    # Create session token
    token = f"token_{user_id}_{int(datetime.utcnow().timestamp())}"
    
    # Store session with timestamps
    sessions[token] = {
        "username": username,
        "user_id": user_id,
        "email": email,
        "roles": roles,
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
    }
    
    save_persistent_sessions(sessions)
    return token


def get_persistent_session(token: str) -> Optional[dict]:
    """Get persistent session data"""
    sessions = load_persistent_sessions()
    return sessions.get(token)


def update_last_activity(token: str):
    """Update last activity timestamp for a session"""
    sessions = load_persistent_sessions()
    
    if token in sessions:
        sessions[token]["last_activity"] = datetime.utcnow().isoformat()
        save_persistent_sessions(sessions)


def check_session_timeout(token: str) -> bool:
    """
    Check if session has timed out due to inactivity.
    Returns True if session is still valid, False if timed out.
    """
    session = get_persistent_session(token)
    
    if not session:
        return False
    
    # Parse last activity timestamp
    try:
        last_activity = datetime.fromisoformat(session["last_activity"])
        now = datetime.utcnow()
        elapsed = (now - last_activity).total_seconds()
        
        if elapsed > IDLE_TIMEOUT_SECONDS:
            # Session timed out, remove it
            sessions = load_persistent_sessions()
            del sessions[token]
            save_persistent_sessions(sessions)
            return False
        
        return True
    except Exception as e:
        logger.error(f"Error checking session timeout: {e}")
        return False


def restore_session_from_persistent(token: str):
    """Restore session state from persistent storage"""
    session = get_persistent_session(token)
    
    if not session:
        return False
    
    # Check if session has timed out
    if not check_session_timeout(token):
        return False
    
    # Update last activity
    update_last_activity(token)
    
    # Restore session state
    st.session_state.authenticated = True
    st.session_state.user_id = session["user_id"]
    st.session_state.username = session["username"]
    st.session_state.email = session["email"]
    st.session_state.roles = session["roles"]
    st.session_state.permissions = []
    st.session_state.token = token
    st.session_state.login_time = datetime.fromisoformat(session["created_at"])
    
    # Also set logged_in for new system
    st.session_state.logged_in = True
    st.session_state.session_token = token
    
    return True


def clear_persistent_session(token: str):
    """Remove a session from persistent storage"""
    sessions = load_persistent_sessions()
    if token in sessions:
        del sessions[token]
        save_persistent_sessions(sessions)


# ============================================================
# STREAMLIT AUTH CLASS
# ============================================================


class StreamlitAuth:
    """Streamlit authentication utilities"""

    @staticmethod
    def init_session_state():
        """Initialize Streamlit session state"""
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
        if "user_id" not in st.session_state:
            st.session_state.user_id = None
        if "username" not in st.session_state:
            st.session_state.username = None
        if "email" not in st.session_state:
            st.session_state.email = None
        if "roles" not in st.session_state:
            st.session_state.roles = []
        if "permissions" not in st.session_state:
            st.session_state.permissions = []
        if "token" not in st.session_state:
            st.session_state.token = None
        if "login_time" not in st.session_state:
            st.session_state.login_time = None
        if "session_token" not in st.session_state:
            st.session_state.session_token = None

    @staticmethod
    def login(
        user_id: str,
        username: str,
        email: str,
        roles: list,
    ) -> str:
        """
        Login user and create session (both in-memory and persistent).

        Args:
            user_id: User ID
            username: Username
            email: Email address
            roles: User roles

        Returns:
            Session token
        """
        # Create persistent session for page refresh support
        token = create_persistent_session(username, user_id, email, roles)

        # Update in-memory session state
        st.session_state.authenticated = True
        st.session_state.user_id = user_id
        st.session_state.username = username
        st.session_state.email = email
        st.session_state.roles = roles
        st.session_state.permissions = []
        st.session_state.token = token
        st.session_state.session_token = token
        st.session_state.login_time = datetime.utcnow()
        
        # Also set logged_in for new system
        st.session_state.logged_in = True

        logger.info(f"User logged in: {username}")
        return token

    @staticmethod
    def logout():
        """Logout user"""
        # Clear persistent session
        if st.session_state.get("session_token"):
            clear_persistent_session(st.session_state.session_token)
        
        # Clear in-memory session state
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.email = None
        st.session_state.roles = []
        st.session_state.permissions = []
        st.session_state.token = None
        st.session_state.login_time = None
        st.session_state.session_token = None
        st.session_state.logged_in = False

        logger.info("User logged out")

    @staticmethod
    def check_and_restore_session():
        """
        Check for existing persistent session on page load.
        Restores session if valid and not timed out.
        """
        StreamlitAuth.init_session_state()
        
        # If already authenticated in memory, update last activity
        if st.session_state.get("session_token"):
            token = st.session_state.session_token
            if check_session_timeout(token):
                update_last_activity(token)
                return True
            else:
                # Session timed out
                StreamlitAuth.logout()
                return False
        
        return False

    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated"""
        StreamlitAuth.init_session_state()
        return st.session_state.authenticated

    @staticmethod
    def get_current_user() -> Optional[dict]:
        """Get current user info"""
        StreamlitAuth.init_session_state()

        if not st.session_state.authenticated:
            return None

        return {
            "user_id": st.session_state.user_id,
            "username": st.session_state.username,
            "email": st.session_state.email,
            "roles": st.session_state.roles,
            "permissions": st.session_state.permissions,
        }

    @staticmethod
    def require_role(role: str) -> bool:
        """Check if current user has role"""
        user = StreamlitAuth.get_current_user()

        if not user:
            return False

        return role in user["roles"]

    @staticmethod
    def require_login_with_persistence(page_name: str = "This page") -> bool:
        """
        Check if user is logged in, restore from persistent session if needed,
        and check for timeout. Use this in all pages that require authentication.
        
        Returns True if user is authenticated and not timed out.
        Returns False if not authenticated or timed out (displays warning).
        
        Usage:
            from streamlit_auth import StreamlitAuth
            
            if not StreamlitAuth.require_login_with_persistence():
                st.stop()
        """
        StreamlitAuth.init_session_state()
        
        # Try to restore session from URL query parameters
        query_params = st.query_params
        if "session_token" in query_params:
            token = query_params.get("session_token", "")
            if token:
                restore_session_from_persistent(token)
        
        # Check if user is logged in
        logged_in = st.session_state.get("logged_in") or st.session_state.get("authenticated")
        
        if not logged_in:
            st.warning(f"🔒 {page_name} requires login")
            return False
        
        # Check for session timeout
        if st.session_state.get("session_token"):
            token = st.session_state.session_token
            if not check_session_timeout(token):
                st.warning("⏰ Your session has expired due to inactivity (15 minutes). Please log in again.")
                StreamlitAuth.logout()
                return False
        
        return True


def require_login(page_name: str = "This page") -> bool:
    """
    Check if user is logged in via the main App.py authentication system.
    
    Usage:
        if not require_login("ML Training"):
            return
    """
    # Check if user is logged in via App.py session state
    if "logged_in" in st.session_state and st.session_state.logged_in and st.session_state.username:
        return True
    
    # Fallback to StreamlitAuth
    StreamlitAuth.init_session_state()
    if StreamlitAuth.is_authenticated():
        return True
    
    # Not logged in - show warning but don't call st.stop() to allow graceful fallback
    st.warning(f"🔒 {page_name} requires login")
    st.info("Please log in using the login area in the sidebar")
    return False


def require_permission(permission, page_name: str = "This feature") -> bool:
    """
    Check if user has required permission.
    
    Usage:
        if not require_permission(Permission.MODEL_TRAIN, "Model training"):
            return
    """
    # First check if user is logged in
    if not require_login(page_name):
        return False
    
    # For now, allow all permissions if user is logged in
    # TODO: Implement role-based permission checking
    return True


def show_user_info():
    """Display current user information"""
    user = StreamlitAuth.get_current_user()

    if user:
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.write(f"**User:** {user['username']}")

        with col2:
            roles_str = ", ".join(user["roles"]) if user["roles"] else "None"
            st.write(f"**Roles:** {roles_str}")

        with col3:
            if st.button("Logout", key="logout_btn"):
                StreamlitAuth.logout()
                st.rerun()


def switch_page_with_token(page_path: str):
    """
    Switch to another page while maintaining session token in URL.
    
    Usage:
        from streamlit_auth import switch_page_with_token
        
        if st.button("Next"):
            switch_page_with_token("pages/next_page.py")
    """
    if st.session_state.get("session_token"):
        st.query_params["session_token"] = st.session_state.session_token
    st.switch_page(page_path)
