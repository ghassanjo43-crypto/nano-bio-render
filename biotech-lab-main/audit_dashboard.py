"""
Audit Dashboard - Comprehensive audit logging and reporting interface
Displays user actions, security metrics, and compliance information
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from auth import (
    get_activity_log, get_activity_stats, audit_log_search, 
    get_user_audit_trail, export_audit_log, generate_audit_report
)


def render_audit_overview():
    """Display audit overview and key metrics"""
    st.subheader("📊 Audit Overview")
    
    # Get statistics
    stats = get_activity_stats(days=7)
    
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📝 Total Activities",
                stats.get("total_activities", 0),
                "Last 7 days"
            )
        
        with col2:
            st.metric(
                "👥 Active Users",
                stats.get("unique_users", 0),
                "Last 7 days"
            )
        
        with col3:
            st.metric(
                "⚠️ Failed Logins",
                stats.get("failed_logins", 0),
                "Last 7 days"
            )
        
        with col4:
            st.metric(
                "🔑 Password Changes",
                stats.get("password_changes", 0),
                "Last 7 days"
            )
        
        st.divider()
        
        # Activities by action
        if stats.get("activities_by_action"):
            st.markdown("**Activity Breakdown**")
            actions_df = pd.DataFrame(
                list(stats["activities_by_action"].items()),
                columns=["Action", "Count"]
            ).sort_values("Count", ascending=False)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.dataframe(actions_df, width='stretch', hide_index=True)
            
            with col2:
                st.bar_chart(actions_df.set_index("Action")["Count"])


def render_activity_log_viewer():
    """Display activity log with filtering options"""
    st.subheader("📋 Activity Log Viewer")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_type = st.selectbox(
            "Filter Type",
            ["All", "By Date Range", "By User", "By Action", "Search"]
        )
    
    # Fetch activity log based on filter
    activity_log = []
    
    if filter_type == "All":
        with col2:
            limit = st.slider("Show entries", 10, 500, 100)
        activity_log = get_activity_log(limit=limit)
    
    elif filter_type == "By Date Range":
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Start Date")
        with col_end:
            end_date = st.date_input("End Date")
        
        activity_log = export_audit_log(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
    
    elif filter_type == "By User":
        with col2:
            username = st.text_input("Username")
        if username:
            activity_log = get_activity_log(username=username, limit=500)
    
    elif filter_type == "By Action":
        actions = ["LOGIN", "LOGOUT", "PASSWORD_CHANGED", "DESIGN_SAVE", "OPTIMIZATION_RUN", "ADMIN_"]
        with col2:
            selected_action = st.selectbox("Select Action", actions)
        if selected_action:
            activity_log = export_audit_log(action_filter=selected_action)
    
    elif filter_type == "Search":
        with col2:
            search_query = st.text_input("Search query")
        if search_query:
            activity_log = audit_log_search(search_query)
    
    # Display activity log
    if activity_log:
        df = pd.DataFrame(activity_log)
        st.dataframe(df, width='stretch', hide_index=True)
        
        # Download option
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No activity records found.")


def render_user_audit_trail():
    """Display detailed audit trail for a specific user"""
    st.subheader("👤 User Audit Trail")
    
    username = st.text_input("Enter username", placeholder="e.g., john_doe")
    
    if username:
        trail = get_user_audit_trail(username)
        
        if trail:
            st.write(f"**Audit Trail for {username}** ({len(trail)} actions)")
            
            # Create timeline view
            for i, action in enumerate(trail):
                with st.expander(f"{action['timestamp']} - {action['action']}"):
                    st.write(f"**Details:** {action.get('details', 'N/A')}")
            
            # Summary statistics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Actions", len(trail))
            with col2:
                if trail:
                    first_action = trail[-1]['timestamp']
                    last_action = trail[0]['timestamp']
                    st.metric("Active Period", f"From {first_action} to {last_action}")
        else:
            st.warning(f"No audit trail found for user '{username}'")


def render_security_report():
    """Display security-focused audit report"""
    st.subheader("🔒 Security Audit Report")
    
    col1, col2 = st.columns(2)
    
    with col1:
        report_days = st.slider("Days to analyze", 1, 90, 7)
    
    with col2:
        if st.button("Generate Report", use_container_width=True):
            report = generate_audit_report("security", days=report_days)
            
            if report:
                st.write(f"**Report Period:** Last {report_days} days")
                
                # Failed login attempts
                if report.get("failed_login_attempts"):
                    st.markdown("#### Failed Login Attempts")
                    failed_df = pd.DataFrame(report["failed_login_attempts"])
                    st.dataframe(failed_df, width='stretch', hide_index=True)
                    
                    # Alert for high failed attempts
                    for attempt in report["failed_login_attempts"]:
                        if attempt["attempts"] >= 5:
                            st.warning(
                                f"⚠️ User '{attempt['username']}' has {attempt['attempts']} failed login attempts"
                            )
                else:
                    st.info("✅ No failed login attempts detected")
                
                st.divider()
                
                # Password changes
                if report.get("password_changes"):
                    st.markdown("#### Password Changes")
                    pw_df = pd.DataFrame(report["password_changes"])
                    st.dataframe(pw_df, width='stretch', hide_index=True)
                else:
                    st.info("No password changes in this period")


def render_compliance_report():
    """Display compliance-focused report"""
    st.subheader("📜 Compliance Report")
    
    col1, col2 = st.columns(2)
    
    with col1:
        report_days = st.slider("Report period (days)", 1, 365, 30, key="compliance_days")
    
    with col2:
        report_format = st.selectbox("Report format", ["Summary", "Detailed"])
    
    if st.button("Generate Compliance Report", use_container_width=True):
        report = generate_audit_report("user_access", days=report_days)
        
        if report and report.get("user_activity"):
            st.write(f"**Reporting Period:** Last {report_days} days")
            st.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            activity_df = pd.DataFrame(report["user_activity"])
            
            if report_format == "Summary":
                st.dataframe(activity_df, width='stretch', hide_index=True)
            else:
                # Detailed view
                for _, user in activity_df.iterrows():
                    with st.expander(f"👤 {user['username']} - {user['total_actions']} actions"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Actions", user['total_actions'])
                        with col2:
                            st.metric("Last Activity", user['last_activity'])
            
            # Export button
            csv = activity_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Report (CSV)",
                data=csv,
                file_name=f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )


def render_audit_dashboard():
    """Main audit dashboard renderer"""
    st.title("🔐 Audit & Compliance Dashboard")
    st.caption("Comprehensive audit logging and security monitoring")
    
    # Tab selection
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview",
        "📋 Activity Log",
        "👤 User Trail",
        "🔒 Security",
        "📜 Compliance"
    ])
    
    with tab1:
        render_audit_overview()
    
    with tab2:
        render_activity_log_viewer()
    
    with tab3:
        render_user_audit_trail()
    
    with tab4:
        render_security_report()
    
    with tab5:
        render_compliance_report()


if __name__ == "__main__":
    # For standalone testing
    render_audit_dashboard()
