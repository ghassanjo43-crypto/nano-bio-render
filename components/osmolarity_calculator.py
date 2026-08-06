"""
Osmolarity Calculator for Nanoparticle Formulations
Calculates colloidal stability and potential for osmotic toxicity
"""

import streamlit as st
from typing import Dict, Tuple


def calculate_osmolarity(design: Dict) -> Dict:
    """
    Calculate osmolarity of nanoparticle formulation.
    
    Osmolarity prediction based on formulation components:
    - Lipids and their concentrations
    - Buffer salt concentration
    - Drug concentration
    - Excipients
    
    Physiological osmolarity: 270-310 mOsm/kg
    Safe range for IV injection: 250-350 mOsm/kg
    
    Args:
        design: Dictionary with formulation parameters
        
    Returns:
        Dictionary with osmolarity calculation and safety assessment
    """
    
    # Extract parameters with safe defaults
    encapsulation_pct = float(design.get("Encapsulation", 85))
    size_nm = float(design.get("Size", 100))
    drug_loading_pct = float(design.get("Drug", 50))
    peg_density_pct = float(design.get("PEG_Density", 50))
    material = design.get("Material", "Lipid NP")
    
    # ================================================================
    # OSMOLARITY CALCULATION
    # ================================================================
    
    # Base osmolarity from lipid formulation
    # Typical LNP: 4 lipids at ~50-100 nmol/mL each
    material_osmolarity_base = {
        "Lipid NP": 250,        # 4 lipids × ~60 nmol/mL
        "PLGA": 150,            # Lower osmolen count
        "Gold NP": 80,          # Minimal water-soluble component
        "Silica NP": 100,       # Inorganic core
        "DNA Origami": 300,     # DNA phosphate groups osmotically active
        "Liposome": 280,        # Similar to LNP
        "Polymeric NP": 160,    # Polymer backbone contribution
        "Albumin NP": 200,      # Protein core
    }
    
    base_osmolarity = material_osmolarity_base.get(material, 200)
    
    # Drug contribution to osmolarity
    # Each % of drug adds small osmolar contribution (~0.5-1.0 mOsm/kg per %)
    drug_osmolarity = drug_loading_pct * 0.7
    
    # PEGylation contribution
    # PEG molecules add osmotic activity (~1-2 mOsm per 1% density)
    peg_osmolarity = peg_density_pct * 1.2
    
    # Encapsulation efficiency affects water content
    # Lower encapsulation = more water = slight increase in osmolarity
    encapsulation_correction = (100 - encapsulation_pct) * 0.3
    
    # Total osmolarity
    total_osmolarity = base_osmolarity + drug_osmolarity + peg_osmolarity + encapsulation_correction
    
    # ================================================================
    # SAFETY ASSESSMENT
    # ================================================================
    
    physiological_osmolarity = 300  # Reference
    safe_range_min = 250
    safe_range_max = 350
    warning_range_min = 200
    warning_range_max = 400
    
    # Determine status
    if safe_range_min <= total_osmolarity <= safe_range_max:
        status = "✅ Safe"
        safety_score = 100
        concern = "No osmotic concerns"
    elif warning_range_min <= total_osmolarity <= warning_range_max:
        status = "⚠️ Caution"
        safety_score = max(50, 100 - abs(total_osmolarity - physiological_osmolarity) / 2)
        if total_osmolarity < safe_range_min:
            concern = "Hypo-osmotic: May cause cell swelling"
        else:
            concern = "Hyper-osmotic: May cause hemolysis"
    else:
        status = "❌ Unsafe"
        safety_score = max(10, 50 - abs(total_osmolarity - physiological_osmolarity) / 5)
        if total_osmolarity < warning_range_min:
            concern = "Severely hypo-osmotic: Cell lysis/rupture likely"
        else:
            concern = "Severely hyper-osmotic: Severe hemolysis risk"
    
    # Calculate deviation from ideal
    deviation_from_ideal = abs(total_osmolarity - physiological_osmolarity)
    
    # Recommendations
    recommendations = []
    if total_osmolarity < safe_range_min:
        recommendations.append("🔧 Increase buffer/salt concentration")
        recommendations.append("🔧 Reduce PEGylation density")
    elif total_osmolarity > safe_range_max:
        recommendations.append("🔧 Reduce buffer/salt concentration")
        recommendations.append("🔧 Reduce drug loading")
        recommendations.append("🔧 Consider using water as solvent instead of buffer")
    
    return {
        "osmolarity_mosm_kg": round(total_osmolarity, 1),
        "physiological_reference": physiological_osmolarity,
        "safe_range": (safe_range_min, safe_range_max),
        "status": status,
        "safety_score": round(safety_score, 1),
        "concern": concern,
        "deviation_from_ideal": round(deviation_from_ideal, 1),
        "components_breakdown": {
            "base_material": round(base_osmolarity, 1),
            "drug_contribution": round(drug_osmolarity, 1),
            "peg_contribution": round(peg_osmolarity, 1),
            "encapsulation_correction": round(encapsulation_correction, 1),
        },
        "recommendations": recommendations,
        "hemolysis_risk": "Very Low" if total_osmolarity < 250 else 
                         "Low" if 250 <= total_osmolarity <= 350 else 
                         "Moderate" if 350 < total_osmolarity <= 400 else 
                         "High"
    }


def display_osmolarity_widget(design: Dict) -> None:
    """Display osmolarity calculation results in Streamlit UI"""
    
    result = calculate_osmolarity(design)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Osmolarity",
            f"{result['osmolarity_mosm_kg']} mOsm/kg",
            delta=f"{result['deviation_from_ideal']:+.1f} from ideal",
            help="Physiological: 270-310 mOsm/kg"
        )
    
    with col2:
        st.metric(
            "Safety Status",
            result['status'],
            help=result['concern']
        )
    
    with col3:
        st.metric(
            "Safety Score",
            f"{result['safety_score']:.0f}/100",
            help="Osmolarity-based toxicity risk"
        )
    
    # Detailed breakdown
    with st.expander("📊 Osmolarity Breakdown"):
        components = result['components_breakdown']
        st.write("""
        **Osmolarity Contributors:**
        """)
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"- Base material: {components['base_material']} mOsm/kg")
            st.write(f"- Drug: {components['drug_contribution']} mOsm/kg")
        with col2:
            st.write(f"- PEG coating: {components['peg_contribution']} mOsm/kg")
            st.write(f"- Encapsulation: {components['encapsulation_correction']} mOsm/kg")
        
        st.divider()
        
        if result['recommendations']:
            st.warning("**Recommendations:**")
            for rec in result['recommendations']:
                st.write(f"• {rec}")


if __name__ == "__main__":
    # Test osmolarity calculator
    test_design = {
        "Material": "Lipid NP",
        "Size": 100,
        "Encapsulation": 85,
        "Drug": 50,
        "PEG_Density": 50,
    }
    
    result = calculate_osmolarity(test_design)
    print(f"Osmolarity: {result['osmolarity_mosm_kg']} mOsm/kg")
    print(f"Status: {result['status']}")
    print(f"Safety Score: {result['safety_score']}")
