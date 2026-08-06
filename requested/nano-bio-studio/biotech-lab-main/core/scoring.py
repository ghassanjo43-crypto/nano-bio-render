# core/scoring.py
from __future__ import annotations

import streamlit as st
import numpy as np


def compute_impact(design: dict, weights: dict = None) -> dict:
    """Compute delivery (0-100), toxicity (0-10), cost (0-100).
    
    weights dict can override defaults:
    {
        'size': 0.18, 'charge': 0.14, 'encap': 0.18, 'pdi': 0.10,
        'hydro': 0.06, 'stability': 0.04, 'targeting': 0.08,
        'release': 0.04, 'surface_area': 0.04, 'hydrophobicity': 0.05,
        'crystallinity': 0.05, 'coating': 0.05
    }
    """

    d = design

    # ---- Delivery Score (0-100)
    # Size: optimal is 80-120nm
    if 80 <= d["Size"] <= 120:
        size_score = 100
    elif d["Size"] < 80:
        size_score = (d["Size"] / 80.0) * 100
    else:
        size_score = max(0, 100 - ((d["Size"] - 120) / 2))

    # Charge: optimal is -10 to +10 mV
    if abs(d["Charge"]) <= 10:
        charge_score = 100
    else:
        charge_score = max(0, 100 - ((abs(d["Charge"]) - 10) * 3))

    # Encapsulation: direct percentage
    encap_score = float(d["Encapsulation"])

    # Advanced properties (safe defaults if missing)
    pdi = float(d.get("PDI", 0.15))
    hyd_size = float(d.get("HydrodynamicSize", d["Size"] * 1.2))
    stability = float(d.get("Stability", 85))
    surface_area_val = d.get("SurfaceArea")
    surface_area = float(surface_area_val) if surface_area_val is not None else 250
    degradation_time = float(d.get("DegradationTime", 30))

    # Surface & Chemistry parameters
    hydrophobicity_val = d.get("Hydrophobicity")
    hydrophobicity = float(hydrophobicity_val) if hydrophobicity_val is not None else 1.5
    crystallinity_val = d.get("CrystallinityIndex")
    crystallinity = float(crystallinity_val) if crystallinity_val is not None else 65
    coating = d.get("SurfaceCoating", ["PEG (Stealth)"])
    if coating is None:
        coating = ["PEG (Stealth)"]
    coating_thickness_val = d.get("CoatingThickness")
    coating_thickness = float(coating_thickness_val) if coating_thickness_val is not None else 2.5
    functional_groups = d.get("FunctionalGroups", [])
    if functional_groups is None:
        functional_groups = []

    # Targeting parameters
    ligand = d.get("Ligand", "None")
    ligand_density = float(d.get("LigandDensity", 0))
    receptor_binding = float(d.get("ReceptorBinding", 100.0))
    release_predictability = float(d.get("ReleasePredictability", 85))

    # PDI score (lower is better)
    pdi_score = max(0, 100 - (pdi * 200))

    # Hydrodynamic/core ratio score (closer to ~1.15 is good)
    size_ratio = hyd_size / d["Size"] if d["Size"] else 1.0
    if 1.0 <= size_ratio <= 1.3:
        hydrodynamic_score = 100
    else:
        hydrodynamic_score = max(0, 100 - (abs(size_ratio - 1.15) * 50))

    # Targeting score: bonus for active targeting
    if ligand != "None":
        # Ligand density score (higher is better, optimal 50-80%)
        if 50 <= ligand_density <= 80:
            ligand_score = 100
        else:
            ligand_score = max(0, 100 - (abs(ligand_density - 65) * 2))
        
        # Receptor binding score (lower Kd = better binding, optimal <50nM)
        if receptor_binding < 50:
            binding_score = 100
        else:
            binding_score = max(0, 100 - (receptor_binding / 10))
        
        targeting_score = (ligand_score * 0.6 + binding_score * 0.4)
    else:
        targeting_score = 60  # Passive targeting baseline

    # Release predictability score
    release_score = float(release_predictability)

    # Surface Chemistry Scores
    # Surface Area score (optimal 200-400 nm²)
    if 200 <= surface_area <= 400:
        surface_area_score = 100
    else:
        surface_area_score = max(0, 100 - (abs(surface_area - 300) / 3))
    
    # Hydrophobicity score (optimal 0.5-2.5 LogP for PEGylated NPs)
    if 0.5 <= hydrophobicity <= 2.5:
        hydrophobicity_score = 100
    else:
        hydrophobicity_score = max(0, 100 - (abs(hydrophobicity - 1.5) * 20))
    
    # Crystallinity score (higher is better for stability, optimal 70-90%)
    if 70 <= crystallinity <= 90:
        crystallinity_score = 100
    else:
        crystallinity_score = max(0, 100 - (abs(crystallinity - 80) * 2))
    
    # Coating score (stealth coatings improve circulation)
    coating_bonus = 0
    if isinstance(coating, list):
        if "PEG (Stealth)" in coating:
            coating_bonus = 30  # Excellent for circulation
        if "Hyaluronic Acid" in coating:
            coating_bonus += 20  # Good for targeting
        if "Chitosan" in coating:
            coating_bonus += 15  # Mucoadhesive
        if "Albumin" in coating:
            coating_bonus += 10  # Biocompatible
    else:
        if coating == "PEG (Stealth)":
            coating_bonus = 30
    coating_score = min(100, 50 + coating_bonus)
    
    # Coating thickness score (optimal 2-5 nm for PEG)
    if 2 <= coating_thickness <= 5:
        thickness_score = 100
    elif coating_thickness > 0:
        thickness_score = max(0, 100 - (abs(coating_thickness - 3.5) * 15))
    else:
        thickness_score = 30
    
    # Functional groups score (improves biocompatibility)
    functional_score = 70  # Base score
    if isinstance(functional_groups, list):
        if "-COOH (Carboxyl)" in functional_groups:
            functional_score += 20  # Good for targeting
        if "-NH2 (Amino)" in functional_groups:
            functional_score += 15  # Electrostatic interactions
        if "-OH (Hydroxyl)" in functional_groups:
            functional_score += 10  # Hydrophilic
    functional_score = min(100, functional_score)

    # Weighted average delivery (updated with surface chemistry)
    # Default weights
    default_weights = {
        'size': 0.18, 'charge': 0.14, 'encap': 0.18, 'pdi': 0.10,
        'hydro': 0.06, 'stability': 0.04, 'targeting': 0.08,
        'release': 0.04, 'surface_area': 0.04, 'hydrophobicity': 0.05,
        'crystallinity': 0.05, 'coating': 0.05
    }
    
    # Override with custom weights if provided
    if weights:
        default_weights.update(weights)
    w = default_weights
    
    # Normalize weights to ensure they sum to 1.0
    total_weight = sum(w.values())
    if total_weight != 1.0:
        w = {k: v/total_weight for k, v in w.items()}
    
    delivery = (
        size_score * w['size']
        + charge_score * w['charge']
        + encap_score * w['encap']
        + pdi_score * w['pdi']
        + hydrodynamic_score * w['hydro']
        + stability * w['stability']
        + targeting_score * w['targeting']
        + release_score * w['release']
        + surface_area_score * w['surface_area']
        + hydrophobicity_score * w['hydrophobicity']
        + crystallinity_score * w['crystallinity']
        + coating_score * w['coating']
    )

    # ---- Toxicity (0-10)
    base_toxicity = min(
        10,
        (abs(d["Charge"]) / 10) + (max(0, abs(d["Size"] - 100)) / 50),
    )

    pdi_toxicity = pdi * 2
    degradation_toxicity = max(0, (degradation_time - 30) / 30)
    
    # Surface chemistry toxicity factors
    surface_toxicity = 0
    
    # Hydrophobicity toxicity (too hydrophobic = aggregation/toxicity)
    if hydrophobicity > 3.0:
        surface_toxicity += (hydrophobicity - 3.0) * 0.5  # Excess hydrophobicity
    if hydrophobicity < 0 and hydrophobicity > -2:
        surface_toxicity += 0.5  # Too hydrophilic may cause aggregation
    
    # Low crystallinity may indicate amorphous defects (toxicity risk)
    if crystallinity < 40:
        surface_toxicity += (40 - crystallinity) / 20
    
    # Coating protects against toxicity
    coating_toxicity_reduction = 0
    if isinstance(coating, list) and len(coating) > 0:
        if "PEG (Stealth)" in coating:
            coating_toxicity_reduction += 2
        if "Hyaluronic Acid" in coating:
            coating_toxicity_reduction += 1.5
        if "Albumin" in coating:
            coating_toxicity_reduction += 1
    
    surface_toxicity = max(0, surface_toxicity - coating_toxicity_reduction)
    
    # Targeting-related toxicity: improper targeting increases toxicity
    targeting_toxicity = 0
    if ligand != "None":
        # Off-target toxicity from poor ligand density or binding
        if ligand_density < 20 or ligand_density > 95:
            targeting_toxicity += 1  # Poor density = off-target effects
        if receptor_binding > 500:
            targeting_toxicity += 0.5  # Weak binding = poor specificity

    toxicity = min(10, base_toxicity + pdi_toxicity + degradation_toxicity + surface_toxicity + targeting_toxicity)

    # ---- Cost (0-100)
    base_cost = min(
        100,
        (100 - encap_score) * 0.8 + (d["Size"] / 4),
    )

    surface_area_cost = surface_area / 20
    pdi_cost = (0.2 - min(pdi, 0.2)) * 100
    degradation_cost = max(0, (degradation_time - 60) / 10)
    
    # Surface Chemistry costs
    coating_cost = 0
    if isinstance(coating, list):
        if "PEG (Stealth)" in coating:
            coating_cost += 25
        if "Hyaluronic Acid" in coating:
            coating_cost += 20
        if "Chitosan" in coating:
            coating_cost += 15
        if "Albumin" in coating:
            coating_cost += 18
    
    # Functional groups synthesis cost
    functional_cost = len(functional_groups) * 5 if functional_groups else 0
    
    # Coating thickness impacts manufacturing cost
    coating_thickness_cost = max(0, coating_thickness / 2) if coating_thickness > 0 else 0
    
    # Targeting cost: active targeting adds cost
    targeting_cost = 0
    if ligand != "None":
        # Ligand synthesis/conjugation cost
        ligand_cost_map = {
            "GalNAc": 20,
            "Folate": 15,
            "Transferrin": 30,
            "RGD Peptide": 25,
            "Anti-HER2": 40,
        }
        targeting_cost = ligand_cost_map.get(ligand, 20)

    cost = min(100, base_cost + surface_area_cost + pdi_cost + degradation_cost + targeting_cost + coating_cost + functional_cost + coating_thickness_cost)

    return {"Delivery": float(delivery), "Toxicity": float(toxicity), "Cost": float(cost)}


def get_recommendations(design: dict) -> list[str]:
    recommendations: list[str] = []

    if design["Size"] < 80:
        recommendations.append("🔴 **Increase size to 80–120nm** for better stability and circulation")
    elif design["Size"] > 150:
        recommendations.append("🔴 **Reduce size to 80–120nm** for better cellular uptake")

    if abs(design["Charge"]) > 15:
        recommendations.append("🟡 **Lower surface charge** to ±10mV for reduced toxicity")
    elif abs(design["Charge"]) > 10:
        recommendations.append("🟡 **Reduce charge** closer to neutral for optimal safety")

    if design["Encapsulation"] < 70:
        recommendations.append("🔴 **Improve encapsulation to >80%** for better drug delivery efficiency")
    elif design["Encapsulation"] < 85:
        recommendations.append("🟡 **Aim for >85% encapsulation** for optimal performance")

    # Surface Chemistry recommendations
    hydrophobicity = float(design.get("Hydrophobicity", 1.5))
    if hydrophobicity > 3.0:
        recommendations.append("🔴 **Reduce hydrophobicity (LogP <3.0)** to prevent aggregation and toxicity")
    elif hydrophobicity > 2.5:
        recommendations.append("🟡 **Lower hydrophobicity** for better aqueous stability")
    
    crystallinity = float(design.get("CrystallinityIndex", 65))
    if crystallinity < 50:
        recommendations.append("🔴 **Increase crystallinity to >60%** for better structural stability")
    elif crystallinity < 70:
        recommendations.append("🟡 **Improve crystallinity to 70-90%** for optimal performance")
    
    coating = design.get("SurfaceCoating", [])
    if not coating or (isinstance(coating, list) and "PEG (Stealth)" not in coating):
        recommendations.append("💡 **Add PEG coating** for enhanced circulation time and reduced opsonization")
    
    coating_thickness_val = design.get("CoatingThickness")
    coating_thickness = float(coating_thickness_val) if coating_thickness_val is not None else 2.5
    if coating_thickness and coating_thickness < 1.5:
        recommendations.append("🟡 **Increase coating thickness to 2-5nm** for better protection")
    elif coating_thickness and coating_thickness > 6:
        recommendations.append("🟡 **Reduce coating thickness** to <6nm to avoid reduced drug penetration")

    # Targeting recommendations
    if design.get("Ligand", "None") != "None":
        ligand_density = float(design.get("LigandDensity", 0))
        if ligand_density < 30:
            recommendations.append("🔴 **Increase ligand density to >30%** for effective targeting")
        elif ligand_density < 50:
            recommendations.append("🟡 **Increase ligand density to 50-80%** for optimal targeting efficiency")
        elif ligand_density > 95:
            recommendations.append("🟡 **Reduce ligand density to <90%** to avoid steric hindrance")
        
        receptor_binding = float(design.get("ReceptorBinding", 100.0))
        if receptor_binding > 500:
            recommendations.append("🟡 **Improve receptor binding affinity** (target Kd <50nM) for better specificity")
    else:
        recommendations.append("💡 **Consider active targeting** (ligand + receptor) to improve drug delivery specificity")
    
    release_pred = float(design.get("ReleasePredictability", 85))
    if release_pred < 70:
        recommendations.append("🔴 **Improve release predictability to >70%** for consistent drug delivery")
    elif release_pred < 85:
        recommendations.append("🟡 **Aim for >85% release predictability** for optimal performance")

    if not recommendations:
        recommendations.append("✅ **Excellent design!** All parameters are within optimal ranges")

    return recommendations


def validate_parameter(param: str, value: float, optimal_range: list[float]) -> str:
    lo, hi = optimal_range
    if lo <= value <= hi:
        return "✅"
    if abs(value - lo) < 20 or abs(value - hi) < 20:
        return "🟡"
    return "🔴"


def regulatory_checklist(design: dict) -> float:
    checklist = {
        "Size < 200nm": design["Size"] <= 200,
        "PDI < 0.3": float(design.get("PDI", 0.15)) < 0.3,
        "Charge within ±30mV": abs(design["Charge"]) <= 30,
        "Encapsulation > 70%": design["Encapsulation"] >= 70,
        "Stability > 80%": float(design.get("Stability", 85)) >= 80,
        "Material approved for medical use": design.get("Material") in ["Lipid NP", "PLGA"],
        "Degradation products characterized": float(design.get("DegradationTime", 30)) < 90,
        "Sterilization method defined": True,
    }

    passed = sum(bool(v) for v in checklist.values())
    total = len(checklist)
    return (passed / total) * 100.0


def overall_score_from_impact(impact: dict) -> float:
    """Convenience helper used by multiple tabs."""
    return float(
        np.clip(
            (impact["Delivery"] * 0.6)
            + ((10 - impact["Toxicity"]) * 3)
            + ((100 - impact["Cost"]) * 0.1),
            0,
            100,
        )
    )
