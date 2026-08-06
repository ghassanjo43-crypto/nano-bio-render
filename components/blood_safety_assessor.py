"""
Blood Safety Assessor - Hemolytic Activity Prediction
Predicts red blood cell (RBC) lysis risk and blood compatibility
"""

import streamlit as st
from typing import Dict


def calculate_hemolysis_risk(design: Dict) -> Dict:
    """
    Predict hemolytic potential of nanoparticle formulation.
    
    Hemolysis (RBC lysis) is caused by:
    1. High positive charge (membrane disruption)
    2. Ultra-small particles (can penetrate RBC membrane)
    3. High hydrophobicity (lipophilic interaction with membrane)
    4. Surfactant-like activity
    
    Args:
        design: Dictionary with formulation parameters
        
    Returns:
        Dictionary with hemolysis assessment and safety rating
    """
    
    # Extract parameters
    charge_mv = float(design.get("Charge", -30))
    size_nm = float(design.get("Size", 100))
    hydrophobicity = float(design.get("Hydrophobicity") or 1.5)
    encapsulation_pct = float(design.get("Encapsulation", 85))
    peg_density_pct = float(design.get("PEG_Density", 50))
    material = design.get("Material", "Lipid NP")
    
    # ================================================================
    # HEMOLYSIS RISK FACTORS
    # ================================================================
    
    hemolysis_score = 0
    drivers = []
    
    # ---- FACTOR 1: CHARGE EFFECT ----
    # Positive charges disrupt RBC membranes
    # Negative charges are generally safer (repelled by RBC surface)
    
    if charge_mv > 0:
        if charge_mv > 25:
            charge_risk = 50
            drivers.append(f"High positive charge: {charge_mv} mV")
        elif charge_mv > 15:
            charge_risk = 30
            drivers.append(f"Moderate positive charge: {charge_mv} mV")
        elif charge_mv > 5:
            charge_risk = 15
            drivers.append(f"Slight positive charge: {charge_mv} mV")
        else:
            charge_risk = 5
    else:
        # Negative charges protective
        if charge_mv < -40:
            charge_risk = 10
            drivers.append("Very negative (protective)")
        else:
            charge_risk = 0
    
    hemolysis_score += charge_risk
    
    # ---- FACTOR 2: SIZE EFFECT ----
    # Ultra-small particles can penetrate RBC membranes
    # Small NPs can also increase surface reactivity
    
    if size_nm < 30:
        size_risk = 40
        drivers.append(f"Ultra-small size: {size_nm} nm (membrane penetration)")
    elif size_nm < 50:
        size_risk = 25
        drivers.append(f"Small size: {size_nm} nm (increased reactivity)")
    elif size_nm < 80:
        size_risk = 10
        drivers.append(f"Small-medium size: {size_nm} nm")
    else:
        size_risk = 0
    
    hemolysis_score += size_risk
    
    # ---- FACTOR 3: HYDROPHOBICITY EFFECT ----
    # Lipophilic particles interact with RBC lipid bilayer
    # Optimal: 0.5-2.5 LogP
    
    if hydrophobicity < 0:
        hydro_risk = 0  # Very hydrophilic (safe)
    elif hydrophobicity < 0.5:
        hydro_risk = 5  # Hydrophilic
    elif hydrophobicity < 1.0:
        hydro_risk = 0  # Optimal range start
    elif hydrophobicity < 2.5:
        hydro_risk = 0  # Optimal range
    elif hydrophobicity < 3.5:
        hydro_risk = 15
        drivers.append(f"High hydrophobicity: {hydrophobicity:.1f} LogP")
    else:
        hydro_risk = 35
        drivers.append(f"Very high hydrophobicity: {hydrophobicity:.1f} LogP")
    
    hemolysis_score += hydro_risk
    
    # ---- FACTOR 4: PEG PROTECTIVE EFFECT ----
    # PEGylation reduces surface reactivity and charge exposure
    
    peg_protection = peg_density_pct * 0.3  # Each % PEG reduces risk by 0.3 points
    hemolysis_score = max(0, hemolysis_score - peg_protection)
    
    # ---- FACTOR 5: ENCAPSULATION EFFECT ----
    # Higher encapsulation = less free reactive surface
    
    encapsulation_protection = (encapsulation_pct - 50) * 0.2
    hemolysis_score = max(0, hemolysis_score - encapsulation_protection)
    
    # ---- FACTOR 6: MATERIAL EFFECT ----
    # Some materials inherently more hemolytic
    
    material_base_risk = {
        "Lipid NP": 0,          # Well-tolerated
        "PLGA": 5,              # Slight risk from degradation products
        "Gold NP": 15,          # Metal surface reactivity
        "Silica NP": 20,        # Surface hydroxyl groups
        "DNA Origami": 10,      # Phosphate groups
        "Liposome": 0,          # Similar to lipid NP
        "Polymeric NP": 10,     # Polymer surface effects
        "Albumin NP": 0,        # Biocompatible protein
    }
    
    material_risk = material_base_risk.get(material, 5)
    hemolysis_score += material_risk
    
    # Final hemolysis score (0-100)
    final_hemolysis_score = min(100, max(0, hemolysis_score))
    
    # ================================================================
    # SAFETY CLASSIFICATION
    # ================================================================
    
    if final_hemolysis_score < 20:
        safety_level = "✅ Very Low Risk"
        hemolysis_status = "Safe - Expected minimal hemolysis"
        safe_for_iv = True
    elif final_hemolysis_score < 35:
        safety_level = "🟢 Low Risk"
        hemolysis_status = "Generally safe - Monitor in studies"
        safe_for_iv = True
    elif final_hemolysis_score < 50:
        safety_level = "🟡 Moderate Risk"
        hemolysis_status = "Use with caution - Further testing recommended"
        safe_for_iv = False
    elif final_hemolysis_score < 75:
        safety_level = "🔴 High Risk"
        hemolysis_status = "NOT recommended for IV delivery"
        safe_for_iv = False
    else:
        safety_level = "🔴❌ Very High Risk"
        hemolysis_status = "Unacceptable - High hemolysis probability"
        safe_for_iv = False
    
    # ================================================================
    # RECOMMENDATIONS
    # ================================================================
    
    recommendations = []
    
    if charge_mv > 15:
        recommendations.append("🔧 Neutralize charge (target ±10 mV or less)")
        recommendations.append("🔧 Consider negative charge instead of positive")
    
    if size_nm < 50:
        recommendations.append(f"🔧 Increase particle size (current: {size_nm} nm)")
    
    if hydrophobicity > 2.5:
        recommendations.append("🔧 Reduce hydrophobicity (add hydrophilic coatings)")
    
    if peg_density_pct < 30:
        recommendations.append(f"🔧 Increase PEGylation (current: {peg_density_pct}%)")
    
    if encapsulation_pct < 70:
        recommendations.append(f"🔧 Improve encapsulation efficiency (current: {encapsulation_pct}%)")
    
    if not recommendations and final_hemolysis_score > 30:
        recommendations.append("ℹ️ Consider alternative materials or formulation approaches")
    
    return {
        "hemolysis_score": round(final_hemolysis_score, 1),      # 0-100 (higher = worse)
        "safety_level": safety_level,
        "status_description": hemolysis_status,
        "safe_for_iv_delivery": safe_for_iv,
        "risk_factors": {
            "charge_contribution": charge_risk,
            "size_contribution": size_risk,
            "hydrophobicity_contribution": hydro_risk,
            "material_contribution": material_risk,
            "peg_protection": round(-peg_protection, 1),  # Negative (protective)
            "encapsulation_protection": round(-encapsulation_protection, 1),
        },
        "primary_drivers": drivers,
        "recommendations": recommendations,
    }


def display_hemolysis_widget(design: Dict) -> None:
    """Display hemolysis risk assessment in Streamlit UI"""
    
    result = calculate_hemolysis_risk(design)
    
    # Main metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        score_color = "normal" if result['hemolysis_score'] < 35 else "inverse" if result['hemolysis_score'] < 50 else "off"
        st.metric(
            "Hemolysis Score",
            f"{result['hemolysis_score']:.0f}/100",
            delta="Higher = More Hemolytic",
            help="Predicted RBC lysis risk"
        )
    
    with col2:
        st.metric(
            "Safety Level",
            result['safety_level'],
            help=result['status_description']
        )
    
    with col3:
        iv_status = "✅ Suitable" if result['safe_for_iv_delivery'] else "❌ Not Suitable"
        st.metric(
            "IV Delivery",
            iv_status,
            help="Blood compatibility assessment"
        )
    
    # Risk factors breakdown
    with st.expander("📊 Risk Factors Breakdown"):
        factors = result['risk_factors']
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Contributing Factors:**")
            for factor, value in factors.items():
                if factor.endswith("_protection"):
                    label = factor.replace("_", " ").title()
                    st.write(f"- {label}: {value:.1f} (protective)")
                else:
                    label = factor.replace("_", " ").title()
                    if value > 0:
                        st.write(f"- {label}: +{value:.0f}")
        
        with col2:
            if result['primary_drivers']:
                st.write("**Primary Risk Drivers:**")
                for driver in result['primary_drivers']:
                    st.write(f"⚠️ {driver}")
    
    # Recommendations
    if result['recommendations']:
        st.info("**Recommendations to Reduce Hemolysis Risk:**")
        for i, rec in enumerate(result['recommendations'], 1):
            st.write(f"{i}. {rec}")


if __name__ == "__main__":
    # Test hemolysis calculator
    test_design = {
        "Material": "Lipid NP",
        "Size": 100,
        "Charge": -30,
        "Hydrophobicity": 1.5,
        "Encapsulation": 85,
        "PEG_Density": 50,
    }
    
    result = calculate_hemolysis_risk(test_design)
    print(f"Hemolysis Score: {result['hemolysis_score']}")
    print(f"Safety Level: {result['safety_level']}")
    print(f"Safe for IV: {result['safe_for_iv_delivery']}")
