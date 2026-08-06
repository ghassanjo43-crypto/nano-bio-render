"""
Materials and Targets Library Page
"""

import streamlit as st
import json
from pathlib import Path

def load_data():
    """Load nanoparticle and target data from JSON files"""
    data_dir = Path(__file__).parent.parent / "data"
    
    with open(data_dir / "nanoparticles.json", "r") as f:
        nanoparticles = json.load(f)["nanoparticles"]
    
    with open(data_dir / "targets.json", "r") as f:
        targets = json.load(f)["targets"]
    
    return nanoparticles, targets

def show():
    """Display materials and targets library"""
    st.title("📚 Materials & Targets Library")
    st.markdown("Browse available nanoparticle types and biological targets")
    
    st.markdown("---")
    
    # Tabs for nanoparticles and targets
    tab1, tab2 = st.tabs(["🔬 Nanoparticle Materials", "🎯 Biological Targets"])
    
    nanoparticles, targets = load_data()
    
    with tab1:
        st.subheader("Nanoparticle Library")
        st.markdown("Select a nanoparticle type to view detailed specifications:")
        
        # Create a searchable/filterable view
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_np = st.text_input("🔍 Search nanoparticles", "", key="search_np")
        
        with col2:
            np_types = list(set([np["type"] for np in nanoparticles]))
            filter_type = st.selectbox("Filter by type", ["All"] + np_types, key="filter_np")
        
        # Filter nanoparticles
        filtered_nps = nanoparticles
        if search_np:
            filtered_nps = [np for np in filtered_nps if search_np.lower() in np["name"].lower() or search_np.lower() in np["description"].lower()]
        if filter_type != "All":
            filtered_nps = [np for np in filtered_nps if np["type"] == filter_type]
        
        # Display nanoparticles
        for np in filtered_nps:
            with st.expander(f"**{np['name']}** ({np['type']})"):
                st.markdown(f"**Description:** {np['description']}")
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.markdown(f"**Size Range:** {np['typical_size_range'][0]}-{np['typical_size_range'][1]} nm")
                    st.markdown(f"**Charge Range:** {np['typical_charge_range'][0]} to {np['typical_charge_range'][1]} mV")
                
                with col_b:
                    st.markdown(f"**Common Ligands:** {', '.join(np['common_ligands'])}")
                    st.markdown(f"**Common Payloads:** {', '.join(np['common_payloads'])}")
                
                st.success(f"✅ **Advantages:** {np['advantages']}")
                st.warning(f"⚠️ **Limitations:** {np['limitations']}")
                
                if st.button(f"Use {np['name']} in Design", key=f"use_{np['id']}"):
                    st.session_state.design['Material'] = np['name']
                    st.session_state.design['Size'] = sum(np['typical_size_range']) / 2
                    st.session_state.design['Charge'] = sum(np['typical_charge_range']) / 2
                    st.success(f"✅ {np['name']} loaded into design!")
                    st.info("Go to **Design Nanoparticle** page to customize parameters")
    
    with tab2:
        st.subheader("Biological Target Library")
        st.markdown("Select a biological target to view characteristics:")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_tgt = st.text_input("🔍 Search targets", "", key="search_tgt")
        
        with col2:
            tgt_types = list(set([tgt["type"] for tgt in targets]))
            filter_tgt_type = st.selectbox("Filter by type", ["All"] + tgt_types, key="filter_tgt")
        
        # Filter targets
        filtered_tgts = targets
        if search_tgt:
            filtered_tgts = [tgt for tgt in filtered_tgts if search_tgt.lower() in tgt["name"].lower() or search_tgt.lower() in tgt["description"].lower()]
        if filter_tgt_type != "All":
            filtered_tgts = [tgt for tgt in filtered_tgts if tgt["type"] == filter_tgt_type]
        
        # Display targets
        for tgt in filtered_tgts:
            with st.expander(f"**{tgt['name']}** ({tgt['type']})"):
                st.markdown(f"**Description:** {tgt['description']}")
                
                st.markdown(f"**Key Receptors:** {', '.join(tgt['receptors'])}")
                
                st.markdown("**Key Features:**")
                for feature in tgt['key_features']:
                    st.markdown(f"- {feature}")
                
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.info(f"**Typical Accumulation:** {tgt['typical_accumulation']}")
                
                with col_b:
                    st.warning(f"**Challenges:** {tgt['challenges']}")
                
                if st.button(f"Target {tgt['name']}", key=f"target_{tgt['id']}"):
                    st.session_state.design['target'] = tgt['name']
                    st.success(f"✅ {tgt['name']} selected as target!")
                    st.info("Go to **Design Nanoparticle** page to optimize for this target")
    
    st.markdown("---")
    st.info("💡 **Tip:** You can upload custom materials and targets in the Import/Export section")
