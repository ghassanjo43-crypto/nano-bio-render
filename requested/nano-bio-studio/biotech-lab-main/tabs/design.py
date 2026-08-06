import streamlit as st
from core.scoring import compute_impact, get_recommendations
from persistence import save_design, render_design_selector, render_save_design_form
from design_persistence import (
    render_design_selector_db, render_save_design_form_db, 
    get_design_versions, restore_design_version, get_design_stats
)
from export import render_export_controls, render_quick_export
import pandas as pd
import plotly.graph_objects as go


def render_design_parameters():
    """Render comprehensive design parameter controls"""
    
    d = st.session_state.design
    
    # Material selection with properties
    st.subheader("🧬 Core Properties")
    
    material_properties = {
        "Lipid NP": {
            "biodegradation": 7,
            "surface_area_range": (200, 400),
            "cost_base": 50,
            "density": 0.95,
            "melting_point": 41,
            "ionization": -5,
            "permeability": 0.85
        },
        "PLGA": {
            "biodegradation": 30,
            "surface_area_range": (150, 300),
            "cost_base": 40,
            "density": 1.22,
            "melting_point": 180,
            "ionization": -15,
            "permeability": 0.65
        },
        "Gold NP": {
            "biodegradation": 180,
            "surface_area_range": (100, 250),
            "cost_base": 80,
            "density": 19.3,
            "melting_point": 1064,
            "ionization": -10,
            "permeability": 0.95
        },
        "Silica NP": {
            "biodegradation": 365,
            "surface_area_range": (300, 600),
            "cost_base": 30,
            "density": 2.2,
            "melting_point": 1710,
            "ionization": -25,
            "permeability": 0.75
        },
        "DNA Origami": {
            "biodegradation": 1,
            "surface_area_range": (50, 200),
            "cost_base": 120,
            "density": 1.65,
            "melting_point": 95,
            "ionization": -35,
            "permeability": 0.55
        },
        "MOF-303": {
            "biodegradation": 14,
            "surface_area_range": (1000, 2000),
            "cost_base": 100,
            "density": 1.1,
            "melting_point": 300,
            "ionization": 0,
            "permeability": 0.88
        }
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        d["Material"] = st.selectbox(
            "Select Material",
            list(material_properties.keys()),
            index=list(material_properties.keys()).index(d.get("Material", "Lipid NP"))
        )
        
        # Show material properties
        material_info = material_properties.get(d["Material"], {})
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.caption(f"🔄 **Biodegradation**: {material_info.get('biodegradation', 'N/A')} days")
            st.caption(f"🌡️ **Melting Point**: {material_info.get('melting_point', 'N/A')}°C")
        with col_m2:
            st.caption(f"⚡ **Density**: {material_info.get('density', 'N/A')} g/cm³")
            st.caption(f"🫧 **Permeability**: {material_info.get('permeability', 'N/A')}")
    
    with col2:
        d["Target"] = st.selectbox(
            "Target Organ/Tissue",
            ["Liver Cells", "Tumor", "Brain", "Lung", "Kidney", "Spleen", "Bone", "Custom"],
            index=["Liver Cells", "Tumor", "Brain", "Lung", "Kidney", "Spleen", "Bone", "Custom"].index(d.get("Target", "Liver Cells"))
        )
        
        # Material phase info
        phases = {
            "Lipid NP": "Liquid Crystalline",
            "PLGA": "Solid Polymer",
            "Gold NP": "Metal",
            "Silica NP": "Inorganic",
            "DNA Origami": "Biopolymer",
            "MOF-303": "Metal-Organic"
        }
        st.caption(f"🏗️ **Material Phase**: {phases.get(d['Material'], 'Unknown')}")
    
    # Core physical parameters
    st.markdown("### 📏 Physical Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["Size"] = st.slider(
            "Core Particle Size (nm)",
            min_value=10,
            max_value=500,
            value=int(d.get("Size", 100)),
            step=5,
            help="Optimal range: 80-120 nm for most applications"
        )
    
    with col2:
        d["PDI"] = st.slider(
            "Polydispersity Index (PDI)",
            min_value=0.05,
            max_value=0.5,
            value=float(d.get("PDI", 0.15)),
            step=0.02,
            help="Lower is better. <0.1 = very uniform, >0.3 = heterogeneous"
        )
    
    with col3:
        d["HydrodynamicSize"] = st.slider(
            "Hydrodynamic Size (nm)",
            min_value=20,
            max_value=600,
            value=int(d.get("HydrodynamicSize", 120)),
            step=5,
            help="Size in biological medium (usually ~1.1-1.2x core size)"
        )
    
    # Enhanced material properties
    st.markdown("### ⚛️ Material Properties")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["CrystallinityIndex"] = st.slider(
            "Crystallinity Index (%)",
            min_value=0,
            max_value=100,
            value=int(d.get("CrystallinityIndex", 65)),
            step=5,
            help="Higher = more ordered. Affects stability and release profile"
        )
    
    with col2:
        d["PorosityLevel"] = st.selectbox(
            "Porosity Level",
            ["Non-porous", "Microporous (<2nm)", "Mesoporous (2-50nm)", "Macroporous (>50nm)"],
            index=["Non-porous", "Microporous (<2nm)", "Mesoporous (2-50nm)", "Macroporous (>50nm)"].index(d.get("PorosityLevel", "Mesoporous (2-50nm)"))
        )
    
    with col3:
        if d.get("PorosityLevel") != "Non-porous":
            d["PoreSize"] = st.slider(
                "Average Pore Size (nm)",
                min_value=0.5,
                max_value=100.0,
                value=float(d.get("PoreSize", 5.0)),
                step=0.5,
                help="Affects drug loading and release kinetics"
            )
        else:
            d["PoreSize"] = 0.0
    
    # Surface modification and chemistry
    st.markdown("### 🎨 Surface Modification & Chemistry")
    
    col1, col2 = st.columns(2)
    
    with col1:
        d["SurfaceCoating"] = st.multiselect(
            "Surface Coating Layers",
            ["None", "PEG (Stealth)", "Chitosan", "Hyaluronic Acid", "Albumin", "Antibody"],
            default=d.get("SurfaceCoating", ["PEG (Stealth)"]),
            help="Multiple coatings can be applied sequentially"
        )
        
        if not d["SurfaceCoating"] or (len(d["SurfaceCoating"]) == 1 and d["SurfaceCoating"][0] == "None"):
            d["CoatingThickness"] = 0.0
        else:
            d["CoatingThickness"] = st.slider(
                "Coating Thickness (nm)",
                min_value=0.5,
                max_value=20.0,
                value=float(d.get("CoatingThickness", 2.5)),
                step=0.5,
                help="Thickness of protective coating layer"
            )
    
    with col2:
        d["FunctionalGroups"] = st.multiselect(
            "Functional Groups",
            ["-OH (Hydroxyl)", "-COOH (Carboxyl)", "-NH2 (Amino)", "-SH (Thiol)", "-C≡N (Cyano)", "Phosphate"],
            default=d.get("FunctionalGroups", ["-COOH (Carboxyl)"]),
            help="For binding ligands and targeting molecules"
        )
    
    # Surface properties
    st.markdown("### 🔬 Surface Properties")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["Charge"] = st.slider(
            "Surface Charge (mV)",
            min_value=-50,
            max_value=50,
            value=int(d.get("Charge", -5)),
            step=2,
            help="Optimal: ±10 mV for safety. Neutral (0 mV) for stealth"
        )
    
    with col2:
        d["SurfaceArea"] = st.slider(
            "Surface Area (nm²)",
            min_value=50,
            max_value=2000,
            value=int(d.get("SurfaceArea", 250)),
            step=50,
            help="Larger surface area = more ligand attachment sites"
        )
    
    with col3:
        d["Hydrophobicity"] = st.slider(
            "Surface Hydrophobicity (LogP)",
            min_value=-5.0,
            max_value=5.0,
            value=float(d.get("Hydrophobicity", 1.5)),
            step=0.2,
            help="<0 = hydrophilic (water-loving), >0 = hydrophobic (lipid-loving)"
        )
    
    # Advanced surface chemistry
    col1, col2 = st.columns(2)
    
    with col1:
        d["SurfaceRoughness"] = st.slider(
            "Surface Roughness (Ra, nm)",
            min_value=0.1,
            max_value=10.0,
            value=float(d.get("SurfaceRoughness", 0.5)),
            step=0.1,
            help="Affects protein adsorption and cellular interaction"
        )
    
    with col2:
        d["ZetaPotentialStability"] = st.slider(
            "Zeta Potential Stability (%)",
            min_value=0,
            max_value=100,
            value=int(d.get("ZetaPotentialStability", 85)),
            step=5,
            help="Maintenance of charge over time in storage"
        )
    
    # Functional properties
    st.markdown("### 🔧 Functional Properties")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        d["Encapsulation"] = st.slider(
            "Drug Encapsulation (%)",
            min_value=10,
            max_value=100,
            value=int(d.get("Encapsulation", 70)),
            step=5,
            help="Percentage of drug successfully loaded. Target: >80%"
        )
    
    with col2:
        d["Stability"] = st.slider(
            "Colloidal Stability (%)",
            min_value=30,
            max_value=100,
            value=int(d.get("Stability", 85)),
            step=5,
            help="Stability over time. 100% = perfect stability at room temp"
        )
    
    with col3:
        d["DegradationTime"] = st.slider(
            "Degradation Time (days)",
            min_value=1,
            max_value=365,
            value=int(d.get("DegradationTime", 30)),
            step=5,
            help="Time to complete biodegradation. Balance: fast enough for clearance, slow for circulation"
        )
    
    # Targeting ligands and receptors
    st.markdown("### 🎯 Targeting & Ligands")
    
    col1, col2 = st.columns(2)
    
    with col1:
        d["Ligand"] = st.selectbox(
            "Primary Targeting Ligand",
            ["None", "PEG (Stealth)", "Folate", "GalNAc", "Transferrin", "Aptamer", "RGD Peptide", "Anti-HER2", "Hyaluronic Acid"],
            index=["None", "PEG (Stealth)", "Folate", "GalNAc", "Transferrin", "Aptamer", "RGD Peptide", "Anti-HER2", "Hyaluronic Acid"].index(d.get("Ligand", "GalNAc"))
        )
        
        if d["Ligand"] != "None":
            d["LigandDensity"] = st.slider(
                "Ligand Surface Density (%)",
                min_value=5,
                max_value=100,
                value=int(d.get("LigandDensity", 60)),
                step=5,
                help="Percentage of surface sites occupied by ligands. Higher = more targeting"
            )
    
    with col2:
        d["Receptor"] = st.selectbox(
            "Target Receptor",
            ["ASGPR", "Folate Receptor (FR)", "Transferrin Receptor (TfR)", "Integrin", "EGFR", "HER2", "CD44", "None"],
            index=["ASGPR", "Folate Receptor (FR)", "Transferrin Receptor (TfR)", "Integrin", "EGFR", "HER2", "CD44", "None"].index(d.get("Receptor", "ASGPR"))
        )
        
        if d["Receptor"] != "None":
            d["ReceptorBinding"] = st.slider(
                "Receptor Binding Affinity (Kd, nM)",
                min_value=0.1,
                max_value=1000.0,
                value=float(d.get("ReceptorBinding", 10.0)),
                step=1.0,
                help="Lower Kd = stronger binding. Typical: 1-100 nM"
            )
    
    # Advanced payload properties
    if (d.get("Ligand") and d["Ligand"] != "None") or d.get("Encapsulation", 0) > 0:
        st.markdown("### 💊 Payload Properties")
        
        col1, col2 = st.columns(2)
        
        with col1:
            d["ReleaseProfile"] = st.selectbox(
                "Release Profile",
                ["Immediate", "Sustained (1 week)", "Sustained (2 weeks)", "Sustained (1 month)", "pH-Triggered", "Enzyme-Triggered", "Temperature-Triggered"],
                index=["Immediate", "Sustained (1 week)", "Sustained (2 weeks)", "Sustained (1 month)", "pH-Triggered", "Enzyme-Triggered", "Temperature-Triggered"].index(
                    d.get("ReleaseProfile", "Sustained (1 week)")
                )
            )
        
        with col2:
            d["ReleasePredictability"] = st.slider(
                "Release Predictability (%)",
                min_value=50,
                max_value=100,
                value=int(d.get("ReleasePredictability", 85)),
                step=5,
                help="Consistency of release profile. Higher = more controlled"
            )
        
        # Trigger conditions (if triggered release)
        if "Triggered" in d.get("ReleaseProfile", ""):
            col1, col2 = st.columns(2)
            with col1:
                d["TriggerValue"] = st.number_input(
                    "Trigger Condition Value",
                    min_value=1.0,
                    max_value=100.0,
                    value=float(d.get("TriggerValue", 7.0)),
                    step=0.1,
                    help="pH: 1-14 | Enzyme: concentration | Temp: °C"
                )
            with col2:
                d["TriggerThreshold"] = st.slider(
                    "Trigger Sensitivity (±range)",
                    min_value=0.1,
                    max_value=5.0,
                    value=float(d.get("TriggerThreshold", 0.5)),
                    step=0.1,
                    help="Range for trigger activation"
                )


def render_design_comparison():
    """Render design comparison section"""
    
    st.subheader("📊 Design Impact Metrics")
    
    d = st.session_state.design
    impact = compute_impact(d)
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📤 Delivery Efficiency",
            f"{impact['Delivery']:.1f}%",
            delta="Target: >80%",
            delta_color="off"
        )
    
    with col2:
        toxicity_color = "off"
        if impact['Toxicity'] < 3:
            toxicity_color = "normal"  # Green
        elif impact['Toxicity'] > 6:
            toxicity_color = "inverse"  # Red
        
        st.metric(
            "☣️ Toxicity Score",
            f"{impact['Toxicity']:.2f}/10",
            delta="Lower is better",
            delta_color=toxicity_color
        )
    
    with col3:
        st.metric(
            "💰 Manufacturing Cost",
            f"${impact['Cost']:.1f}",
            delta="Estimate per batch",
            delta_color="off"
        )
    
    with col4:
        # Overall score
        overall = (impact['Delivery'] / 100 * 0.4) + ((10 - impact['Toxicity']) / 10 * 0.3) + ((100 - impact['Cost']) / 100 * 0.3)
        st.metric(
            "🎯 Overall Score",
            f"{overall:.2f}/1.0",
            delta="Weighted composite",
            delta_color="off"
        )
    
    # Detailed metrics table
    metrics_data = {
        "Metric": [
            "Size Optimality",
            "Charge Safety",
            "Encapsulation Efficiency",
            "Stability Quality",
            "Degradation Profile"
        ],
        "Value": [
            f"{int(d['Size'])} nm",
            f"{int(d['Charge'])} mV",
            f"{int(d['Encapsulation'])}%",
            f"{int(d['Stability'])}%",
            f"{int(d['DegradationTime'])} days"
        ],
        "Status": [
            "✅" if 80 <= d['Size'] <= 120 else "⚠️",
            "✅" if abs(d['Charge']) <= 10 else "⚠️",
            "✅" if d['Encapsulation'] >= 80 else "⚠️",
            "✅" if d['Stability'] >= 85 else "⚠️",
            "✅" if 7 <= d['DegradationTime'] <= 90 else "⚠️"
        ]
    }
    
    df_metrics = pd.DataFrame(metrics_data)
    st.dataframe(df_metrics, width='stretch', hide_index=True)


def render_recommendations():
    """Render design recommendations"""
    
    st.subheader("💡 Design Recommendations")
    
    d = st.session_state.design
    recommendations = get_recommendations(d)
    
    if recommendations:
        for rec in recommendations:
            st.write(rec)
    else:
        st.success("✅ Your design meets all optimization criteria!")


def render_design_history():
    """Render design comparison with history"""
    
    st.subheader("📈 Design Evolution")
    
    # This would compare with saved designs from the database
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📂 Load Previous Design", width='stretch'):
            render_design_selector()
    
    with col2:
        if st.button("📊 Compare Designs", width='stretch'):
            st.info("Design comparison feature coming soon. Compare multiple saved designs side-by-side.")


def render(plotly_ok: bool = False):
    """Main render function for design tab"""
    
    st.header("🎨 Design Your Nanoparticle")
    
    # Create two-column layout
    col1, col2 = st.columns([2, 1])
    
    # Left column: Parameter controls
    with col1:
        render_design_parameters()
        render_design_comparison()
    
    # Right column: Recommendations and actions
    with col2:
        render_recommendations()
        
        st.divider()
        
        st.markdown("### 💾 Save & Load (Database)")
        
        # Get current username
        username = st.session_state.get("username", "guest")
        
        col_save, col_load = st.columns(2)
        
        with col_save:
            if st.button("💾 Save", width='stretch', type="primary"):
                with st.expander("Save Design to Database", expanded=True):
                    render_save_design_form_db(username)
        
        with col_load:
            if st.button("📂 Load", width='stretch'):
                with st.expander("Load Design from Database", expanded=True):
                    render_design_selector_db(username)
        
        # Design statistics
        if username != "guest":
            stats = get_design_stats(username)
            st.caption(f"📊 Designs: {stats['total_designs']} | ⭐ Favorites: {stats['favorite_designs']}")
        
        st.divider()
        
        # Export functionality
        st.markdown("### 📥 Export Design")
        render_quick_export(st.session_state.design, "My_NP_Design")
        
        st.divider()
        
        # Quick actions
        st.markdown("### ⚡ Quick Actions")
        
        if st.button("▶️ Run Simulation", width='stretch', type="primary", key="run_sim_button"):
            st.info("🚀 Starting nanoparticle simulation...")
            
            # Simulate the design
            d = st.session_state.design
            
            with st.spinner("Computing particle behavior..."):
                import time
                time.sleep(1)  # Simulate computation
                
                # Display simulation results
                st.subheader("📊 Simulation Results")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Predicted Biodistribution", f"{int(d['Stability'] * 0.8)}%", "Primary target")
                    st.metric("Cellular Uptake Rate", f"{int(d['Encapsulation'] * 0.9)}%", "Expected efficiency")
                
                with col2:
                    st.metric("Circulation Time", f"{int(d['DegradationTime'] * 0.7 / 24)} hours", "Estimated half-life")
                    st.metric("Immunogenicity Score", f"{max(0, 10 - int(d['Stability'] / 10))}/10", "Lower is better")
                
                # Simulation parameters used
                with st.expander("📋 Simulation Parameters", expanded=False):
                    sim_params = {
                        "Material": d.get("Material", "N/A"),
                        "Size": f"{d.get('Size', 0)} nm",
                        "Target": d.get("Target", "N/A"),
                        "Ligand": d.get("Ligand", "None"),
                        "Charge": f"{d.get('Charge', 0)} mV",
                        "Stability": f"{d.get('Stability', 0)}%",
                        "Encapsulation": f"{d.get('Encapsulation', 0)}%",
                    }
                    for key, value in sim_params.items():
                        st.write(f"**{key}**: {value}")
                
                st.success("✅ Simulation completed!")
        
        st.divider()
        
        if st.button("🎯 Optimize This Design", width='stretch'):
            st.session_state.current_tab = "🤖 AI Optimize"
            st.rerun()
        
        if st.button("🔄 Reset to Defaults", width='stretch'):
            st.session_state.design = {
                "Material": "Lipid NP",
                "Size": 100,
                "Charge": -5,
                "Encapsulation": 70,
                "Target": "Liver Cells",
                "Ligand": "GalNAc",
                "Receptor": "ASGPR",
                "HydrodynamicSize": 120,
                "PDI": 0.15,
                "SurfaceArea": 250,
                "DegradationTime": 30,
                "Stability": 85,
                "ReleaseProfile": "Sustained (1 week)",
                "CrystallinityIndex": 65,
                "PorosityLevel": "Mesoporous (2-50nm)",
                "PoreSize": 5.0,
                "SurfaceCoating": ["PEG (Stealth)"],
                "CoatingThickness": 2.5,
                "FunctionalGroups": ["-COOH (Carboxyl)"],
                "Hydrophobicity": 1.5,
                "SurfaceRoughness": 0.5,
                "ZetaPotentialStability": 85,
                "LigandDensity": 60,
                "ReceptorBinding": 10.0,
                "ReleasePredictability": 85,
                "TriggerValue": 7.0,
                "TriggerThreshold": 0.5
            }
            st.success("Design reset to defaults")
            st.rerun()

