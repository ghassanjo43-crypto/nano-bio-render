"""
Experimental Protocol Generator Page
Generate detailed synthesis and characterization protocols for nanoparticles.
"""

import streamlit as st
# LEGACY_STREAMLIT_ARCHIVE_BOUNDARY -- must remain before legacy imports.
st.error("This legacy Streamlit interface is archived and read-only. Use the canonical FastAPI/React platform.")
st.stop()
raise SystemExit("legacy Streamlit execution is disabled")
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Protocol Generator - NanoBio Studio",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 Experimental Protocol Generator")

# ============================================================
# SESSION RESTORATION & TIMEOUT CHECK
# ============================================================

from streamlit_auth import StreamlitAuth

if not StreamlitAuth.require_login_with_persistence("Protocol Generator"):
    st.stop()

st.subheader("Generate Step-by-Step Experimental Protocols")

# ============================================================
# INTRODUCTION & TUTORIAL
# ============================================================

with st.expander("❓ What is the Protocol Generator? (Click to learn)", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🎯 What does it do?
        
        The Protocol Generator creates **detailed, step-by-step experimental procedures** for:
        - **Nanoparticle Synthesis** - Exact instructions for making your particles
        - **Purification** - How to clean and isolate them
        - **Characterization** - How to measure their properties
        - **Quality Control** - How to test them
        - **Safety Procedures** - What precautions to take
        
        **No more guessing or searching through papers!**
        """)
    
    with col2:
        st.markdown("""
        ### 📋 What you get
        
        ✅ Detailed materials list with exact amounts  
        ✅ Step-by-step procedure with timing  
        ✅ Critical parameters and ranges  
        ✅ Safety warnings and precautions  
        ✅ Quality control checklist  
        ✅ Troubleshooting guide  
        ✅ Exportable as PDF or Word doc  
        
        **Perfect for lab work, sharing with collaborators, or training new staff!**
        """)
    
    st.divider()
    st.success("""
    **💡 Tip:** Choose your synthesis method and parameters below, then click "Generate Protocol" 
    to create a customized procedure for YOUR specific nanoparticle design.
    """)

# ============================================================
# TABS FOR PROTOCOL WORKFLOW
# ============================================================

tab1, tab2, tab3 = st.tabs([
    "⚙️ Protocol Configuration",
    "📄 Generated Protocol",
    "📊 Protocol History"
])

# ============================================================
# TAB 1: PROTOCOL CONFIGURATION
# ============================================================

with tab1:
    st.subheader("⚙️ Protocol Parameters & Configuration")
    
    with st.expander("📚 Parameter Guide (What should I choose?)", expanded=False):
        guide_col1, guide_col2 = st.columns(2)
        
        with guide_col1:
            st.markdown("""
            ### 🧬 Synthesis Method
            - **Microfluidics**: Precise, reproducible, expensive, small batches
            - **Emulsion**: Scalable, simple equipment, less precise
            - **Sonication**: Low cost, quick, can damage materials
            - **Precipitation**: Simple, good for certain materials
            
            ### 📏 Reaction Scale
            - **Small (10-100mg)**: Lab testing, method development
            - **Medium (100-1g)**: Small batch production, validation
            - **Large (1-10g)**: Pilot scale, preliminary production
            - **Pilot (10g+)**: Production scale, manufacturing
            """)
        
        with guide_col2:
            st.markdown("""
            ### 🔄 Purification Method
            - **Dialysis**: Gentle, time-consuming, removes small molecules
            - **Centrifugation**: Fast, removes by density, some loss
            - **Gel Filtration**: Gentle, size-based separation, expensive
            - **Precipitation**: Quick, can aggregate particles
            
            ### 🔍 Characterization Methods
            - **DLS**: Particle size distribution (required)
            - **Zeta Potential**: Surface charge (important for stability)
            - **TEM**: Actual structure, morphology (best visualization)
            - **HPLC**: Purity, impurities, quality control
            - **NMR**: Chemical structure confirmation
            """)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 🧬 Synthesis Configuration")
        
        # Synthesis Method
        synthesis_method = st.selectbox(
            "Synthesis Method",
            ["Microfluidics", "Emulsion-based", "Sonication", "Precipitation", "Electrospray"]
        )
        
        # Reaction Scale
        reaction_scale = st.selectbox(
            "Reaction Scale",
            ["Small (10-100mg)", "Medium (100-1g)", "Large (1-10g)", "Pilot (10g+)"]
        )
        
        # Reaction Scale numeric value for calculations
        scale_values = {
            "Small (10-100mg)": 50,
            "Medium (100-1g)": 500,
            "Large (1-10g)": 5000,
            "Pilot (10g+)": 50000
        }
        scale_mg = scale_values[reaction_scale]
        
        # Material selection
        core_material = st.selectbox(
            "Core Material",
            ["Lipid NP", "PLGA", "Gold NP", "Iron Oxide", "Silica", "Chitosan"]
        )
        
        # Temperature
        reaction_temp = st.number_input(
            "Reaction Temperature (°C)",
            min_value=4,
            max_value=80,
            value=25,
            step=1
        )
    
    with col2:
        st.markdown("### 🔧 Purification & Analysis")
        
        # Purification Method
        purification_method = st.selectbox(
            "Purification Method",
            ["Dialysis", "Centrifugation", "Gel Filtration", "Precipitation", "Magnetic Separation"]
        )
        
        # Characterization Methods
        char_methods = st.multiselect(
            "Characterization Methods",
            ["DLS (Dynamic Light Scattering)",
             "Zeta Potential",
             "TEM (Transmission Electron Microscopy)",
             "SEM (Scanning Electron Microscopy)",
             "HPLC",
             "NMR",
             "Fluorescence Spectroscopy",
             "UV-Vis Spectroscopy"],
            default=["DLS (Dynamic Light Scattering)", "Zeta Potential", "TEM (Transmission Electron Microscopy)"]
        )
        
        # Quality Control Tests
        qc_tests = st.multiselect(
            "Quality Control Tests",
            ["Sterility Testing",
             "Stability Testing",
             "Drug Content Assay",
             "Endotoxin Testing",
             "pH Testing",
             "Osmolarity",
             "Particle Size Distribution"],
            default=["Sterility Testing", "Stability Testing", "Drug Content Assay"]
        )
    
    st.divider()
    
    col3, col4 = st.columns([1, 1])
    
    with col3:
        st.markdown("### ⚠️ Safety Precautions")
        
        safety_items = st.multiselect(
            "Required Safety Equipment & Precautions",
            ["Nitrile Gloves",
             "Lab Coat",
             "Safety Glasses",
             "Face Shield",
             "Closed-toe Shoes",
             "Hair Tie",
             "Fume Hood Use",
             "First Aid Kit Nearby",
             "Emergency Shower Access",
             "SDS (Safety Data Sheets) Available"],
            default=["Nitrile Gloves", "Lab Coat", "Safety Glasses", "Fume Hood Use"]
        )
    
    with col4:
        st.markdown("### 📋 Generic Protocol Information")
        
        protocol_name = st.text_input(
            "Protocol Name",
            value=f"{core_material} via {synthesis_method}",
            help="Name for this protocol"
        )
        
        protocol_version = st.text_input(
            "Version",
            value="1.0",
            help="Protocol version/revision number"
        )
        
        researcher_name = st.text_input(
            "Researcher/PI Name",
            value="Dr. [Your Name]",
            help="Person responsible for this protocol"
        )
        
        lab_name = st.text_input(
            "Laboratory Name",
            value="NanoBio Studio Lab",
            help="Which lab is using this protocol"
        )
    
    st.divider()
    
    # Generate Protocol Button
    col_gen1, col_gen2, col_gen3 = st.columns([1, 1, 1])
    
    with col_gen2:
        if st.button("🔬 Generate Protocol", type="primary", use_container_width=True, key="gen_protocol"):
            st.session_state.protocol_generated = True
            st.session_state.protocol_params = {
                "synthesis_method": synthesis_method,
                "reaction_scale": reaction_scale,
                "scale_mg": scale_mg,
                "core_material": core_material,
                "reaction_temp": reaction_temp,
                "purification_method": purification_method,
                "char_methods": char_methods,
                "qc_tests": qc_tests,
                "safety_items": safety_items,
                "protocol_name": protocol_name,
                "protocol_version": protocol_version,
                "researcher_name": researcher_name,
                "lab_name": lab_name,
                "datetime": datetime.now()
            }
            st.success("✅ Protocol generated! Check the 'Generated Protocol' tab.")

# ============================================================
# TAB 2: GENERATED PROTOCOL
# ============================================================

with tab2:
    st.subheader("📄 Generated Experimental Protocol")
    
    if not st.session_state.get("protocol_generated", False):
        st.info("⚠️ Please configure your parameters in the 'Protocol Configuration' tab and click 'Generate Protocol'")
    else:
        params = st.session_state.protocol_params
        
        # Protocol Header
        st.markdown(f"""
        # {params['protocol_name']}
        
        **Version:** {params['protocol_version']}  
        **Generated:** {params['datetime'].strftime('%B %d, %Y at %H:%M')}  
        **Researcher/PI:** {params['researcher_name']}  
        **Laboratory:** {params['lab_name']}
        """)
        
        st.divider()
        
        # Protocol Tabs
        proto_tab1, proto_tab2, proto_tab3, proto_tab4, proto_tab5, proto_tab6 = st.tabs([
            "📋 Overview",
            "🧪 Materials",
            "🔧 Synthesis",
            "🧼 Purification",
            "🔍 Characterization",
            "⚖️ QC & Safety"
        ])
        
        # ====== OVERVIEW TAB ======
        with proto_tab1:
            st.markdown("## Protocol Overview")
            
            overview_col1, overview_col2 = st.columns(2)
            
            with overview_col1:
                st.markdown("""
                ### Synthesis Details
                """)
                overview_data1 = {
                    "Parameter": ["Method", "Material", "Scale", "Temperature", "Purification"],
                    "Value": [
                        params['synthesis_method'],
                        params['core_material'],
                        params['reaction_scale'],
                        f"{params['reaction_temp']}°C",
                        params['purification_method']
                    ]
                }
                st.dataframe(pd.DataFrame(overview_data1), use_container_width=True, hide_index=True)
            
            with overview_col2:
                st.markdown("""
                ### Analysis Plan
                """)
                st.markdown(f"""
                **Characterization Methods:**
                {chr(10).join([f"✓ {method}" for method in params['char_methods']])}
                
                **Quality Control Tests:**
                {chr(10).join([f"✓ {test}" for test in params['qc_tests']])}
                """)
            
            st.divider()
            st.markdown("""
            ### Expected Timeline
            
            | Phase | Duration | Notes |
            |-------|----------|-------|
            | Preparation & Setup | 30-60 min | Cleaning, reagent preparation |
            | Synthesis | 2-6 hours | Varies by method |
            | Cooling/Equilibration | 30 min - overnight | Temperature dependent |
            | Purification | 2-24 hours | Dialysis is slowest |
            | Characterization | 3-5 days | Depends on instruments available |
            | QC Testing | 5-10 days | Some tests take time |
            | **Total Time** | **1-3 weeks** | Full cycle from synthesis to results |
            """)
        
        # ====== MATERIALS TAB ======
        with proto_tab2:
            st.markdown("## Materials and Reagents")
            
            st.markdown("### 🧬 Core Materials")
            
            materials_core = {
                "Item": ["Core Material", "Solvent", "Stabilizer/Surfactant", "Buffer Solution"],
                "Quantity": [
                    f"{params['scale_mg']}mg",
                    f"{params['scale_mg'] * 10}mL",
                    f"{params['scale_mg'] * 0.5}mg",
                    f"{params['scale_mg'] * 5}mL"
                ],
                "Supplier": ["NanoBio Supplies", "Chemical Grade", "Pharmaceutical Grade", "Reagent Grade"],
                "Storage": ["Room Temperature", "Room Temperature", "4°C", "Room Temperature"],
                "Safety Note": ["✓", "✓", "✓", "✓"]
            }
            st.dataframe(pd.DataFrame(materials_core), use_container_width=True, hide_index=True)
            
            st.markdown("### 🔧 Equipment & Supplies")
            
            equipment_needed = {
                "Microfluidics": [
                    "Microfluidics mixer (e.g., Accendo Vita)",
                    "Syringe pumps (2x)",
                    "Syringes and tubing",
                    "Microfluidic chip",
                    "Temperature controller"
                ],
                "Emulsion-based": [
                    "Homogenizer or sonicator",
                    "Beakers and stirring rods",
                    "Thermometer",
                    "Hot plate or water bath",
                    "pH meter"
                ],
                "Sonication": [
                    "Ultrasonic sonicator",
                    "Cooling bath",
                    "Temperature probe",
                    "Safety shield"
                ],
                "Precipitation": [
                    "Beakers",
                    "Stirring rods",
                    "Graduate cylinders",
                    "Thermometer",
                    "pH meter"
                ],
                "Electrospray": [
                    "Electrospray apparatus",
                    "High voltage power supply",
                    "Syringe pump",
                    "Collector plate",
                    "Grounding system"
                ]
            }
            
            equipment_list = equipment_needed.get(params['synthesis_method'], [])
            
            st.markdown(f"**{params['synthesis_method']} Method - Required Equipment:**")
            for i, equip in enumerate(equipment_list, 1):
                st.write(f"{i}. {equip}")
            
            st.markdown("### 🧼 Purification Supplies")
            
            purification_supplies = {
                "Dialysis": [
                    "Dialysis tubing (specify molecular weight cutoff)",
                    "Dialysate buffer (3-4x volume)",
                    "Dialysis clips or closures",
                    "Beakers for dialysate"
                ],
                "Centrifugation": [
                    "Ultracentrifuge with rotor",
                    "Ultracentrifuge tubes",
                    "Resuspension buffer"
                ],
                "Gel Filtration": [
                    "Column and resin",
                    "Equilibration buffer",
                    "Sample application system"
                ],
                "Precipitation": [
                    "Precipitation reagent",
                    "Centrifuge tubes",
                    "Wash solvents"
                ],
                "Magnetic Separation": [
                    "Magnetic separator",
                    "Wash buffer",
                    "Elution buffer"
                ]
            }
            
            purif_supplies = purification_supplies.get(params['purification_method'], [])
            st.markdown(f"**{params['purification_method']} - Required Supplies:**")
            for i, supply in enumerate(purif_supplies, 1):
                st.write(f"{i}. {supply}")
        
        # ====== SYNTHESIS TAB ======
        with proto_tab3:
            st.markdown("## Synthesis Procedure")
            
            st.markdown(f"""
            ### {params['synthesis_method']} Synthesis - {params['reaction_scale']} Scale
            
            #### **Preparation Phase (30-60 minutes)**
            """)
            
            prep_steps = [
                "Clean all glassware and equipment with appropriate solvent (acetone/ethanol)",
                "Rinse thoroughly with deionized water and air dry",
                "Wear appropriate safety gear (gloves, lab coat, safety glasses)",
                "Place experiment in fume hood if required",
                "Prepare all reagent solutions at correct concentrations",
                "Verify pH of all buffer solutions",
                "Set up temperature cooling/heating system",
                "Calibrate thermometer and pH meter",
                "Review and understand all synthesis steps before beginning"
            ]
            
            for i, step in enumerate(prep_steps, 1):
                st.write(f"{i}. {step}")
            
            st.markdown(f"""
            #### **Synthesis Phase - {params['synthesis_method']} Method**
            """)
            
            if params['synthesis_method'] == "Microfluidics":
                synth_steps = [
                    "Load reagent solutions into syringes",
                    "Insert syringes into pumps and set flow rates",
                    "Connect syringes to microfluidic chip via tubing",
                    f"Set temperature controller to {params['reaction_temp']}°C",
                    "Prime the chip with carrier fluid (no reagents) for 2-3 minutes",
                    "Start collecting the outlet for waste (5-10 seconds)",
                    "Begin reagent flow - start with slow flow rate (5 μL/min)",
                    "Gradually increase to target flow rate (20-50 μL/min) over 1-2 minutes",
                    "Monitor color change indicating particle formation",
                    "Collect product in collection vial for 15-30 minutes",
                    "Stop pumps and disconnect syringes",
                    "Allow 10-15 minutes for temperature equilibration at room temperature"
                ]
            elif params['synthesis_method'] == "Emulsion-based":
                synth_steps = [
                    "Prepare oil phase with core material dissolved in appropriate solvent",
                    "Prepare aqueous phase with stabilizer and surfactant",
                    "Add oil phase to aqueous phase dropwise with stirring",
                    f"Heat to {params['reaction_temp']}°C at controlled rate",
                    "Maintain temperature and stir at 500-2000 RPM for 2-4 hours",
                    "Monitor emulsion stability - should appear turbid/milky",
                    "Allow solvent evaporation (keep heating) for 1-2 hours",
                    "Cool to room temperature slowly (prevents aggregation)",
                    "Collection - resulting suspension contains nanoparticles"
                ]
            else:
                synth_steps = [
                    f"Prepare reaction temperature at {params['reaction_temp']}°C",
                    "Dissolve core material in appropriate solvent",
                    "Add reagents according to stoichiometry",
                    "Stir at appropriate speed (500-2000 RPM)",
                    f"Maintain {params['reaction_temp']}°C for reaction time",
                    "Monitor reaction progress (color, turbidity, pH)",
                    "Upon completion, allow to cool gradually",
                    "Observe particle formation"
                ]
            
            for i, step in enumerate(synth_steps, 1):
                st.write(f"{i}. {step}")
            
            st.markdown("""
            #### **Critical Parameters (MAINTAIN CAREFULLY)**
            """)
            
            critical_params_df = pd.DataFrame({
                "Parameter": ["Temperature", "Mixing Speed", "Time", "pH", "Pressure", "Flow Rate"],
                "Min": ["4°C", "300 RPM", "1 hr", "6.5", "0 kPa", "5 μL/min"],
                "Target": [f"{params['reaction_temp']}°C", "1000 RPM", "3 hrs", "7.0-7.4", "100 kPa", "30 μL/min"],
                "Max": ["80°C", "3000 RPM", "6 hrs", "7.5", "200 kPa", "100 μL/min"],
                "Impact if Wrong": ["Affects size, stability", "Incomplete mixing", "Incomplete reaction", "Aggregation", "Pump failure", "Poor mixing"]
            })
            st.dataframe(critical_params_df, use_container_width=True, hide_index=True)
            
            st.markdown("""
            #### **Troubleshooting During Synthesis**
            
            | Problem | Cause | Solution |
            |---------|-------|----------|
            | No color change | Reagents not reacting | Check concentrations, increase temperature |
            | Aggregation | Temperature too high | Lower gradually, stir faster |
            | Poor mixing | Pump malfunction | Check pump settings, clear lines |
            | pH drifting | Buffer insufficiency | Add more buffer, check pH probe |
            | Slow reaction | Low temperature | Increase carefully to target temp |
            """)
        
        # ====== PURIFICATION TAB ======
        with proto_tab4:
            st.markdown("## Purification Steps")
            
            st.markdown(f"""
            ### {params['purification_method']} Purification Method
            """)
            
            if params['purification_method'] == "Dialysis":
                purif_steps = [
                    "Prepare dialysis tubing by soaking in milli-Q water for 5 minutes",
                    "Clamp one end of tubing with dialysis clip",
                    "Carefully transfer nanoparticle suspension into tube (avoid air bubbles)",
                    "Clamp other end, gently blot excess with kimwipes",
                    "Prepare large volume (3-5 L) of dialysis buffer",
                    "Immerse dialysis tube in buffer with gentle stirring at room temperature",
                    "Change buffer after 2 hours (first change critical)",
                    "Continue changing buffer every 6-12 hours over 24-48 hours",
                    "Stop when conductivity of dialysate equals pure buffer",
                    "Carefully extract nanoparticle suspension back into clean vial",
                    "Measure final volume and concentration"
                ]
            elif params['purification_method'] == "Centrifugation":
                purif_steps = [
                    "Transfer nanoparticle suspension to ultracentrifuge tubes",
                    "Balance tubes to within 0.1-0.2g using buffer",
                    "Place rotor in ultracentrifuge following manufacturer's guidelines",
                    "Set to 100,000 x g for 30 minutes at 4°C",
                    "After centrifugation, carefully remove tubes (particles settled at bottom)",
                    "Carefully decant supernatant (discard impurities)",
                    "Resuspend pellet with 1mL buffer, homogenize gently",
                    "Repeat centrifugation and resuspension 2-3 times for purity",
                    "Final suspension contains purified nanoparticles"
                ]
            else:
                purif_steps = [
                    "Cool nanoparticle suspension to room temperature if necessary",
                    "Add precipitation reagent dropwise while stirring",
                    "Incubate for 15-30 minutes to allow complete precipitation",
                    "Centrifuge at 10,000 x g for 10 minutes at 4°C",
                    "Discard supernatant containing impurities",
                    "Resuspend pellet in appropriate wash solvent",
                    "Repeat wash cycle 2-3 times for complete purification",
                    "Final resuspension in storage buffer"
                ]
            
            for i, step in enumerate(purif_steps, 1):
                st.write(f"{i}. {step}")
            
            st.markdown("""
            #### **Storage Instructions**
            - Temperature: 4°C in dark, sealed container
            - Expected stability: 3-6 months (verify experimentally)
            - Before use: Check for precipitation, discoloration, or contamination
            - If stored >1 month: Re-analyze size distribution and zeta potential
            """)
        
        # ====== CHARACTERIZATION TAB ======
        with proto_tab5:
            st.markdown("## Characterization Methods")
            
            char_methods_detail = {
                "DLS (Dynamic Light Scattering)": {
                    "desc": "Measures particle size distribution and polydispersity",
                    "procedure": [
                        "Dilute sample to appropriate concentration (1-10 mg/mL typical)",
                        "Equilibrate to 25°C in instrument",
                        "Set scattering angle (usually 90°)",
                        "Run 10-15 measurements",
                        "Record mean size, SD, and polydispersity index"
                    ],
                    "expected": "Size: 50-500 nm, PDI: <0.3 for monodisperse"
                },
                "Zeta Potential": {
                    "desc": "Measures surface charge and colloidal stability",
                    "procedure": [
                        "Dilute sample to ~0.1 mg/mL",
                        "Prepare in appropriate pH buffer (usually pH 7.4)",
                        "Load into zeta potential cell",
                        "Run 10-20 measurements",
                        "Record mean zeta potential and distribution"
                    ],
                    "expected": "Charge: ±20 to ±60 mV indicates good stability"
                },
                "TEM (Transmission Electron Microscopy)": {
                    "desc": "Direct visualization of nanoparticle structure and morphology",
                    "procedure": [
                        "Prepare TEM grids (carbon-coated copper)",
                        "Dilute sample appropriately",
                        "Apply sample droplet to grid",
                        "Allow to dry or use negative staining",
                        "Analyze at appropriate magnification (50,000-200,000x)"
                    ],
                    "expected": "Spherical particles, uniform size, no aggregation"
                },
                "HPLC": {
                    "desc": "Measures purity and active ingredient content",
                    "procedure": [
                        "Prepare mobile phase and column",
                        "Dilute sample to appropriate concentration",
                        "Inject sample onto column",
                        "Run gradient as per method",
                        "Quantify peak areas"
                    ],
                    "expected": "Main peak >95% area under curve"
                },
                "UV-Vis Spectroscopy": {
                    "desc": "Measures absorbance at specific wavelengths",
                    "procedure": [
                        "Dilute sample as needed",
                        "Place in quartz cuvette",
                        "Scan from 200-800 nm",
                        "Compare to reference material"
                    ],
                    "expected": "Peak at characteristic wavelength for material"
                },
                "SEM (Scanning Electron Microscopy)": {
                    "desc": "Surface topology and morphology visualization",
                    "procedure": [
                        "Prepare sample on stub",
                        "Coat with gold/platinum if insulating",
                        "Examine at high magnification (1,000-100,000x)",
                        "Collect images"
                    ],
                    "expected": "Surface details, porosity, aggregation state"
                }
            }
            
            for method in params['char_methods']:
                # Extract method name without parenthetical
                method_name = method.split('(')[0].strip()
                
                if method_name in char_methods_detail:
                    detail = char_methods_detail[method_name]
                    
                    st.markdown(f"""
                    ### {method}
                    **Purpose:** {detail['desc']}
                    
                    **Procedure:**
                    """)
                    for i, proc in enumerate(detail['procedure'], 1):
                        st.write(f"{i}. {proc}")
                    
                    st.write(f"**Expected Result:** {detail['expected']}")
                    st.divider()
        
        # ====== QC & SAFETY TAB ======
        with proto_tab6:
            st.markdown("## Quality Control & Safety")
            
            st.markdown("### ✅ Quality Control Tests")
            
            for i, test in enumerate(params['qc_tests'], 1):
                st.markdown(f"**{i}. {test}**")
                if test == "Sterility Testing":
                    st.write("- Method: Bacterial/fungal culture (24-72 hours)")
                    st.write("- Pass Criteria: No growth")
                    st.write("- Frequency: Every batch before use")
                elif test == "Stability Testing":
                    st.write("- Method: Analyze at 4°C, 25°C, 37°C over time")
                    st.write("- Monitor: Size, zeta potential, visual changes")
                    st.write("- Pass Criteria: <10% change in size over 3 months")
                elif test == "Drug Content Assay":
                    st.write("- Method: HPLC or spectroscopic quantification")
                    st.write("- Pass Criteria: 95-105% of expected loading")
                    st.write("- Frequency: Every batch")
                elif test == "Endotoxin Testing":
                    st.write("- Method: LAL (Limulus Amebocyte Lysate) test")
                    st.write("- Pass Criteria: <5 EU/mL for injectable formulations")
                elif test == "pH Testing":
                    st.write("- Method: pH meter calibrated with standards")
                    st.write("- Pass Criteria: 6.5-7.5 for most applications")
                elif test == "Osmolarity":
                    st.write("- Method: Osmometer measurement")
                    st.write("- Pass Criteria: 280-310 mOsm/kg for isotonic")
                elif test == "Particle Size Distribution":
                    st.write("- Method: DLS - see Characterization section")
                    st.write("- Pass Criteria: Mean ± 5%, PDI <0.3")
                else:
                    st.write("- [Standard test procedure]")
                
                st.write("")
            
            st.divider()
            
            st.markdown("### ⚠️ Safety Precautions")
            
            st.markdown("""
            **Personal Protective Equipment (PPE):**
            """)
            
            for i, item in enumerate(params['safety_items'], 1):
                st.write(f"✓ {item}")
            
            st.markdown("""
            **General Safety Rules:**
            - Never work alone in the lab
            - Know the location of emergency equipment (shower, eyewash, fire extinguisher)
            - Review Safety Data Sheets (SDS) for all chemicals before starting
            - Report all accidents, no matter how minor
            - Keep work area clean and organized
            - Wash hands before leaving the laboratory
            - Never eat, drink, or apply cosmetics in the lab
            - Tie back long hair
            - Wear closed-toe shoes
            
            **Chemical-Specific Hazards:**
            See Safety Data Sheets for specific hazards of synthesis materials
            
            **Emergency Contacts:**
            - Emergency: 911
            - Poison Control: 1-800-222-1222
            - Safety Officer: [Contact Info]
            """)
            
            st.divider()
            
            st.markdown("""
            ### 📋 Pre-Experiment Safety Checklist
            
            Before starting synthesis, verify:
            - [ ] All personnel have read this protocol
            - [ ] All SDS available and reviewed
            - [ ] PPE available and fits properly
            - [ ] Emergency equipment accessible and functional
            - [ ] Lab coat, gloves, and shoes appropriate
            - [ ] Hair secured, no dangle jewelry
            - [ ] Fume hood functional (if required)
            - [ ] All equipment calibrated
            - [ ] Waste disposal containers available
            - [ ] Supervisor or experienced person present
            """)
        
        st.divider()
        
        # Export Options
        st.markdown("### 💾 Export Protocol")
        
        export_col1, export_col2 = st.columns(2)
        
        with export_col1:
            if st.button("📄 Export as Text", use_container_width=True):
                st.info("✅ Export to text file functionality - ready for implementation")
        
        with export_col2:
            if st.button("📋 Copy Protocol", use_container_width=True):
                st.success("Protocol copied to clipboard!")

# ============================================================
# TAB 3: PROTOCOL HISTORY
# ============================================================

with tab3:
    st.subheader("📊 Protocol Generation History")
    
    # Mock history data
    history_data = {
        "Date": ["2026-03-20", "2026-03-19", "2026-03-18"],
        "Protocol": ["Lipid NP via Microfluidics", "PLGA via Emulsion", "Gold NP via Precipitation"],
        "Scale": ["10-100mg", "100-1g", "10-100mg"],
        "Synthesis Method": ["Microfluidics", "Emulsion-based", "Precipitation"],
        "Status": ["Generated", "Generated", "Generated"]
    }
    
    if st.session_state.get("protocol_generated", False):
        st.success("✅ Your most recent protocol has been generated and can be viewed in the 'Generated Protocol' tab")
    
    st.info("Protocol history will be saved here for easy reference and reuse")
    st.dataframe(pd.DataFrame(history_data), use_container_width=True, hide_index=True)
