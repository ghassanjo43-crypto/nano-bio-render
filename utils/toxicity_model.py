"""
Toxicity and Safety Assessment Module
Heuristic risk scoring for nanoparticle formulations
"""

import numpy as np
from typing import Dict, Tuple

def calculate_size_risk(size: float) -> Tuple[float, str]:
    """
    Calculate risk score based on nanoparticle size
    
    Parameters:
    -----------
    size : float
        Nanoparticle diameter (nm)
    
    Returns:
    --------
    score : float
        Risk score (0-10, lower is better)
    explanation : str
        Risk explanation
    """
    
    if size < 5:
        return 7.0, "Very small particles (<5 nm) may be rapidly cleared by kidneys or show enhanced tissue penetration with potential toxicity"
    elif 5 <= size < 20:
        return 4.0, "Small particles (5-20 nm) - Good for renal clearance but may cross biological barriers"
    elif 20 <= size < 100:
        return 2.0, "Optimal size range (20-100 nm) for EPR effect and tumor accumulation"
    elif 100 <= size < 200:
        return 3.0, "Medium particles (100-200 nm) - Good for EPR but may face clearance by RES"
    elif 200 <= size < 500:
        return 6.0, "Large particles (200-500 nm) - Rapid clearance by spleen and liver macrophages"
    else:
        return 9.0, "Very large particles (>500 nm) - High risk of filtration, embolism, and rapid RES clearance"

def calculate_charge_risk(charge: float, size: float) -> Tuple[float, str]:
    """
    Calculate risk score based on surface charge
    
    Parameters:
    -----------
    charge : float
        Zeta potential (mV)
    size : float
        Nanoparticle diameter (nm)
    
    Returns:
    --------
    score : float
        Risk score (0-10)
    explanation : str
        Risk explanation
    """
    
    if charge > 30:
        return 8.0, "Highly positive charge (>+30 mV) - High risk: hemolysis, platelet activation, non-specific protein binding"
    elif charge > 10:
        return 5.0, "Positive charge (+10 to +30 mV) - Moderate risk: enhanced cell uptake but potential membrane disruption"
    elif -10 <= charge <= 10:
        return 2.0, "Near-neutral charge (-10 to +10 mV) - Low toxicity but may have stability issues"
    elif -30 <= charge < -10:
        return 3.0, "Negative charge (-10 to -30 mV) - Generally safe, good stability, reduced non-specific uptake"
    else:
        return 6.0, "Highly negative charge (<-30 mV) - Potential for rapid clearance and complement activation"

def calculate_dose_risk(dose: float, size: float) -> Tuple[float, str]:
    """
    Calculate risk score based on dose
    
    Parameters:
    -----------
    dose : float
        Dose (mg/kg)
    size : float
        Particle size (nm)
    
    Returns:
    --------
    score : float
        Risk score (0-10)
    explanation : str
        Risk explanation
    """
    
    # Adjust threshold based on size - smaller particles more concerning at high dose
    if size < 50:
        threshold_low, threshold_med, threshold_high = 1.0, 5.0, 15.0
    else:
        threshold_low, threshold_med, threshold_high = 2.0, 10.0, 30.0
    
    if dose < threshold_low:
        return 2.0, f"Low dose (<{threshold_low} mg/kg) - Minimal systemic exposure risk"
    elif dose < threshold_med:
        return 4.0, f"Moderate dose ({threshold_low}-{threshold_med} mg/kg) - Monitor for accumulation"
    elif dose < threshold_high:
        return 6.0, f"High dose ({threshold_med}-{threshold_high} mg/kg) - Potential for organ accumulation and toxicity"
    else:
        return 9.0, f"Very high dose (>{threshold_high} mg/kg) - High risk of acute toxicity and organ damage"

def calculate_pdi_risk(pdi: float) -> Tuple[float, str]:
    """
    Calculate risk score based on polydispersity index
    
    Parameters:
    -----------
    pdi : float
        Polydispersity index (0-1)
    
    Returns:
    --------
    score : float
        Risk score (0-10)
    explanation : str
        Risk explanation
    """
    
    if pdi < 0.1:
        return 1.0, "Monodisperse (PDI <0.1) - Highly uniform, predictable behavior"
    elif pdi < 0.2:
        return 2.0, "Low polydispersity (PDI 0.1-0.2) - Acceptable uniformity for clinical use"
    elif pdi < 0.3:
        return 4.0, "Moderate polydispersity (PDI 0.2-0.3) - Variable biodistribution possible"
    elif pdi < 0.5:
        return 7.0, "High polydispersity (PDI 0.3-0.5) - Inconsistent behavior, batch variability"
    else:
        return 9.0, "Very high polydispersity (PDI >0.5) - Unacceptable heterogeneity, unpredictable effects"

def calculate_ligand_risk(ligand: str, charge: float) -> Tuple[float, str]:
    """
    Calculate risk score based on surface ligand
    
    Parameters:
    -----------
    ligand : str
        Surface ligand type
    charge : float
        Surface charge (mV)
    
    Returns:
    --------
    score : float
        Risk score (0-10)
    explanation : str
        Risk explanation
    """
    
    ligand_lower = ligand.lower()
    
    if "peg" in ligand_lower:
        if "peg2000" in ligand_lower or "peg 2000" in ligand_lower:
            return 1.0, "PEG2000 - Optimal stealth effect, clinically validated, minimal immunogenicity"
        else:
            return 2.0, "PEG coating - Good stealth effect, reduced protein binding and RES uptake"
    
    elif "antibody" in ligand_lower or "mab" in ligand_lower:
        return 4.0, "Antibody targeting - Potential immunogenicity, but highly specific targeting"
    
    elif "peptide" in ligand_lower or "rgd" in ligand_lower:
        return 3.0, "Peptide ligand - Generally safe, specific targeting with low immunogenicity"
    
    elif "folate" in ligand_lower or "transferrin" in ligand_lower:
        return 2.0, "Small molecule targeting - Safe, well-tolerated, specific binding"
    
    elif "cholesterol" in ligand_lower:
        return 3.0, "Cholesterol - Stabilizes lipid formulations but may affect circulation time"
    
    elif "hyaluronic" in ligand_lower or "ha" in ligand_lower:
        return 2.0, "Hyaluronic acid - Biocompatible, biodegradable, CD44 targeting"
    
    elif "none" in ligand_lower or not ligand:
        if abs(charge) < 10:
            return 6.0, "No ligand + neutral charge - Poor stability and rapid aggregation risk"
        else:
            return 5.0, "No ligand - May lack stealth effect, rapid clearance by RES"
    
    else:
        return 4.0, "Custom ligand - Assess immunogenicity and toxicity separately"

def calculate_payload_risk(payload: str, loading: float) -> Tuple[float, str]:
    """
    Calculate risk score based on payload type and loading
    
    Parameters:
    -----------
    payload : str
        Payload type
    loading : float
        Payload loading (% w/w)
    
    Returns:
    --------
    score : float
        Risk score (0-10)
    explanation : str
        Risk explanation
    """
    
    payload_lower = payload.lower()
    
    # Base risk by payload type
    if "mrna" in payload_lower:
        base_risk = 2.0
        explanation = "mRNA - Generally safe, transient expression, clinically validated"
    
    elif "sirna" in payload_lower:
        base_risk = 3.0
        explanation = "siRNA - Safe profile, specific gene silencing, potential off-targets"
    
    elif "dna" in payload_lower or "plasmid" in payload_lower:
        base_risk = 4.0
        explanation = "DNA/plasmid - Risk of genomic integration, longer expression"
    
    elif "crispr" in payload_lower or "cas" in payload_lower:
        base_risk = 5.0
        explanation = "CRISPR-Cas - Powerful but requires careful delivery, off-target concerns"
    
    elif "small molecule" in payload_lower or "drug" in payload_lower:
        base_risk = 3.0
        explanation = "Small molecule drug - Toxicity depends on specific drug, controlled release beneficial"
    
    elif "protein" in payload_lower or "peptide" in payload_lower:
        base_risk = 3.0
        explanation = "Protein/peptide - Generally safe but may trigger immune response"
    
    elif "antibody" in payload_lower:
        base_risk = 4.0
        explanation = "Antibody - Potential immunogenicity and off-target binding"
    
    elif "imaging" in payload_lower:
        base_risk = 2.0
        explanation = "Imaging agent - Diagnostic use, minimal therapeutic risk"
    
    elif "none" in payload_lower:
        base_risk = 1.0
        explanation = "No payload - Carrier only, minimal payload-related risk"
    
    else:
        base_risk = 4.0
        explanation = "Custom payload - Requires specific toxicity assessment"
    
    # Adjust based on loading
    if loading > 80:
        loading_penalty = 2.0
        explanation += " | Very high loading (>80%) - structural instability risk"
    elif loading > 50:
        loading_penalty = 1.0
        explanation += " | High loading - monitor stability"
    elif loading < 5:
        loading_penalty = 0.5
        explanation += " | Low loading - may require higher particle dose"
    else:
        loading_penalty = 0
    
    return min(10, base_risk + loading_penalty), explanation

def calculate_material_risk(material: str, size: float) -> Tuple[float, str]:
    """
    Calculate risk score based on nanoparticle material
    
    Parameters:
    -----------
    material : str
        Nanoparticle material type
    size : float
        Particle size (nm)
    
    Returns:
    --------
    score : float
        Risk score (0-10)
    explanation : str
        Risk explanation
    """
    
    material_lower = material.lower()
    
    if "lipid" in material_lower or "liposome" in material_lower:
        return 2.0, "Lipid-based - Biocompatible, biodegradable, clinically established"
    
    elif "plga" in material_lower or "polymer" in material_lower:
        return 3.0, "Polymer (PLGA) - FDA-approved, biodegradable, acidic degradation products"
    
    elif "gold" in material_lower or "aunp" in material_lower:
        if size < 10:
            return 4.0, "Gold NP - Generally safe but small particles may accumulate in organs"
        else:
            return 5.0, "Gold NP - Non-biodegradable, potential for long-term accumulation"
    
    elif "silica" in material_lower or "msn" in material_lower:
        return 5.0, "Silica - Concerns about long-term clearance and potential pulmonary toxicity"
    
    elif "quantum dot" in material_lower or "qd" in material_lower:
        return 7.0, "Quantum Dot - Contains heavy metals (Cd, Se), toxicity concerns, limited clinical use"
    
    elif "carbon nanotube" in material_lower or "cnt" in material_lower:
        return 7.0, "Carbon Nanotube - Biopersistence, potential for asbestos-like effects, aggregation"
    
    elif "dendrimer" in material_lower:
        return 4.0, "Dendrimer - Cationic dendrimers may be toxic, requires surface modification"
    
    elif "mof" in material_lower or "metal-organic" in material_lower:
        return 5.0, "Metal-Organic Framework - Newer platform, stability in biological fluids needs validation"
    
    elif "exosome" in material_lower:
        return 3.0, "Exosome - Natural vesicle, excellent biocompatibility, standardization challenges"
    
    else:
        return 5.0, "Custom material - Requires comprehensive toxicity assessment"

def calculate_overall_safety_score(design: Dict) -> Dict:
    """
    Calculate comprehensive safety assessment
    
    Parameters:
    -----------
    design : dict
        Nanoparticle design parameters
    
    Returns:
    --------
    safety_assessment : dict
        Complete safety assessment with scores and recommendations
    """
    
    # Individual risk scores
    size_risk, size_exp = calculate_size_risk(design.get('Size', 100))
    charge_risk, charge_exp = calculate_charge_risk(design.get('Charge', -5), design.get('Size', 100))
    dose_risk, dose_exp = calculate_dose_risk(design.get('dose', 10.0), design.get('Size', 100))
    pdi_risk, pdi_exp = calculate_pdi_risk(design.get('PDI', 0.15))
    ligand_risk, ligand_exp = calculate_ligand_risk(design.get('Ligand', 'GalNAc'), design.get('Charge', -5))
    payload_risk, payload_exp = calculate_payload_risk(design.get('payload', 'Drug'), design.get('payload_amount', 1.0))
    material_risk, material_exp = calculate_material_risk(design.get('Material', 'Lipid NP'), design.get('Size', 100))
    
    # Weighted overall score
    weights = {
        'size': 0.15,
        'charge': 0.20,
        'dose': 0.20,
        'pdi': 0.10,
        'ligand': 0.10,
        'payload': 0.15,
        'material': 0.10
    }
    
    overall_score = (
        size_risk * weights['size'] +
        charge_risk * weights['charge'] +
        dose_risk * weights['dose'] +
        pdi_risk * weights['pdi'] +
        ligand_risk * weights['ligand'] +
        payload_risk * weights['payload'] +
        material_risk * weights['material']
    )
    
    # Risk classification
    if overall_score < 3:
        risk_level = "LOW"
        risk_color = "green"
        recommendation = "Favorable safety profile. Proceed with in vitro validation."
    elif overall_score < 5:
        risk_level = "MODERATE"
        risk_color = "orange"
        recommendation = "Acceptable with monitoring. Conduct thorough in vitro and in vivo toxicity studies."
    elif overall_score < 7:
        risk_level = "HIGH"
        risk_color = "red"
        recommendation = "Significant concerns. Consider design modifications before proceeding."
    else:
        risk_level = "VERY HIGH"
        risk_color = "darkred"
        recommendation = "Major safety concerns. Redesign strongly recommended."
    
    return {
        'overall_score': overall_score,
        'risk_level': risk_level,
        'risk_color': risk_color,
        'recommendation': recommendation,
        'individual_scores': {
            'size': {'score': size_risk, 'explanation': size_exp},
            'charge': {'score': charge_risk, 'explanation': charge_exp},
            'dose': {'score': dose_risk, 'explanation': dose_exp},
            'pdi': {'score': pdi_risk, 'explanation': pdi_exp},
            'ligand': {'score': ligand_risk, 'explanation': ligand_exp},
            'payload': {'score': payload_risk, 'explanation': payload_exp},
            'material': {'score': material_risk, 'explanation': material_exp}
        },
        'weights': weights
    }
