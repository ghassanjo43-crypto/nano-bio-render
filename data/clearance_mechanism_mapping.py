"""
Clearance Mechanism Module
Maps nanoparticle characteristics to predicted clearance pathways and organ accumulation
"""

# Clearance mechanisms based on size
CLEARANCE_BY_SIZE = {
    "Ultra-small (< 10 nm)": {
        "primary_clearance": "Renal filtration",
        "secondary_clearance": "Hepatic uptake (minimal)",
        "circulation_time": "Minutes (5-30 min)",
        "blood_extravasation": "High (small size)",
        "tumor_penetration": "Excellent",
        "mpa_uptake": "Low",
        "kidney_accumulation": "Very High",
        "liver_accumulation": "Low",
        "spleen_accumulation": "Low",
        "concerns": [
            "Rapid renal clearance may limit therapeutic window",
            "High kidney exposure (potential nephrotoxicity)",
            "Limited MPS protection"
        ],
        "optimal_for": ["Brain tumors", "Highly penetrating tumors"],
        "not_optimal_for": ["HCC", "Diseases requiring long circulation"]
    },
    "Small (10-50 nm)": {
        "primary_clearance": "Mixed - renal and hepatic",
        "secondary_clearance": "MPS uptake (moderate)",
        "circulation_time": "1-4 hours",
        "blood_extravasation": "Moderate to High",
        "tumor_penetration": "Good",
        "mpa_uptake": "Moderate",
        "kidney_accumulation": "Moderate to High",
        "liver_accumulation": "Moderate",
        "spleen_accumulation": "Moderate",
        "concerns": [
            "Partial renal clearance",
            "Moderate MPS uptake",
            "Moderate liver and kidney accumulation"
        ],
        "optimal_for": ["Most tumors", "Balanced targeting"],
        "not_optimal_for": []
    },
    "Medium (50-100 nm)": {
        "primary_clearance": "Hepatic (MPS) and splenic uptake",
        "secondary_clearance": "Renal (minimal)",
        "circulation_time": "2-6 hours (with PEGylation)",
        "blood_extravasation": "Moderate (EPR effect)",
        "tumor_penetration": "Moderate to Good",
        "mpa_uptake": "High",
        "kidney_accumulation": "Low",
        "liver_accumulation": "High",
        "spleen_accumulation": "High",
        "concerns": [
            "High MPS uptake (opsonization)",
            "Requires PEGylation for extended circulation",
            "High liver/spleen accumulation"
        ],
        "optimal_for": ["Most commercial formulations", "HCC"],
        "not_optimal_for": []
    },
    "Large (100-200 nm)": {
        "primary_clearance": "Spleen and lymph node uptake",
        "secondary_clearance": "Hepatic uptake",
        "circulation_time": "1-3 hours (without PEGylation)",
        "blood_extravasation": "Moderate (EPR effect optimal)",
        "tumor_penetration": "Moderate",
        "mpa_uptake": "Very High",
        "kidney_accumulation": "Very Low",
        "liver_accumulation": "Very High",
        "spleen_accumulation": "Very High",
        "concerns": [
            "Rapid MPS clearance",
            "Very high liver/spleen accumulation",
            "PEGylation essential",
            "Limited renal clearance"
        ],
        "optimal_for": ["Immunotherapy", "Spleen-targeted delivery"],
        "not_optimal_for": ["Brain tumor targeting"]
    },
    "Very Large (> 200 nm)": {
        "primary_clearance": "Splenic and lymphatic clearance",
        "secondary_clearance": "Hepatic uptake",
        "circulation_time": "< 1 hour (without PEGylation)",
        "blood_extravasation": "Poor",
        "tumor_penetration": "Poor",
        "mpa_uptake": "Extremely High",
        "kidney_accumulation": "Negligible",
        "liver_accumulation": "Extremely High",
        "spleen_accumulation": "Extremely High",
        "concerns": [
            "Extremely rapid MPS clearance",
            "Poor tumor penetration",
            "Poor blood extravasation"
        ],
        "optimal_for": ["MPS-targeted delivery", "Lymphatic targeting"],
        "not_optimal_for": ["Systemic tumor treatment", "Brain tumors"]
    }
}

# Clearance pathways by charge
CLEARANCE_BY_CHARGE = {
    "Cationic (+ charge)": {
        "protein_corona_formation": "Rapid and extensive",
        "mps_recognition": "Very Fast",
        "circulation_time": "Minutes (without shielding)",
        "liver_accumulation": "Very High",
        "spleen_accumulation": "Very High",
        "blood_compatibility": "Poor (RBC aggregation risk)",
        "kidney_filtration": "Minimal (absorbed by RES)",
        "requires_shielding": True,
        "shielding_method": "PEGylation or protein coating",
        "concerns": [
            "Rapid opsonization",
            "Potential for RBC hemolysis",
            "Blood clotting anomalies"
        ],
        "suitable_applications": ["Gene delivery", "Immune stimulation"],
        "unsuitable_applications": ["Passive targeting", "Long circulation"]
    },
    "Neutral (no charge)": {
        "protein_corona_formation": "Minimal to Moderate",
        "mps_recognition": "Moderate",
        "circulation_time": "2-4 hours (size-dependent)",
        "liver_accumulation": "Moderate to High",
        "spleen_accumulation": "Moderate",
        "blood_compatibility": "Good",
        "kidney_filtration": "Size-dependent",
        "requires_shielding": False,
        "shielding_method": "Not needed for charge",
        "concerns": [
            "Still subject to MPS uptake (size-dependent)",
            "Moderate liver accumulation"
        ],
        "suitable_applications": ["Most therapeutic applications"],
        "unsuitable_applications": ["None (universal)"]
    },
    "Anionic (- charge)": {
        "protein_corona_formation": "Moderate",
        "mps_recognition": "Moderate",
        "circulation_time": "2-5 hours (size/coating dependent)",
        "liver_accumulation": "Moderate",
        "spleen_accumulation": "Low to Moderate",
        "blood_compatibility": "Good",
        "kidney_filtration": "Size-dependent",
        "requires_shielding": False,
        "shielding_method": "Optional (PEGylation for extended circulation)",
        "concerns": [
            "Different protein corona than cationic",
            "Moderate MPS recognition"
        ],
        "suitable_applications": ["Nucleic acid delivery", "Most therapeutics"],
        "unsuitable_applications": []
    }
}

# Disease-organ accumulation preferences
DISEASE_CLEARANCE_PREFERENCES = {
    "Liver Cancer (HCC)": {
        "target_organ": "Liver",
        "desired_accumulation": "Liver (specific HCC cells)",
        "avoid_accumulation": ["Spleen (excessive)", "Kidney (nephrotoxicity)"],
        "recommended_size": "50-100 nm",
        "recommended_charge": "Neutral to Anionic",
        "recommended_modifications": [
            "PEGylation for MPS evasion",
            "Galactose/Mannose targeting",
            "Transferrin targeting"
        ],
        "optimization_goal": "High liver accumulation, HCC cell-specific uptake"
    },
    "Pancreatic Cancer": {
        "target_organ": "Pancreas",
        "desired_accumulation": "Pancreatic tumor cells",
        "avoid_accumulation": ["Liver (excessive)", "Kidney (off-target)"],
        "recommended_size": "50-100 nm",
        "recommended_charge": "Neutral",
        "recommended_modifications": [
            "PEGylation for extended circulation",
            "Folate receptor targeting (FR-α)",
            "CD44 targeting (Hyaluronic acid)"
        ],
        "optimization_goal": "Extended circulation for tumor accumulation via EPR"
    },
    "Breast Cancer": {
        "target_organ": "Mammary gland",
        "desired_accumulation": "Breast tumor cells",
        "avoid_accumulation": ["Excessive liver/spleen", "Kidney"],
        "recommended_size": "70-120 nm",
        "recommended_charge": "Neutral to Anionic",
        "recommended_modifications": [
            "PEGylation",
            "HER2 antibody targeting",
            "Folic acid targeting"
        ],
        "optimization_goal": "Optimized EPR effect with active targeting"
    },
    "Lung Cancer": {
        "target_organ": "Lung",
        "desired_accumulation": "Lung tumor cells",
        "avoid_accumulation": ["Liver/spleen (excessive)", "Kidney"],
        "recommended_size": "50-150 nm",
        "recommended_charge": "Neutral",
        "recommended_modifications": [
            "PEGylation for circulation",
            "RGD peptide or antibody targeting",
            "Integrin targeting"
        ],
        "optimization_goal": "Lung-specific accumulation via breathing/circulation"
    },
    "Colorectal Cancer": {
        "target_organ": "Colon",
        "desired_accumulation": "Colorectal tumor cells",
        "avoid_accumulation": ["Systemic accumulation", "Off-target organs"],
        "recommended_size": "50-100 nm",
        "recommended_charge": "Neutral",
        "recommended_modifications": [
            "Intestinal pH targeting (if oral)",
            "RGD peptide targeting",
            "Extended circulation via PEGylation"
        ],
        "optimization_goal": "High tumor accumulation, minimal off-target distribution"
    }
}

# Material-based clearance profiles
MATERIAL_CLEARANCE_PROFILES = {
    "PLGA": {
        "typical_size_range": "50-200 nm",
        "typical_charge": "Neutral to Slightly Negative",
        "primary_route": "Hepatic (MPS followed by hepatocyte uptake)",
        "secondary_route": "Splenic uptake (size-dependent)",
        "half_life": "2-4 hours",
        "liver_accumulation": "Very High",
        "spleen_accumulation": "High",
        "kidney_accumulation": "Low",
        "brain_penetration": "Low (unless < 50 nm)",
        "bbb_crossing": "Poor",
        "metabolism": "Hepatic (enzymatic degradation of PLGA)",
        "advantages": ["Biodegradable", "FDA approved", "Long-circulation with PEG"],
        "disadvantages": ["High MPS uptake", "Limited BBB penetration"]
    },
    "Lipid NP": {
        "typical_size_range": "70-150 nm",
        "typical_charge": "Cationic to Neutral (formulation-dependent)",
        "primary_route": "Hepatic (MPS uptake is rapid initially)",
        "secondary_route": "Splenic uptake",
        "half_life": "15-30 minutes (uncoated); 1-2 hours (PEGylated)",
        "liver_accumulation": "Very High (major barrier)",
        "spleen_accumulation": "High",
        "kidney_accumulation": "Low",
        "brain_penetration": "Moderate (with ApoE)",
        "bbb_crossing": "Possible (with ApoE enhancement)",
        "metabolism": "Hepatic (lipid breakdown)",
        "advantages": ["High transfection efficiency", "mRNA delivery potential", "Can target brain"],
        "disadvantages": ["Rapid MPS clearance", "Requires extensive PEGylation", "Strong innate immune response"]
    },
    "Gold NP": {
        "typical_size_range": "10-150 nm",
        "typical_charge": "Neutral to Anionic (surface-dependent)",
        "primary_route": "Size-dependent (< 10 nm: renal; > 10 nm: hepatic)",
        "secondary_route": "Spleen (larger sizes)",
        "half_life": "1-5 hours (size-dependent)",
        "liver_accumulation": "Moderate to High",
        "spleen_accumulation": "Moderate",
        "kidney_accumulation": "High (small sizes)",
        "brain_penetration": "Size-dependent",
        "bbb_crossing": "Possible for ultra-small sizes",
        "metabolism": "No metabolism (inert, cleared as-is)",
        "advantages": ["Inert (no metabolism)", "Long shelf-life", "Tunable size"],
        "disadvantages": ["Renal accumulation risk", "High density"]
    },
    "Silica NP": {
        "typical_size_range": "10-200 nm",
        "typical_charge": "Neutral to Slightly Negative",
        "primary_route": "Hepatic (MPS) and renal (size-dependent)",
        "secondary_route": "Splenic uptake",
        "half_life": "1-4 hours (size-dependent)",
        "liver_accumulation": "Moderate to High",
        "spleen_accumulation": "Moderate",
        "kidney_accumulation": "Variable (size-dependent)",
        "brain_penetration": "Size-dependent",
        "bbb_crossing": "Poor",
        "metabolism": "Slow (partially cleared via MPS, partially eliminated)",
        "advantages": ["Tunable size", "Good biocompatibility", "Long shelf-life"],
        "disadvantages": ["Hepatic and splenic accumulation", "Potential kidney deposition"]
    },
    "DNA Origami": {
        "typical_size_range": "50-150 nm",
        "typical_charge": "Anionic (DNA phosphate backbone)",
        "primary_route": "Hepatic and splenic uptake",
        "secondary_route": "Nuclease-mediated degradation",
        "half_life": "1-2 hours",
        "liver_accumulation": "High",
        "spleen_accumulation": "Moderate to High",
        "kidney_accumulation": "Low",
        "brain_penetration": "Poor",
        "bbb_crossing": "Poor",
        "metabolism": "Enzymatic (nuclease degradation)",
        "advantages": ["Programmable targeting", "Immunostimulatory (if desired)"],
        "disadvantages": ["Nuclease susceptibility", "Hepatic accumulation", "Immunogenicity"]
    },
    "Liposome": {
        "typical_size_range": "50-400 nm",
        "typical_charge": "Neutral to Cationic (formula-dependent)",
        "primary_route": "Hepatic MPS uptake (rapid for uncoated)",
        "secondary_route": "Splenic uptake",
        "half_life": "30-60 minutes (uncoated); 4-6 hours (PEGylated)",
        "liver_accumulation": "Very High (uncoated)",
        "spleen_accumulation": "High",
        "kidney_accumulation": "Low",
        "brain_penetration": "Low",
        "bbb_crossing": "Poor",
        "metabolism": "Hepatic (hepatocyte-mediated lipid uptake and metabolism)",
        "advantages": ["Flexibility in formulation", "Long circulation (PEGylated)", "Clinically approved"],
        "disadvantages": ["Rapid MPS clearance", "High liver accumulation"]
    },
    "Polymeric NP": {
        "typical_size_range": "50-300 nm",
        "typical_charge": "Neutral to Slightly Negative (polymer-dependent)",
        "primary_route": "Hepatic (MPS) and splenic uptake",
        "secondary_route": "Renal (for very small sizes)",
        "half_life": "2-6 hours (polymer and size-dependent)",
        "liver_accumulation": "High",
        "spleen_accumulation": "Moderate to High",
        "kidney_accumulation": "Low (except ultra-small)",
        "brain_penetration": "Moderate (with optimization)",
        "bbb_crossing": "Possible with targeting",
        "metabolism": "Variable (polymer-dependent degradation)",
        "advantages": ["Tunable properties", "Biodegradable options", "Extended circulation possible"],
        "disadvantages": ["MPS accumulation", "Variable liver accumulation"]
    },
    "Albumin NP": {
        "typical_size_range": "50-200 nm",
        "typical_charge": "Anionic (natural protein)",
        "primary_route": "Natural albumin circulation pathway",
        "secondary_route": "Slower hepatic uptake than synthetic NPs",
        "half_life": "12-24 hours (natural albumin circulation)",
        "liver_accumulation": "Low to Moderate",
        "spleen_accumulation": "Low",
        "kidney_accumulation": "Low",
        "brain_penetration": "Moderate (natural protein advantage)",
        "bbb_crossing": "Possible (gp60-mediated transport)",
        "metabolism": "Hepatic proteolysis (natural protein degradation)",
        "advantages": ["Long circulation time", "FDA approved (Abraxane®)", "Good biocompatibility"],
        "disadvantages": ["Higher cost", "Potential protein aggregation"]
    }
}


def get_clearance_by_size(size_category):
    """Get clearance mechanism information by size"""
    return CLEARANCE_BY_SIZE.get(size_category, {})


def get_clearance_by_charge(charge_type):
    """Get clearance mechanism information by charge"""
    return CLEARANCE_BY_CHARGE.get(charge_type, {})


def get_disease_clearance_optimization(disease_name):
    """Get clearance optimization recommendations for a disease"""
    return DISEASE_CLEARANCE_PREFERENCES.get(disease_name, {})


def get_material_clearance_profile(material_name):
    """Get clearance profile for a material"""
    return MATERIAL_CLEARANCE_PROFILES.get(material_name, {})


def get_predicted_organ_accumulation(material_name, size_nm, charge_type):
    """Predict organ accumulation based on material, size, and charge"""
    material_profile = get_material_clearance_profile(material_name)
    size_profile = get_clearance_by_size(categorize_size(size_nm))
    charge_profile = get_clearance_by_charge(charge_type)
    
    return {
        "liver_accumulation": size_profile.get("liver_accumulation"),
        "spleen_accumulation": size_profile.get("spleen_accumulation"),
        "kidney_accumulation": size_profile.get("kidney_accumulation"),
        "circulation_half_life": material_profile.get("half_life"),
        "material_advantage": material_profile.get("advantages"),
        "clearance_limitation": material_profile.get("disadvantages")
    }


def categorize_size(size_nm):
    """Categorize nanoparticle size"""
    if size_nm < 10:
        return "Ultra-small (< 10 nm)"
    elif size_nm < 50:
        return "Small (10-50 nm)"
    elif size_nm < 100:
        return "Medium (50-100 nm)"
    elif size_nm < 200:
        return "Large (100-200 nm)"
    else:
        return "Very Large (> 200 nm)"


def get_clearance_optimization_for_disease_drug_material(disease_name, drug_name, material_name):
    """Get comprehensive clearance optimization"""
    disease_spec = get_disease_clearance_optimization(disease_name)
    material_spec = get_material_clearance_profile(material_name)
    
    return {
        "disease_target": disease_spec.get("target_organ"),
        "recommended_size": disease_spec.get("recommended_size"),
        "material_typical_size": material_spec.get("typical_size_range"),
        "liver_concern": f"Material accumulation: {material_spec.get('liver_accumulation')}",
        "spleen_concern": f"Material accumulation: {material_spec.get('spleen_accumulation')}",
        "half_life": material_spec.get("half_life"),
        "recommendations": disease_spec.get("recommended_modifications")
    }
