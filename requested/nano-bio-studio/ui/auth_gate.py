# ui/auth_gate.py
import streamlit as st
from auth import authenticate

def require_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None

    if st.session_state.logged_in:
        return

    st.title("🧬 NanoBio Studio — Secure Login")
    st.caption("© Experts Group FZE — Ghassan Muammar. Confidential / Proprietary.")

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Login", width='stretch', key="btn_login"):
            ok, role = authenticate(username, password)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username = username.strip()
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with c2:
        if st.button("Clear", width='stretch', key="btn_clear_login"):
            st.session_state.login_username = ""
            st.session_state.login_password = ""
            st.rerun()

    st.stop()
