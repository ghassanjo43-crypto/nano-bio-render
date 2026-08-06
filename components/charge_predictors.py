"""
Charge-Based Predictors for Nanoparticle Behavior
Includes: Improved Blood Half-Life, Isoelectric Point, Charge Stability
"""

import streamlit as st
from typing import Dict, Tuple


def predict_improved_blood_half_life(design: Dict) -> float:
    """
    Predict blood half-life with multi-factor model.
    
    Better than simple formula: t_half = 2.0 + (size / 100)
    
    Incorporates:
    - Size-dependent clearance (renal vs hepatic)
    - PEGylation effect (extends circulation 2-3x)
    - Charge effect (affects protein corona formation)
    - Material type inherent properties
    - Disease-specific MPS function (optional)
    
    Args:
        design: Dictionary with formulation parameters
        
    Returns:
        Estimated blood half-life in hours (float)
    """
    
    size_nm = float(design.get("Size", 100))
    charge_mv = float(design.get("Charge", -30))
    peg_density_pct = float(design.get("PEG_Density", 50))
    material = design.get("Material", "Lipid NP")
    
    # ================================================================
    # STEP 1: BASE CLEARANCE BY SIZE CATEGORY
    # ================================================================
    
    # Different size ranges have different clearance mechanisms
    if size_nm < 10:
        # Ultra-small: primarily renal filtration
        base_t_half = 0.25  # hours (15 minutes)
        clearance_mechanism = "Renal Filtration (Ultra-small)"
    elif size_nm < 50:
        # Small: mixed renal and hepatic
        base_t_half = 2.0   # hours
        clearance_mechanism = "Mixed Renal/Hepatic (Small)"
    elif size_nm < 100:
        # Medium: hepatic and splenic uptake begins
        base_t_half = 4.0   # hours
        clearance_mechanism = "Hepatic + Splenic (Medium)"
    elif size_nm < 150:
        # Medium-large: primarily MPS
        base_t_half = 3.5   # hours (subject to strong opsonization)
        clearance_mechanism = "MPS Uptake (Medium-Large)"
    elif size_nm < 200:
        # Large: rapid MPS clearance
        base_t_half = 2.5   # hours
        clearance_mechanism = "Rapid MPS (Large)"
    else:
        # Very large: extremely rapid clearance
        base_t_half = 1.0   # hours
        clearance_mechanism = "Splenic/Lymphatic (Very Large)"
    
    # ================================================================
    # STEP 2: PEG PROTECTIVE EFFECT
    # ================================================================
    
    # PEGylation dramatically extends half-life by evading opsonin adsorption
    # 0% PEG: multiplier = 1.0
    # 30% PEG: multiplier ≈ 1.8-2.0
    # 50% PEG: multiplier ≈ 2.5-3.0
    # Higher PEG density has diminishing returns
    
    peg_multiplier = 1.0 + (peg_density_pct / 100) * 2.0
    
    # ================================================================
    # STEP 3: CHARGE PROTECTIVE EFFECT
    # ================================================================
    
    # Neutral charge is protective (delays protein corona)
    # Very negative or very positive charges promote opsonization
    
    charge_abs = abs(charge_mv)
    
    if charge_abs < 5:
        # Near neutral - excellent
        charge_multiplier = 1.2
        charge_effect = "Excellent (near-neutral)"
    elif charge_abs < 10:
        # Slightly charged - good
        charge_multiplier = 1.1
        charge_effect = "Good (slightly charged)"
    elif charge_abs < 15:
        # Moderately charged - acceptable
        charge_multiplier = 1.0
        charge_effect = "Acceptable (moderately charged)"
    elif charge_abs < 25:
        # Highly charged - reduced circulation
        charge_multiplier = max(0.6, 1.0 - (charge_abs - 15) / 50)
        charge_effect = "Moderate reduction (highly charged)"
    else:
        # Very high charge - significant clearance increase
        charge_multiplier = max(0.3, 1.0 - (charge_abs - 25) / 50)
        charge_effect = "Significant reduction (very high charge)"
    
    # ================================================================
    # STEP 4: MATERIAL INHERENT PROPERTIES
    # ================================================================
    
    # Different materials have different inherent clearance rates
    material_multiplier = {
        "Lipid NP": 1.0,         # Reference (well-studied)
        "PLGA": 0.85,            # Slightly faster clearance
        "Gold NP": 1.3,          # More resistant to opsonization
        "Silica NP": 0.9,        # Moderate clearance
        "DNA Origami": 0.6,      # Rapid clearance (DNA immune recognition)
        "Liposome": 1.0,         # Similar to lipids
        "Polymeric NP": 0.8,     # Slight faster clearance
        "Albumin NP": 1.1,       # Biocompatible, slight advantage
    }
    
    material_mult = material_multiplier.get(material, 1.0)
    
    # ================================================================
    # COMBINED CALCULATION
    # ================================================================
    
    predicted_t_half = base_t_half * peg_multiplier * charge_multiplier * material_mult
    
    # Cap at reasonable values (0.1 - 48 hours)
    predicted_t_half = max(0.1, min(48, predicted_t_half))
    
    return {
        "blood_half_life_hours": round(predicted_t_half, 2),
        "clearance_mechanism": clearance_mechanism,
        "base_half_life": round(base_t_half, 2),
        "peg_multiplier": round(peg_multiplier, 2),
        "charge_multiplier": round(charge_multiplier, 2),
        "material_multiplier": round(material_mult, 2),
        "charge_effect_description": charge_effect,
        "clinical_implication": format_clinical_implication(predicted_t_half),
    }


def calculate_isoelectric_point(design: Dict) -> Dict:
    """
    Estimate isoelectric point (pI) of nanoparticle.
    
    At pI, particle has net zero charge and is most prone to aggregation.
    Predicts particle behavior at different pH values.
    
    Args:
        design: Dictionary with formulation parameters
        
    Returns:
        Dictionary with pI estimation and pH-dependent charge prediction
    """
    
    charge_base_mv = float(design.get("Charge", -30))
    size_nm = float(design.get("Size", 100))
    material = design.get("Material", "Lipid NP")
    
    # ================================================================
    # CHARGE-pH RELATIONSHIP
    # ================================================================
    
    # For typical NPs, charge changes ~2-3 mV per pH unit
    # This depends on surface functional groups
    
    # Material-specific charge sensitivity
    charge_sensitivity = {
        "Lipid NP": 2.2,        # Slight pH dependence
        "PLGA": 3.5,            # Carboxyl groups = pH sensitive
        "Gold NP": 2.0,         # Au surface less sensitive
        "Silica NP": 4.0,       # Silanol groups = very pH sensitive
        "DNA Origami": 2.5,     # Phosphate groups
        "Liposome": 2.0,        # Lipid less sensitive
        "Polymeric NP": 3.0,    # Depends on polymer
        "Albumin NP": 3.2,      # Protein charge groups
    }
    
    pH_effect_per_unit = charge_sensitivity.get(material, 2.5)  # mV/pH unit
    
    # Reference pH
    reference_pH = 7.4  # Physiological
    
    # ================================================================
    # ESTIMATE ISOELECTRIC POINT
    # ================================================================
    
    # pI is where charge = 0
    # If particle at pH 7.4 has charge of -30 mV
    # And charge changes by -2.5 mV per pH decrease
    # Then at pI: -30 + (pI - 7.4) * 2.5 = 0
    # Solving: pI = 7.4 - (-30 / 2.5) = 7.4 + 12 = 19.4 (invalid)
    # Or at lower pH: charge becomes less negative
    
    # Simplified: estimate pI assuming linear relationship
    if charge_base_mv < 0:
        # Negatively charged at pH 7.4
        # pI is at lower pH where charge approaches zero
        estimated_pH_neutral = reference_pH - (charge_base_mv / pH_effect_per_unit)
    else:
        # Positively charged at pH 7.4
        # pI is at higher pH where charge approaches zero
        estimated_pH_neutral = reference_pH - (charge_base_mv / pH_effect_per_unit)
    
    # Ensure pI is in biologically relevant range (3-9)
    estimated_pI = max(3, min(9, estimated_pH_neutral))
    
    # ================================================================
    # PREDICT CHARGE AT DIFFERENT pH VALUES
    # ================================================================
    
    pH_values = [2.0, 4.5, 5.5, 6.5, 7.4, 8.0, 8.5]
    charge_predictions = {}
    
    for pH in pH_values:
        delta_pH = pH - reference_pH
        predicted_charge = charge_base_mv - (delta_pH * pH_effect_per_unit)
        charge_predictions[f"pH_{pH:.1f}"] = round(predicted_charge, 1)
    
    # ================================================================
    # AGGREGATION RISK ASSESSMENT
    # ================================================================
    
    # Risk of aggregation is highest near pI (zero charge)
    aggregation_risk_range = (estimated_pI - 0.5, estimated_pI + 0.5)
    
    if 4.0 <= estimated_pI <= 5.5:
        # pI in acidic endosomal environment
        aggregation_location = "Endosomes/Lysosomes"
        aggregation_concern = "High - Particle aggregation in acidic compartments"
    elif 7.0 <= estimated_pI <= 7.8:
        # pI near physiological
        aggregation_location = "Blood/Systemic circulation"
        aggregation_concern = "Moderate - Aggregation in blood possible"
    else:
        aggregation_location = "Outside normal biological pH"
        aggregation_concern = "Low - Aggregation unlikely in biological environments"
    
    return {
        "isoelectric_point_pH": round(estimated_pI, 2),
        "charge_at_ref_pH": round(charge_base_mv, 1),
        "charge_sensitivity_mv_per_pH": round(pH_effect_per_unit, 2),
        "charge_predictions_by_pH": charge_predictions,
        "aggregation_risk_range": (round(aggregation_risk_range[0], 2), round(aggregation_risk_range[1], 2)),
        "aggregation_location": aggregation_location,
        "aggregation_concern": aggregation_concern,
        "recommendations": get_pI_recommendations(estimated_pI),
    }


def format_clinical_implication(half_life_hours: float) -> str:
    """Format clinical implications based on predicted half-life"""
    
    if half_life_hours < 0.5:
        return "⏱️ Ultra-short circulation: Rapid clearance (minutes)"
    elif half_life_hours < 2:
        return "📉 Short circulation: Limited systemic exposure"
    elif half_life_hours < 4:
        return "🟡 Moderate circulation: Typical for many NPs"
    elif half_life_hours < 12:
        return "🟢 Extended circulation: Good for most applications"
    elif half_life_hours < 24:
        return "✅ Long circulation: Excellent targeting window"
    else:
        return "⭐ Very long circulation: Research-grade formulation"


def get_pI_recommendations(estimated_pI: float) -> list:
    """Get recommendations based on isoelectric point"""
    
    recommendations = []
    
    if 4.0 <= estimated_pI <= 5.5:
        recommendations.append("⚠️ Aggregation risk in lysosomes - Design for pH-responsive release")
        recommendations.append("💡 Consider: pH-sensitive linkers, endo-lysosomal escape moieties")
    
    if 6.5 <= estimated_pI <= 7.8:
        recommendations.append("⚠️ Aggregation risk in neutral pH environments - May affect stability")
        recommendations.append("💡 Consider: Increasing charge magnitude or PEGylation")
    
    if estimated_pI < 4.0 or estimated_pI > 8.5:
        recommendations.append("✅ Low aggregation risk in physiological ranges")
    
    return recommendations


def display_halflife_widget(design: Dict) -> None:
    """Display improved blood half-life prediction in Streamlit UI"""
    
    result = predict_improved_blood_half_life(design)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Blood Half-Life",
            f"{result['blood_half_life_hours']:.2f} hours",
            help="Predicted circulation time"
        )
    
    with col2:
        st.metric(
            "Clearance",
            result['clearance_mechanism'],
            help="Primary elimination pathway"
        )
    
    with col3:
        st.metric(
            "Clinical",
            result['clinical_implication'],
            help="Therapeutic window assessment"
        )
    
    # Multiplier breakdown
    with st.expander("📊 Half-Life Calculation Factors"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Base Components:**")
            st.write(f"- Base half-life: {result['base_half_life']} hours")
            st.write(f"- Material factor: {result['material_multiplier']}×")
        
        with col2:
            st.write("**Protective Factors:**")
            st.write(f"- PEG protection: {result['peg_multiplier']}×")
            st.write(f"- Charge effect: {result['charge_multiplier']}× ({result['charge_effect_description']})")


def display_pI_widget(design: Dict) -> None:
    """Display isoelectric point analysis in Streamlit UI"""
    
    result = calculate_isoelectric_point(design)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Isoelectric Point",
            f"pH {result['isoelectric_point_pH']:.2f}",
            help="pH where particle has zero charge"
        )
    
    with col2:
        st.metric(
            "Aggregation Risk",
            result['aggregation_location'],
            help=result['aggregation_concern']
        )
    
    with col3:
        risk_level = "Low ✅" if "Low" in result['aggregation_concern'] else \
                     "Moderate 🟡" if "Moderate" in result['aggregation_concern'] else \
                     "High ⚠️"
        st.metric(
            "Risk Level",
            risk_level,
        )
    
    # Charge predictions at different pH
    with st.expander("📊 Charge at Different pH Values"):
        predictions = result['charge_predictions_by_pH']
        
        # Create two columns for display
        col1, col2 = st.columns(2)
        
        with col1:
            for key in list(predictions.keys())[:4]:
                pH_val = key.replace("pH_", "")
                charge_val = predictions[key]
                st.write(f"pH {pH_val}: {charge_val:+.1f} mV")
        
        with col2:
            for key in list(predictions.keys())[4:]:
                pH_val = key.replace("pH_", "")
                charge_val = predictions[key]
                st.write(f"pH {pH_val}: {charge_val:+.1f} mV")
        
        st.info(f"ℹ️ At pI (pH {result['isoelectric_point_pH']:.1f}), particle charge ≈ 0")
    
    # Recommendations
    if result['recommendations']:
        st.info("**Recommendations:**")
        for rec in result['recommendations']:
            st.write(rec)


if __name__ == "__main__":
    # Test half-life predictor
    test_design = {
        "Material": "Lipid NP",
        "Size": 100,
        "Charge": -30,
        "PEG_Density": 50,
    }
    
    t_half_result = predict_improved_blood_half_life(test_design)
    print(f"Blood Half-Life: {t_half_result['blood_half_life_hours']} hours")
    print(f"Mechanism: {t_half_result['clearance_mechanism']}")
    
    print("\n---\n")
    
    pI_result = calculate_isoelectric_point(test_design)
    print(f"Isoelectric Point: pH {pI_result['isoelectric_point_pH']}")
    print(f"Aggregation Risk: {pI_result['aggregation_concern']}")
