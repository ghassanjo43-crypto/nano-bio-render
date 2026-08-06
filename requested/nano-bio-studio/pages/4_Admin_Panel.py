"""
🔐 Admin Panel - User Management Interface
Enable admins to manage user accounts: create, activate, deactivate, delete, and edit
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
from datetime import datetime
import sqlite3

# ============================================================
# PAGE SETUP
# ============================================================
st.set_page_config(page_title="Admin Panel", page_icon="🔐", layout="wide")

# ============================================================
# DATABASE INITIALIZATION - Auto-create admin user on startup
# ============================================================
try:
    from db_init import ensure_admin_user_exists, ensure_admin_in_biotech_lab
    ensure_admin_user_exists()
    ensure_admin_in_biotech_lab()
except Exception as e:
    print(f"⚠️ Database initialization warning: {e}")

# ============================================================
# AUTHENTICATION CHECK
# ============================================================
# Import auth functions
from auth import (
    get_user_info, list_users_detailed, update_user_role,
    deactivate_user, activate_user, delete_user, reset_password,
    register_user, change_password, get_user_role
)

# Check if user is logged in
if not st.session_state.get("logged_in"):
    st.error("❌ Please log in first")
    st.stop()

# Get the user's actual role from session state or database
user_role = st.session_state.get("role")
username = st.session_state.get("username")

# If role not in session state, try to fetch from auth system
if not user_role and username:
    try:
        user_role = get_user_role(username)
        st.session_state.role = user_role
    except:
        pass

# Check if user is admin
if user_role != "admin":
    st.error(f"❌ Only admins can access this panel. Your role: {user_role or 'Unknown'}")
    st.stop()

st.title("🔐 Admin Panel")
st.write("Manage user accounts and system settings")

# ============================================================
# MAIN TABS
# ============================================================
admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5 = st.tabs([
    "👥 Manage Users",
    "➕ Create User",
    "🔐 Reset Password",
    "👤 My Account",
    "📋 Activity Log"
])

# ============================================================
# Tab 1: Manage Users (Enhanced with inline editing)
# ============================================================
with admin_tab1:
    st.subheader("👥 Manage Users")
    st.write("View, edit, and manage all user accounts")
    
    try:
        users = list_users_detailed()
        if users:
            st.write(f"**Total users:** {len(users)}")
            st.divider()
            
            # Search/filter users
            search_term = st.text_input("🔍 Search users by username or email", key="user_search")
            
            # Filter users based on search
            if search_term:
                filtered_users = [u for u in users if search_term.lower() in u.get("username", "").lower() or search_term.lower() in u.get("email", "").lower()]
            else:
                filtered_users = users
            
            if filtered_users:
                for user in filtered_users:
                    with st.expander(f"👤 {user['username']} ({user['role'].upper()}) - {user['email']}", expanded=False):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # Display user info
                            st.markdown("### User Details")
                            info_col1, info_col2 = st.columns(2)
                            
                            with info_col1:
                                st.write(f"**Username:** `{user['username']}`")
                                st.write(f"**Email:** {user['email'] or '(not set)'}")
                                st.write(f"**Role:** {user['role']}")
                            
                            with info_col2:
                                status_text = "🟢 Active" if user.get('is_active', True) else "🔴 Inactive"
                                st.write(f"**Status:** {status_text}")
                                st.write(f"**Created:** {user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'}")
                                st.write(f"**Last Login:** {user.get('last_login', 'Never') or 'Never'}")
                            
                            st.divider()
                            
                            # Edit email
                            st.markdown("### Edit Email")
                            new_email = st.text_input(
                                "New email address (leave blank to keep current)",
                                value=user.get('email', ''),
                                key=f"email_{user['username']}"
                            )
                            
                            if st.button("✅ Update Email", key=f"email_update_{user['username']}", use_container_width=True):
                                if new_email != user.get('email', ''):
                                    try:
                                        conn = sqlite3.connect("users.db")
                                        c = conn.cursor()
                                        c.execute("UPDATE users SET email = ? WHERE username = ?", (new_email or None, user['username']))
                                        conn.commit()
                                        conn.close()
                                        st.success(f"✅ Email updated for {user['username']}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                                else:
                                    st.info("No changes to save")
                            
                            st.divider()
                            
                            # Change role
                            st.markdown("### Change Role")
                            current_role = user['role']
                            new_role = st.selectbox(
                                f"Select new role for {user['username']}",
                                ["admin", "research", "educator", "student", "viewer"],
                                index=["admin", "research", "educator", "student", "viewer"].index(current_role),
                                key=f"role_{user['username']}"
                            )
                            
                            if st.button("✅ Update Role", key=f"role_update_{user['username']}", use_container_width=True):
                                if new_role != current_role:
                                    if update_user_role(user['username'], new_role):
                                        st.success(f"✅ Role updated: {user['username']} → {new_role}")
                                        st.rerun()
                                    else:
                                        st.error("Failed to update role")
                                else:
                                    st.info("Role unchanged")
                            
                            st.divider()
                            
                            # Password reset
                            st.markdown("### Reset Password")
                            new_temp_password = st.text_input(
                                f"New password for {user['username']}",
                                type="password",
                                key=f"pwd_{user['username']}"
                            )
                            
                            if st.button("🔐 Reset Password", key=f"pwd_reset_{user['username']}", use_container_width=True):
                                if new_temp_password:
                                    success, msg = reset_password(user['username'], new_temp_password)
                                    if success:
                                        st.success(f"✅ Password reset for {user['username']}")
                                    else:
                                        st.error(f"❌ {msg}")
                                else:
                                    st.warning("Please enter a new password")
                        
                        with col2:
                            st.markdown("### Actions")
                            
                            # Activate/Deactivate
                            if user.get('is_active', True):
                                if st.button("🔴 Deactivate Account", key=f"deactivate_{user['username']}", use_container_width=True, help="Disable this account"):
                                    success, msg = deactivate_user(user['username'])
                                    if success:
                                        st.success(f"✅ {msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")
                            else:
                                if st.button("🟢 Activate Account", key=f"activate_{user['username']}", use_container_width=True, help="Enable this account"):
                                    success, msg = activate_user(user['username'])
                                    if success:
                                        st.success(f"✅ {msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")
                            
                            st.divider()
                            
                            # Delete user
                            if st.button("🗑️ Delete Account", key=f"delete_{user['username']}", use_container_width=True, help="Permanently delete this user"):
                                # Store deletion intent
                                if st.session_state.get(f"confirm_delete_{user['username']}"):
                                    try:
                                        if delete_user(user['username']):
                                            st.success(f"✅ User {user['username']} deleted")
                                            st.session_state[f"confirm_delete_{user['username']}"] = False
                                            st.rerun()
                                        else:
                                            st.error("Failed to delete user")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                                else:
                                    st.warning("⚠️ Click again to confirm deletion")
                                    st.session_state[f"confirm_delete_{user['username']}"] = True
            else:
                st.info("No users found matching your search")
        else:
            st.info("No users found")
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================================
# Tab 2: Create User
# ============================================================
with admin_tab2:
    st.subheader("➕ Create New User")
    st.write("Add a new user to the system")
    
    with st.form("create_user_form"):
        create_username = st.text_input(
            "Username",
            help="3+ characters, alphanumeric"
        )
        create_email = st.text_input(
            "Email",
            help="Optional"
        )
        create_password = st.text_input(
            "Password",
            type="password",
            help="6+ characters"
        )
        create_password_confirm = st.text_input(
            "Confirm Password",
            type="password"
        )
        create_role = st.selectbox(
            "Role",
            ["student", "educator", "research", "admin", "viewer"],
            index=0
        )
        
        if st.form_submit_button("Create User", use_container_width=True):
            if len(create_username) < 3:
                st.error("❌ Username must be at least 3 characters")
            elif len(create_password) < 6:
                st.error("❌ Password must be at least 6 characters")
            elif create_password != create_password_confirm:
                st.error("❌ Passwords do not match")
            else:
                success, msg = register_user(create_username, create_password, create_email, create_role)
                if success:
                    st.success(f"✅ {msg}")
                    st.success(f"✓ User '{create_username}' created successfully!")
                else:
                    st.error(f"❌ {msg}")

# ============================================================
# Tab 3: Reset Password
# ============================================================
with admin_tab3:
    st.subheader("🔐 Reset Password")
    st.write("Reset any user's password")
    
    with st.form("reset_password_form"):
        reset_username = st.selectbox(
            "Select user",
            [u["username"] for u in list_users_detailed()],
            key="reset_user_select"
        )
        reset_password_new = st.text_input(
            "New Password",
            type="password",
            help="6+ characters with letters and numbers"
        )
        reset_password_confirm = st.text_input(
            "Confirm Password",
            type="password",
            help="Re-enter the password"
        )
        
        if st.form_submit_button("Reset Password", use_container_width=True):
            if reset_password_new != reset_password_confirm:
                st.error("❌ Passwords do not match")
            else:
                success, msg = reset_password(reset_username, reset_password_new)
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

# ============================================================
# Tab 4: My Account
# ============================================================
with admin_tab4:
    st.subheader("👤 My Account")
    st.write("Manage your admin account")
    
    # Show current user info
    current_user_info = get_user_info(st.session_state.username)
    if current_user_info:
        st.markdown("### Your Account Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Username:** {current_user_info['username']}")
            st.write(f"**Email:** {current_user_info['email']}")
            st.write(f"**Role:** {current_user_info['role']}")
        with col2:
            st.write(f"**Status:** {'Active' if current_user_info['is_active'] else 'Inactive'}")
            st.write(f"**Created:** {current_user_info.get('created_at', 'N/A')[:10] if current_user_info.get('created_at') else 'N/A'}")
            st.write(f"**Last Login:** {current_user_info.get('last_login', 'Never') or 'Never'}")
    
    st.divider()
    
    # Change password
    with st.form("change_password_form"):
        st.markdown("### Change Your Password")
        old_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        new_pwd_confirm = st.text_input("Confirm New Password", type="password")
        
        if st.form_submit_button("Change Password", use_container_width=True):
            if new_pwd != new_pwd_confirm:
                st.error("❌ Passwords do not match")
            else:
                success, msg = change_password(st.session_state.username, old_pwd, new_pwd)
                if success:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")

# ============================================================
# Tab 5: Activity Log
# ============================================================
with admin_tab5:
    st.subheader("📋 Activity Log")
    st.write("View system activity and audit trail")
    
    try:
        # Try to import and show activity log if available
        from auth import get_activity_log
        
        activity_log = get_activity_log()
        if activity_log:
            # Display as table
            log_df = []
            for log in activity_log[-50:]:  # Show last 50 entries
                log_df.append({
                    "Timestamp": log.get('timestamp', 'N/A'),
                    "User": log.get('username', 'Unknown'),
                    "Action": log.get('action', 'N/A'),
                    "Details": log.get('details', '')
                })
            
            import pandas as pd
            st.dataframe(pd.DataFrame(log_df), use_container_width=True)
        else:
            st.info("No activity log entries found")
    except:
        st.info("Activity logging not yet configured")

st.divider()
st.caption("🔐 Admin Panel - All changes are logged for security audit purposes")
