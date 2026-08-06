"""
Design History & Comparison Module
View, compare, and manage design versions and history
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from design_persistence import (
    get_design_versions, restore_design_version, 
    get_user_designs, load_design_from_db
)
from core.scoring import compute_impact


def get_design_changes(version_old: dict, version_new: dict) -> Dict:
    """
    Compare two design versions and identify changes.
    
    Args:
        version_old: Older design dictionary
        version_new: Newer design dictionary
    
    Returns:
        Dictionary with changes grouped by type
    """
    changes = {
        "added": {},
        "removed": {},
        "modified": {}
    }
    
    all_keys = set(version_old.keys()) | set(version_new.keys())
    
    for key in all_keys:
        old_val = version_old.get(key)
        new_val = version_new.get(key)
        
        if key not in version_old:
            changes["added"][key] = new_val
        elif key not in version_new:
            changes["removed"][key] = old_val
        elif old_val != new_val:
            changes["modified"][key] = {"from": old_val, "to": new_val}
    
    return changes


def render_design_history_timeline(username: str, design_name: str):
    """
    Render a timeline view of design history.
    
    Args:
        username: Username
        design_name: Design name
    """
    versions = get_design_versions(username, design_name)
    
    if not versions:
        st.info("📭 No version history available")
        return
    
    st.markdown(f"### 📜 Design History: {design_name}")
    
    # Create timeline
    for i, version in enumerate(versions):
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 1])
            
            with col1:
                st.metric("Version", f"v{version['version_number']}")
            
            with col2:
                st.write(f"**{version['version_notes']}**")
                st.caption(f"Created: {version['created_at']}")
                
                # Show what changed (if not first version)
                if i < len(versions) - 1:
                    next_version = versions[i + 1]
                    changes = get_design_changes(next_version['design_data'], version['design_data'])
                    
                    if changes['added'] or changes['modified'] or changes['removed']:
                        with st.expander("🔍 View Changes"):
                            if changes['modified']:
                                st.markdown("**Modified Parameters:**")
                                mod_data = []
                                for key, change in changes['modified'].items():
                                    mod_data.append({
                                        "Parameter": key,
                                        "Old Value": str(change['from']),
                                        "New Value": str(change['to'])
                                    })
                                st.dataframe(pd.DataFrame(mod_data), use_container_width=True, hide_index=True)
                            
                            if changes['added']:
                                st.markdown("**Added Parameters:**")
                                add_data = [{"Parameter": k, "Value": str(v)} for k, v in changes['added'].items()]
                                st.dataframe(pd.DataFrame(add_data), use_container_width=True, hide_index=True)
                            
                            if changes['removed']:
                                st.markdown("**Removed Parameters:**")
                                rem_data = [{"Parameter": k, "Value": str(v)} for k, v in changes['removed'].items()]
                                st.dataframe(pd.DataFrame(rem_data), use_container_width=True, hide_index=True)
            
            with col3:
                col_restore, col_load = st.columns(2)
                with col_restore:
                    if st.button("↩️ Restore", key=f"restore_{version['version_number']}", use_container_width=True):
                        success = restore_design_version(username, design_name, version['version_number'])
                        if success:
                            st.success(f"Restored v{version['version_number']}")
                            st.rerun()
                
                with col_load:
                    if st.button("📂 Load", key=f"load_v_{version['version_number']}", use_container_width=True):
                        design_data = version['design_data']
                        st.session_state.design = design_data
                        st.success(f"Loaded v{version['version_number']}")
                        st.rerun()
            
            st.divider()


def render_design_comparison(username: str, design_name: str):
    """
    Render UI for comparing two versions of a design.
    
    Args:
        username: Username
        design_name: Design name
    """
    versions = get_design_versions(username, design_name)
    
    if len(versions) < 2:
        st.info("⚠️ Need at least 2 versions to compare")
        return
    
    st.markdown(f"### 🔄 Compare Versions: {design_name}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        version_1_num = st.selectbox(
            "Version 1",
            [v['version_number'] for v in versions],
            key="comp_v1"
        )
    
    with col2:
        version_2_num = st.selectbox(
            "Version 2",
            [v['version_number'] for v in versions],
            key="comp_v2"
        )
    
    # Get selected versions
    v1 = next((v for v in versions if v['version_number'] == version_1_num), None)
    v2 = next((v for v in versions if v['version_number'] == version_2_num), None)
    
    if v1 and v2 and version_1_num != version_2_num:
        st.markdown(f"**Comparing v{version_1_num} → v{version_2_num}**")
        
        changes = get_design_changes(v1['design_data'], v2['design_data'])
        
        # Show changes summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Modified", len(changes['modified']))
        with col2:
            st.metric("Added", len(changes['added']))
        with col3:
            st.metric("Removed", len(changes['removed']))
        
        st.divider()
        
        # Detailed comparison
        if changes['modified']:
            st.markdown("### 🔄 Modified Parameters")
            mod_data = []
            for key, change in changes['modified'].items():
                old_val = change['from']
                new_val = change['to']
                
                # Format lists nicely
                if isinstance(old_val, list):
                    old_val = ", ".join(str(v) for v in old_val)
                if isinstance(new_val, list):
                    new_val = ", ".join(str(v) for v in new_val)
                
                mod_data.append({
                    "Parameter": key,
                    "v" + str(version_1_num): str(old_val),
                    "v" + str(version_2_num): str(new_val)
                })
            
            st.dataframe(pd.DataFrame(mod_data), use_container_width=True, hide_index=True)
        
        if changes['added']:
            st.markdown("### ➕ Added Parameters")
            add_data = []
            for key, value in changes['added'].items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                add_data.append({"Parameter": key, "Value": str(value)})
            st.dataframe(pd.DataFrame(add_data), use_container_width=True, hide_index=True)
        
        if changes['removed']:
            st.markdown("### ➖ Removed Parameters")
            rem_data = []
            for key, value in changes['removed'].items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                rem_data.append({"Parameter": key, "Value": str(value)})
            st.dataframe(pd.DataFrame(rem_data), use_container_width=True, hide_index=True)
        
        # Impact comparison
        try:
            st.divider()
            st.markdown("### 📊 Impact Metrics Comparison")
            
            impact_1 = compute_impact(v1['design_data'])
            impact_2 = compute_impact(v2['design_data'])
            
            impact_data = []
            for metric in ['Delivery', 'Toxicity', 'Cost']:
                val_1 = impact_1.get(metric, 0)
                val_2 = impact_2.get(metric, 0)
                change = val_2 - val_1
                
                impact_data.append({
                    "Metric": metric,
                    f"v{version_1_num}": f"{val_1:.2f}",
                    f"v{version_2_num}": f"{val_2:.2f}",
                    "Change": f"{change:+.2f}"
                })
            
            st.dataframe(pd.DataFrame(impact_data), use_container_width=True, hide_index=True)
        except:
            pass


def render_all_designs_history(username: str):
    """
    Render browsable history of all user's designs.
    
    Args:
        username: Username
    """
    designs = get_user_designs(username)
    
    if not designs:
        st.info("📭 No designs to show")
        return
    
    st.markdown("### 📚 All Designs History")
    
    # Display designs in tabs
    tabs = st.tabs([d['design_name'] for d in designs])
    
    for tab, design in zip(tabs, designs):
        with tab:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Created**: {design['created_at']}")
                st.write(f"**Updated**: {design['updated_at']}")
                if design['description']:
                    st.caption(design['description'])
                if design['tags']:
                    st.caption(f"**Tags**: {design['tags']}")
            
            with col2:
                if st.button("📜 View History", key=f"hist_{design['id']}", use_container_width=True):
                    st.session_state[f"show_history_{design['id']}"] = True
                
                if st.button("🔄 Compare Versions", key=f"comp_{design['id']}", use_container_width=True):
                    st.session_state[f"show_comparison_{design['id']}"] = True
            
            # Show history if requested
            if st.session_state.get(f"show_history_{design['id']}", False):
                render_design_history_timeline(username, design['design_name'])
            
            # Show comparison if requested
            if st.session_state.get(f"show_comparison_{design['id']}", False):
                render_design_comparison(username, design['design_name'])


def render_project_dashboard(username: str):
    """
    Render a comprehensive project/design history dashboard.
    
    Args:
        username: Username
    """
    st.header("📊 Design History Dashboard")
    
    designs = get_user_designs(username)
    
    if not designs:
        st.info("📭 No designs yet. Create your first design!")
        return
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Designs", len(designs))
    
    with col2:
        favorites = sum(1 for d in designs if d['is_favorite'])
        st.metric("Favorites", favorites)
    
    with col3:
        total_versions = sum(len(get_design_versions(username, d['design_name'])) for d in designs)
        st.metric("Total Versions", total_versions)
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📅 Timeline", "📚 All Designs", "🔄 Compare"])
    
    with tab1:
        st.markdown("### Recent Activity")
        
        # Get all recent versions across designs
        recent_items = []
        for design in designs:
            versions = get_design_versions(username, design['design_name'])
            for version in versions[:3]:  # Last 3 versions per design
                recent_items.append({
                    "design_name": design['design_name'],
                    "version": version['version_number'],
                    "timestamp": version['created_at'],
                    "notes": version['version_notes']
                })
        
        # Sort by timestamp (newest first)
        recent_items.sort(key=lambda x: x['timestamp'], reverse=True)
        
        if recent_items:
            for item in recent_items[:10]:  # Show last 10 items
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{item['design_name']}** (v{item['version']})")
                    st.caption(f"{item['notes']}")
                    st.caption(f"📅 {item['timestamp']}")
                with col2:
                    if st.button("Load", key=f"load_recent_{item['design_name']}_{item['version']}", use_container_width=True):
                        design_data = load_design_from_db(username, item['design_name'])
                        if design_data:
                            st.session_state.design = design_data
                            st.success("Design loaded!")
                            st.rerun()
                st.divider()
    
    with tab2:
        # Design list with actions
        st.markdown("### All Designs")
        
        for design in designs:
            with st.expander(f"{'⭐ ' if design['is_favorite'] else '☆ '}{design['design_name']}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    if design['description']:
                        st.write(design['description'])
                    st.caption(f"Created: {design['created_at']}")
                    st.caption(f"Updated: {design['updated_at']}")
                    if design['tags']:
                        st.caption(f"Tags: {design['tags']}")
                
                with col2:
                    if st.button("📂 Load", key=f"load_dash_{design['id']}", use_container_width=True):
                        design_data = load_design_from_db(username, design['design_name'])
                        if design_data:
                            st.session_state.design = design_data
                            st.success("Design loaded!")
                            st.rerun()
                
                versions = get_design_versions(username, design['design_name'])
                st.caption(f"📜 {len(versions)} versions")
                
                if st.button("View History", key=f"hist_dash_{design['id']}", use_container_width=True):
                    render_design_history_timeline(username, design['design_name'])
    
    with tab3:
        # Compare designs
        st.markdown("### Compare Designs")
        
        selected_designs = st.multiselect(
            "Select designs to compare",
            [d['design_name'] for d in designs],
            max_selections=2
        )
        
        if len(selected_designs) == 2:
            design1_data = load_design_from_db(username, selected_designs[0])
            design2_data = load_design_from_db(username, selected_designs[1])
            
            if design1_data and design2_data:
                st.markdown(f"### {selected_designs[0]} vs {selected_designs[1]}")
                
                changes = get_design_changes(design1_data, design2_data)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Differences", len(changes['modified']))
                with col2:
                    st.metric("Unique to First", len(changes['removed']))
                with col3:
                    st.metric("Unique to Second", len(changes['added']))
                
                st.divider()
                
                if changes['modified']:
                    st.markdown("**Different Parameters**")
                    mod_data = []
                    for key, change in changes['modified'].items():
                        mod_data.append({
                            "Parameter": key,
                            selected_designs[0]: str(change['from']),
                            selected_designs[1]: str(change['to'])
                        })
                    st.dataframe(pd.DataFrame(mod_data), use_container_width=True, hide_index=True)
        
        elif len(selected_designs) == 1:
            st.info("Select a second design to compare")
