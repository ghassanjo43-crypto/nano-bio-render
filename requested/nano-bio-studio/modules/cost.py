"""
Cost Estimation Page
"""

import streamlit as st
import pandas as pd

def calculate_material_cost(design: dict, batch_size: float, cost_params: dict) -> dict:
    """Calculate material costs for nanoparticle production"""
    
    material_name = design.get('Material', 'Lipid NP').lower()
    
    # Base material cost per gram (USD)
    material_costs = {
        'lipid': cost_params['lipid_cost'],
        'gold': cost_params['gold_cost'],
        'plga': cost_params['plga_cost'],
        'polymer': cost_params['polymer_cost'],
        'silica': cost_params['silica_cost'],
        'liposome': cost_params['lipid_cost'] * 1.2,
        'quantum': cost_params['quantum_cost'],
        'carbon': cost_params['carbon_cost'],
        'dendrimer': cost_params['dendrimer_cost'],
        'mof': cost_params['mof_cost'],
        'exosome': cost_params['exosome_cost']
    }
    
    # Find matching material
    base_cost_per_g = 50  # default
    for key, cost in material_costs.items():
        if key in material_name:
            base_cost_per_g = cost
            break
    
    # Calculate total material needed
    material_needed_g = batch_size / 1000  # Convert mg to g
    material_cost = material_needed_g * base_cost_per_g
    
    return {
        'material_cost': material_cost,
        'material_needed_g': material_needed_g,
        'cost_per_g': base_cost_per_g
    }

def calculate_ligand_cost(design: dict, batch_size: float, cost_params: dict) -> dict:
    """Calculate ligand/surface modification costs"""
    
    ligand_name = design.get('Ligand', 'GalNAc').lower()
    
    # Ligand costs per gram (USD)
    ligand_costs = {
        'peg': cost_params['peg_cost'],
        'peg2000': cost_params['peg_cost'] * 1.5,
        'cholesterol': cost_params['cholesterol_cost'],
        'antibody': cost_params['antibody_cost'],
        'mab': cost_params['antibody_cost'],
        'peptide': cost_params['peptide_cost'],
        'rgd': cost_params['peptide_cost'],
        'folate': cost_params['folate_cost'],
        'transferrin': cost_params['transferrin_cost'],
        'hyaluronic': cost_params['ha_cost'],
        'none': 0
    }
    
    # Find matching ligand
    ligand_cost_per_g = 100  # default
    for key, cost in ligand_costs.items():
        if key in ligand_name:
            ligand_cost_per_g = cost
            break
    
    # Estimate ligand coverage (typically 5-10% of particle mass)
    ligand_fraction = 0.075  # 7.5% average
    ligand_needed_g = (batch_size / 1000) * ligand_fraction
    ligand_cost = ligand_needed_g * ligand_cost_per_g
    
    return {
        'ligand_cost': ligand_cost,
        'ligand_needed_g': ligand_needed_g,
        'cost_per_g': ligand_cost_per_g
    }

def calculate_payload_cost(design: dict, batch_size: float, cost_params: dict) -> dict:
    """Calculate payload costs"""
    
    payload_name = design['payload'].lower()
    loading = design['payload_amount'] / 100  # Convert percentage to fraction
    
    # Payload costs per gram (USD)
    payload_costs = {
        'mrna': cost_params['mrna_cost'],
        'sirna': cost_params['sirna_cost'],
        'dna': cost_params['dna_cost'],
        'plasmid': cost_params['dna_cost'],
        'small molecule': cost_params['small_molecule_cost'],
        'drug': cost_params['small_molecule_cost'],
        'protein': cost_params['protein_cost'],
        'peptide': cost_params['peptide_cost'],
        'antibody': cost_params['antibody_cost'],
        'crispr': cost_params['crispr_cost'],
        'cas': cost_params['crispr_cost'],
        'imaging': cost_params['imaging_cost'],
        'none': 0
    }
    
    # Find matching payload
    payload_cost_per_g = 500  # default
    for key, cost in payload_costs.items():
        if key in payload_name:
            payload_cost_per_g = cost
            break
    
    # Calculate payload needed
    payload_needed_g = (batch_size / 1000) * loading
    payload_cost = payload_needed_g * payload_cost_per_g
    
    return {
        'payload_cost': payload_cost,
        'payload_needed_g': payload_needed_g,
        'cost_per_g': payload_cost_per_g
    }

def show():
    """Display cost estimator interface"""
    st.title("💰 Cost Estimator")
    st.markdown("Calculate manufacturing and clinical costs for your nanoparticle formulation")
    
    st.markdown("---")
    
    # Input parameters
    st.subheader("⚙️ Production Parameters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        batch_size = st.number_input(
            "Batch Size (mg)",
            min_value=1.0,
            max_value=10000.0,
            value=1000.0,
            step=100.0,
            help="Total amount of nanoparticles to produce"
        )
        
        num_subjects = st.number_input(
            "Number of Subjects/Patients",
            min_value=1,
            max_value=10000,
            value=10,
            step=1,
            help="Number of patients for clinical use"
        )
        
        subject_weight = st.number_input(
            "Average Subject Weight (kg)",
            min_value=10.0,
            max_value=150.0,
            value=70.0,
            step=5.0,
            help="Average patient body weight"
        )
    
    with col2:
        num_doses = st.number_input(
            "Doses per Subject",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            help="Number of doses per patient"
        )
        
        overhead_factor = st.number_input(
            "Overhead Factor",
            min_value=1.0,
            max_value=5.0,
            value=2.0,
            step=0.1,
            format="%.1f",
            help="Multiplier for overhead costs (labor, equipment, facilities)"
        )
        
        waste_factor = st.number_input(
            "Waste/Loss Factor",
            min_value=1.0,
            max_value=3.0,
            value=1.3,
            step=0.05,
            format="%.2f",
            help="Account for material waste during production"
        )
    
    st.markdown("---")
    
    # Cost parameters (customizable)
    with st.expander("💵 Cost Parameters (USD per gram)", expanded=False):
        st.markdown("Adjust unit costs for materials and reagents:")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.markdown("**Core Materials:**")
            lipid_cost = st.number_input("Lipid", value=150.0, step=10.0)
            plga_cost = st.number_input("PLGA", value=80.0, step=10.0)
            gold_cost = st.number_input("Gold", value=500.0, step=50.0)
            silica_cost = st.number_input("Silica", value=20.0, step=5.0)
        
        with col_b:
            st.markdown("**Surface Ligands:**")
            peg_cost = st.number_input("PEG", value=100.0, step=10.0)
            cholesterol_cost = st.number_input("Cholesterol", value=50.0, step=5.0)
            peptide_cost = st.number_input("Peptide", value=500.0, step=50.0)
            antibody_cost = st.number_input("Antibody", value=5000.0, step=500.0)
        
        with col_c:
            st.markdown("**Payloads:**")
            mrna_cost = st.number_input("mRNA", value=10000.0, step=1000.0)
            sirna_cost = st.number_input("siRNA", value=8000.0, step=500.0)
            dna_cost = st.number_input("DNA", value=5000.0, step=500.0)
            small_molecule_cost = st.number_input("Small Molecule", value=1000.0, step=100.0)
        
        # Additional costs
        quantum_cost = 1000.0
        carbon_cost = 300.0
        dendrimer_cost = 800.0
        mof_cost = 400.0
        exosome_cost = 15000.0
        folate_cost = 150.0
        transferrin_cost = 3000.0
        ha_cost = 200.0
        protein_cost = 3000.0
        crispr_cost = 12000.0
        imaging_cost = 2000.0
    
    cost_params = {
        'lipid_cost': lipid_cost,
        'plga_cost': plga_cost,
        'polymer_cost': plga_cost,
        'gold_cost': gold_cost,
        'silica_cost': silica_cost,
        'quantum_cost': quantum_cost,
        'carbon_cost': carbon_cost,
        'dendrimer_cost': dendrimer_cost,
        'mof_cost': mof_cost,
        'exosome_cost': exosome_cost,
        'peg_cost': peg_cost,
        'cholesterol_cost': cholesterol_cost,
        'peptide_cost': peptide_cost,
        'antibody_cost': antibody_cost,
        'folate_cost': folate_cost,
        'transferrin_cost': transferrin_cost,
        'ha_cost': ha_cost,
        'mrna_cost': mrna_cost,
        'sirna_cost': sirna_cost,
        'dna_cost': dna_cost,
        'small_molecule_cost': small_molecule_cost,
        'protein_cost': protein_cost,
        'crispr_cost': crispr_cost,
        'imaging_cost': imaging_cost
    }
    
    st.markdown("---")
    
    # Calculate costs
    col_calc1, col_calc2, col_calc3 = st.columns([1, 1, 1])
    
    with col_calc2:
        if st.button("💵 Calculate Costs", type="primary", use_container_width=True):
            with st.spinner("Calculating production costs..."):
                # Adjust batch size for waste
                adjusted_batch_size = batch_size * waste_factor
                
                # Calculate component costs
                material_result = calculate_material_cost(st.session_state.design, adjusted_batch_size, cost_params)
                ligand_result = calculate_ligand_cost(st.session_state.design, adjusted_batch_size, cost_params)
                payload_result = calculate_payload_cost(st.session_state.design, adjusted_batch_size, cost_params)
                
                # Direct material costs
                direct_cost = (
                    material_result['material_cost'] +
                    ligand_result['ligand_cost'] +
                    payload_result['payload_cost']
                )
                
                # Total production cost (including overhead)
                total_production_cost = direct_cost * overhead_factor
                
                # Per-subject calculations
                dose_per_subject = st.session_state.design['dose'] * subject_weight  # mg
                total_dose_per_subject = dose_per_subject * num_doses
                total_dose_needed = total_dose_per_subject * num_subjects
                
                cost_per_subject = (total_production_cost / batch_size) * total_dose_per_subject
                cost_per_dose = cost_per_subject / num_doses
                
                # Store results
                st.session_state.cost_results = {
                    'direct_cost': direct_cost,
                    'total_production_cost': total_production_cost,
                    'cost_per_mg': total_production_cost / batch_size,
                    'cost_per_subject': cost_per_subject,
                    'cost_per_dose': cost_per_dose,
                    'material_result': material_result,
                    'ligand_result': ligand_result,
                    'payload_result': payload_result,
                    'batch_size': batch_size,
                    'adjusted_batch_size': adjusted_batch_size,
                    'dose_per_subject': dose_per_subject,
                    'total_dose_per_subject': total_dose_per_subject,
                    'total_dose_needed': total_dose_needed,
                    'overhead_factor': overhead_factor,
                    'waste_factor': waste_factor,
                    'num_subjects': num_subjects,
                    'num_doses': num_doses
                }
                
                st.success("✅ Cost calculation completed!")
    
    st.markdown("---")
    
    # Display results
    if st.session_state.cost_results is not None:
        results = st.session_state.cost_results
        
        st.subheader("📊 Cost Analysis Results")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Batch Cost",
                f"${results['total_production_cost']:,.2f}",
                help="Total cost to produce the batch"
            )
        
        with col2:
            st.metric(
                "Cost per mg",
                f"${results['cost_per_mg']:.2f}",
                help="Unit cost per milligram"
            )
        
        with col3:
            st.metric(
                "Cost per Subject",
                f"${results['cost_per_subject']:,.2f}",
                help="Total cost per patient for all doses"
            )
        
        with col4:
            st.metric(
                "Cost per Dose",
                f"${results['cost_per_dose']:,.2f}",
                help="Cost per individual dose"
            )
        
        st.markdown("---")
        
        # Cost breakdown
        st.subheader("💵 Cost Breakdown")
        
        breakdown_col1, breakdown_col2 = st.columns(2)
        
        with breakdown_col1:
            st.markdown("### Direct Material Costs")
            
            df_materials = pd.DataFrame([
                {
                    'Component': 'Core Material',
                    'Amount (g)': f"{results['material_result']['material_needed_g']:.3f}",
                    'Cost/g': f"${results['material_result']['cost_per_g']:.2f}",
                    'Total Cost': f"${results['material_result']['material_cost']:.2f}"
                },
                {
                    'Component': 'Surface Ligand',
                    'Amount (g)': f"{results['ligand_result']['ligand_needed_g']:.3f}",
                    'Cost/g': f"${results['ligand_result']['cost_per_g']:.2f}",
                    'Total Cost': f"${results['ligand_result']['ligand_cost']:.2f}"
                },
                {
                    'Component': 'Therapeutic Payload',
                    'Amount (g)': f"{results['payload_result']['payload_needed_g']:.3f}",
                    'Cost/g': f"${results['payload_result']['cost_per_g']:.2f}",
                    'Total Cost': f"${results['payload_result']['payload_cost']:.2f}"
                },
                {
                    'Component': 'DIRECT TOTAL',
                    'Amount (g)': '-',
                    'Cost/g': '-',
                    'Total Cost': f"${results['direct_cost']:.2f}"
                }
            ])
            
            st.dataframe(df_materials, use_container_width=True, hide_index=True)
            
            st.info(f"**Overhead Factor:** {results['overhead_factor']}x")
            st.info(f"**Waste Factor:** {results['waste_factor']}x")
        
        with breakdown_col2:
            st.markdown("### Production Summary")
            
            st.metric("Batch Size (usable)", f"{results['batch_size']:.1f} mg")
            st.metric("Material Needed (with waste)", f"{results['adjusted_batch_size']:.1f} mg")
            st.metric("Dose per Subject", f"{results['dose_per_subject']:.2f} mg")
            st.metric("Total Dose per Subject", f"{results['total_dose_per_subject']:.2f} mg")
            st.metric("Total Material Needed", f"{results['total_dose_needed']:.2f} mg")
            
            if results['batch_size'] < results['total_dose_needed']:
                st.warning(f"⚠️ Batch size insufficient! Need {results['total_dose_needed']:.1f} mg but only producing {results['batch_size']:.1f} mg")
            else:
                st.success(f"✅ Batch size sufficient for {results['num_subjects']} subjects")
        
        st.markdown("---")
        
        # Cost distribution chart
        st.subheader("📈 Cost Distribution")
        
        import matplotlib.pyplot as plt
        
        # Pie chart of cost components
        labels = ['Core Material', 'Surface Ligand', 'Payload', 'Overhead']
        sizes = [
            results['material_result']['material_cost'],
            results['ligand_result']['ligand_cost'],
            results['payload_result']['payload_cost'],
            results['direct_cost'] * (results['overhead_factor'] - 1)
        ]
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
        explode = (0.05, 0.05, 0.1, 0.05)  # Explode the payload slice
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
               shadow=True, startangle=90)
        ax.axis('equal')
        plt.title('Cost Distribution by Component', fontsize=14, fontweight='bold')
        
        st.pyplot(fig)
        
        st.markdown("---")
        
        # Sensitivity analysis
        st.subheader("📊 Cost Sensitivity")
        
        col_sens1, col_sens2 = st.columns(2)
        
        with col_sens1:
            st.markdown("**Impact of Batch Size:**")
            batch_sizes = [100, 500, 1000, 5000, 10000]
            costs_per_mg = [results['direct_cost'] * results['overhead_factor'] / bs for bs in batch_sizes]
            
            df_batch = pd.DataFrame({
                'Batch Size (mg)': batch_sizes,
                'Cost per mg ($)': [f"${c:.2f}" for c in costs_per_mg]
            })
            st.dataframe(df_batch, use_container_width=True, hide_index=True)
        
        with col_sens2:
            st.markdown("**Impact of Subject Number:**")
            subject_nums = [1, 10, 50, 100, 500]
            total_costs = [results['cost_per_subject'] * n for n in subject_nums]
            
            df_subjects = pd.DataFrame({
                'Number of Subjects': subject_nums,
                'Total Cost ($)': [f"${c:,.2f}" for c in total_costs]
            })
            st.dataframe(df_subjects, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Export
        st.subheader("💾 Export Cost Analysis")
        
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            # Create detailed report
            report_text = f"""
NANOBIO STUDIO - COST ANALYSIS REPORT
======================================

Formulation: {st.session_state.design.get('FormulationName', 'Design')}
Material: {st.session_state.design.get('Material', 'Lipid NP')}
Target: {st.session_state.design['target']}

PRODUCTION PARAMETERS:
----------------------
Batch Size: {results['batch_size']:.2f} mg
Adjusted (with waste): {results['adjusted_batch_size']:.2f} mg
Waste Factor: {results['waste_factor']}x
Overhead Factor: {results['overhead_factor']}x

DOSING PARAMETERS:
------------------
Dose: {st.session_state.design['dose']:.2f} mg/kg
Subject Weight: {subject_weight:.1f} kg
Dose per Subject: {results['dose_per_subject']:.2f} mg
Number of Doses: {results['num_doses']}
Total per Subject: {results['total_dose_per_subject']:.2f} mg
Number of Subjects: {results['num_subjects']}
Total Needed: {results['total_dose_needed']:.2f} mg

COST BREAKDOWN:
---------------
Core Material: ${results['material_result']['material_cost']:.2f}
  ({results['material_result']['material_needed_g']:.3f}g @ ${results['material_result']['cost_per_g']:.2f}/g)

Surface Ligand: ${results['ligand_result']['ligand_cost']:.2f}
  ({results['ligand_result']['ligand_needed_g']:.3f}g @ ${results['ligand_result']['cost_per_g']:.2f}/g)

Therapeutic Payload: ${results['payload_result']['payload_cost']:.2f}
  ({results['payload_result']['payload_needed_g']:.3f}g @ ${results['payload_result']['cost_per_g']:.2f}/g)

Direct Material Cost: ${results['direct_cost']:.2f}
Overhead ({results['overhead_factor']}x): ${results['direct_cost'] * (results['overhead_factor'] - 1):.2f}

TOTAL PRODUCTION COST: ${results['total_production_cost']:.2f}

UNIT COSTS:
-----------
Cost per mg: ${results['cost_per_mg']:.2f}
Cost per dose: ${results['cost_per_dose']:.2f}
Cost per subject: ${results['cost_per_subject']:.2f}

TOTAL PROGRAM COST ({results['num_subjects']} subjects): ${results['cost_per_subject'] * results['num_subjects']:.2f}

---
Generated by NanoBio Studio
Experts Group FZE
"""
            
            st.download_button(
                label="📥 Download Cost Report (TXT)",
                data=report_text,
                file_name=f"{st.session_state.design.get('FormulationName', 'design')}_cost_analysis.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col_export2:
            # Export as CSV
            df_export = pd.DataFrame([{
                'Formulation': st.session_state.design.get('FormulationName', 'Design'),
                'Batch_Size_mg': results['batch_size'],
                'Total_Batch_Cost_USD': results['total_production_cost'],
                'Cost_per_mg_USD': results['cost_per_mg'],
                'Cost_per_Subject_USD': results['cost_per_subject'],
                'Cost_per_Dose_USD': results['cost_per_dose'],
                'Material_Cost_USD': results['material_result']['material_cost'],
                'Ligand_Cost_USD': results['ligand_result']['ligand_cost'],
                'Payload_Cost_USD': results['payload_result']['payload_cost'],
                'Direct_Cost_USD': results['direct_cost'],
                'Overhead_Factor': results['overhead_factor'],
                'Waste_Factor': results['waste_factor']
            }])
            
            csv_export = df_export.to_csv(index=False)
            
            st.download_button(
                label="📥 Download Cost Data (CSV)",
                data=csv_export,
                file_name=f"{st.session_state.design.get('FormulationName', 'design')}_cost_data.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    else:
        st.info("👆 Click **Calculate Costs** to generate cost analysis")
        
        with st.expander("ℹ️ About Cost Estimation"):
            st.markdown("""
            ### Cost Calculation Methodology
            
            **Direct Material Costs:**
            - Core nanoparticle material
            - Surface ligands/modifications
            - Therapeutic payload
            
            **Overhead Factor:**
            - Labor costs
            - Equipment depreciation
            - Facility costs
            - Quality control
            - Regulatory compliance
            
            **Waste Factor:**
            - Material loss during synthesis
            - Purification losses
            - QC testing consumption
            - Failed batches
            
            **Cost per Subject:**
            Based on dose (mg/kg), subject weight, and number of doses
            
            **Important Notes:**
            - Costs are estimates based on typical market prices
            - Actual costs vary by supplier, volume, and purity grade
            - R&D costs are not included
            - Clinical trial costs are not included
            - Regulatory filing costs are not included
            - Scale-up may significantly reduce unit costs
            
            **Cost Optimization Strategies:**
            - Increase batch size for economies of scale
            - Optimize payload loading
            - Consider alternative materials
            - Minimize waste through process optimization
            - Use cost-effective ligands where appropriate
            """)
