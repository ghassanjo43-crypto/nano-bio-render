"""
Import/Export Page
"""

import streamlit as st
import json
from datetime import datetime

def show():
    """Display import/export interface"""
    st.title("💾 Import / Export")
    st.markdown("Save or load nanoparticle designs and export results")
    
    st.markdown("---")
    
    # Tabs for import and export
    tab1, tab2 = st.tabs(["📥 Import Design", "📤 Export Data"])
    
    with tab1:
        st.subheader("Import Nanoparticle Design")
        st.markdown("Load a previously saved design from JSON file")
        
        uploaded_file = st.file_uploader(
            "Choose a JSON file",
            type=['json'],
            help="Upload a design file previously exported from NanoBio Studio"
        )
        
        if uploaded_file is not None:
            try:
                design_data = json.load(uploaded_file)
                
                # Display loaded design
                st.success(f"✅ Successfully loaded design: {design_data.get('name', 'Unknown')}")
                
                with st.expander("📋 Loaded Design Preview"):
                    st.json(design_data)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Load This Design", type="primary", use_container_width=True):
                        # Update session state with loaded design
                        for key, value in design_data.items():
                            if key in st.session_state.design:
                                st.session_state.design[key] = value
                        
                        st.success("✅ Design loaded successfully!")
                        st.info("Navigate to **Design Nanoparticle** page to view loaded parameters")
                        st.balloons()
                
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.info("Import cancelled")
            
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON file. Please upload a valid design file.")
            except Exception as e:
                st.error(f"❌ Error loading file: {str(e)}")
        
        else:
            st.info("👆 Upload a JSON design file to import")
        
        st.markdown("---")
        
        # Load from template
        st.subheader("📚 Load from Template")
        st.markdown("Start with a pre-configured design template")
        
        templates = {
            "mRNA-LNP for Tumor": {
                'name': 'mRNA-LNP-Tumor-001',
                'material': 'Lipid Nanoparticle (LNP)',
                'size': 80.0,
                'charge': -5.0,
                'ligand': 'PEG2000',
                'payload': 'mRNA',
                'payload_amount': 40.0,
                'target': 'Tumor Tissue (Solid)',
                'dose': 2.0,
                'pdi': 0.12,
                'kabs': 0.8,
                'kel': 0.15,
                'k12': 0.4,
                'k21': 0.25
            },
            "siRNA-PLGA for Liver": {
                'name': 'siRNA-PLGA-Liver-001',
                'material': 'Polymeric Nanoparticle (PLGA)',
                'size': 150.0,
                'charge': -15.0,
                'ligand': 'PEG (Polyethylene Glycol)',
                'payload': 'siRNA',
                'payload_amount': 30.0,
                'target': 'Liver Hepatocytes',
                'dose': 5.0,
                'pdi': 0.18,
                'kabs': 0.5,
                'kel': 0.1,
                'k12': 0.3,
                'k21': 0.2
            },
            "Gold NP for Imaging": {
                'name': 'AuNP-Imaging-001',
                'material': 'Gold Nanoparticle (AuNP)',
                'size': 20.0,
                'charge': -20.0,
                'ligand': 'PEG (Polyethylene Glycol)',
                'payload': 'Imaging agent',
                'payload_amount': 10.0,
                'target': 'Tumor Tissue (Solid)',
                'dose': 1.0,
                'pdi': 0.08,
                'kabs': 1.0,
                'kel': 0.2,
                'k12': 0.5,
                'k21': 0.3
            }
        }
        
        template_choice = st.selectbox(
            "Select a template",
            list(templates.keys())
        )
        
        if st.button("📥 Load Template", use_container_width=True):
            st.session_state.design = templates[template_choice].copy()
            st.success(f"✅ Template '{template_choice}' loaded!")
            st.info("Navigate to **Design Nanoparticle** page to view and modify parameters")
    
    with tab2:
        st.subheader("Export Nanoparticle Design")
        st.markdown("Save your current design and results")
        
        # Current design export
        st.markdown("### 📋 Current Design")
        
        # Add timestamp
        export_design = st.session_state.design.copy()
        export_design['export_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        export_design['version'] = '1.0'
        
        with st.expander("Preview Design JSON"):
            st.json(export_design)
        
        json_str = json.dumps(export_design, indent=2)
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            st.download_button(
                label="📥 Download Design (JSON)",
                data=json_str,
                file_name=f"{export_design['name']}_design.json",
                mime="application/json",
                use_container_width=True
            )
        
        with col_exp2:
            # Export as CSV (flattened)
            import pandas as pd
            
            df_design = pd.DataFrame([export_design])
            csv_design = df_design.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Design (CSV)",
                data=csv_design,
                file_name=f"{export_design['name']}_design.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        st.markdown("---")
        
        # Export all results
        st.markdown("### 📊 Export All Results")
        st.markdown("Download a complete package of design, simulation, safety, and cost data")
        
        if st.button("📦 Create Complete Export Package", type="primary", use_container_width=True):
            # Create comprehensive export
            complete_export = {
                'design': export_design,
                'simulation_results': st.session_state.simulation_results if st.session_state.simulation_results else "Not run",
                'safety_assessment': st.session_state.safety_assessment if hasattr(st.session_state, 'safety_assessment') and st.session_state.safety_assessment else "Not run",
                'cost_results': st.session_state.cost_results if st.session_state.cost_results else "Not run",
                'export_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Convert to JSON (handle numpy arrays if present)
            def convert_to_serializable(obj):
                import numpy as np
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, (np.int64, np.int32)):
                    return int(obj)
                elif isinstance(obj, (np.float64, np.float32)):
                    return float(obj)
                else:
                    return obj
            
            # Convert numpy arrays in simulation results
            if complete_export['simulation_results'] != "Not run":
                sim_export = {}
                for key, value in complete_export['simulation_results'].items():
                    sim_export[key] = convert_to_serializable(value)
                complete_export['simulation_results'] = sim_export
            
            complete_json = json.dumps(complete_export, indent=2, default=convert_to_serializable)
            
            st.download_button(
                label="📥 Download Complete Package (JSON)",
                data=complete_json,
                file_name=f"{export_design['name']}_complete_export.json",
                mime="application/json",
                use_container_width=True
            )
            
            st.success("✅ Export package created!")
        
        st.markdown("---")
        
        # Batch export information
        with st.expander("ℹ️ About Import/Export"):
            st.markdown("""
            ### Import/Export Features
            
            **Design Files (JSON):**
            - Save your nanoparticle designs for later use
            - Share designs with collaborators
            - Version control for iterative design
            - Complete parameter preservation
            
            **Complete Export Package:**
            - Design parameters
            - Simulation results (PK/PD data)
            - Safety assessment scores
            - Cost analysis
            - Timestamp and version information
            
            **CSV Export:**
            - Spreadsheet-compatible format
            - Easy integration with data analysis tools
            - Batch comparison of multiple designs
            
            **Templates:**
            - Pre-configured designs for common applications
            - Starting points for new formulations
            - Educational examples
            
            **Best Practices:**
            - ✅ Export designs regularly
            - ✅ Use descriptive naming conventions
            - ✅ Include version numbers
            - ✅ Document any manual modifications
            - ✅ Keep backups of important designs
            
            **File Compatibility:**
            - JSON files are human-readable and version-control friendly
            - CSV files can be opened in Excel, Google Sheets, etc.
            - Compatible with R, Python pandas, and other analysis tools
            """)
