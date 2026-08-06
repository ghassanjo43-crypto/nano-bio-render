"""
Immunogenicity & PEGylation Module
Maps materials and drugs to optimal PEGylation strategies and immunogenicity profiles
"""

# Immunogenicity profiles by material
MATERIAL_IMMUNOGENICITY_PROFILES = {
    "PLGA": {
        "base_immunogenicity": "Moderate",
        "clearance_rate_unmodified": "1-3 hours",
        "mps_recognition": "Yes (moderate)",
        "complement_activation": "Moderate",
        "cytokine_response": "TNF-α, IL-6 (moderate)",
        "peg_responsive": True,
        "optimal_peg_density": "5-10% (w/w)",
        "peg_chain_length": "2000-5000 Da",
        "with_peg": {
            "stealth_effect": "High",
            "circulation_time_extended": "4-6 hours",
            "mps_uptake_reduced": "70-80% reduction",
            "immunogenicity": "Low"
        }
    },
    "Lipid NP": {
        "base_immunogenicity": "Very High",
        "clearance_rate_unmodified": "15-30 minutes",
        "mps_recognition": "Yes (rapid, very high)",
        "complement_activation": "Very High",
        "cytokine_response": "Strong innate immune response (IL-6, TNF-α, IFN-β)",
        "peg_responsive": True,
        "optimal_peg_density": "5-10% (molar %)",
        "peg_chain_length": "2000-3000 Da",
        "with_peg": {
            "stealth_effect": "Very High",
            "circulation_time_extended": "1-2 hours",
            "mps_uptake_reduced": "80-90% reduction",
            "immunogenicity": "Low to Moderate"
        }
    },
    "Gold NP": {
        "base_immunogenicity": "Low to Moderate",
        "clearance_rate_unmodified": "2-4 hours",
        "mps_recognition": "Moderate (size-dependent)",
        "complement_activation": "Low",
        "cytokine_response": "IL-6, TNF-α (low to moderate)",
        "peg_responsive": True,
        "optimal_peg_density": "3-7% (w/w)",
        "peg_chain_length": "2000-5000 Da",
        "with_peg": {
            "stealth_effect": "Moderate to High",
            "circulation_time_extended": "3-5 hours",
            "mps_uptake_reduced": "50-70% reduction",
            "immunogenicity": "Very Low"
        }
    },
    "Silica NP": {
        "base_immunogenicity": "Moderate to High",
        "clearance_rate_unmodified": "1-3 hours",
        "mps_recognition": "Yes (moderate)",
        "complement_activation": "Moderate",
        "cytokine_response": "IL-6, TNF-α, IL-1β (moderate)",
        "peg_responsive": True,
        "optimal_peg_density": "5-10% (w/w)",
        "peg_chain_length": "2000-5000 Da",
        "with_peg": {
            "stealth_effect": "High",
            "circulation_time_extended": "3-5 hours",
            "mps_uptake_reduced": "70-80% reduction",
            "immunogenicity": "Low"
        }
    },
    "DNA Origami": {
        "base_immunogenicity": "Moderate (TLR9 activation)",
        "clearance_rate_unmodified": "1-3 hours",
        "mps_recognition": "Yes (moderate)",
        "complement_activation": "Moderate",
        "cytokine_response": "IFN-α, TNF-α (moderate)",
        "peg_responsive": True,
        "optimal_peg_density": "10-15% (w/w)",
        "peg_chain_length": "3000-5000 Da",
        "with_peg": {
            "stealth_effect": "High",
            "circulation_time_extended": "2-4 hours",
            "mps_uptake_reduced": "60-75% reduction",
            "immunogenicity": "Low to Moderate"
        }
    },
    "Liposome": {
        "base_immunogenicity": "High (cationic); Low (neutral)",
        "clearance_rate_unmodified": "30-60 minutes (cationic); 1-3 hours (neutral)",
        "mps_recognition": "Yes (high for cationic)",
        "complement_activation": "High (cationic); Moderate (neutral)",
        "cytokine_response": "Strong response to cationic; moderate to neutral",
        "peg_responsive": True,
        "optimal_peg_density": "5-10% (molar %)",
        "peg_chain_length": "1500-5000 Da",
        "with_peg": {
            "stealth_effect": "Very High",
            "circulation_time_extended": "2-4 hours",
            "mps_uptake_reduced": "80-90% reduction",
            "immunogenicity": "Very Low"
        }
    },
    "Polymeric NP": {
        "base_immunogenicity": "Low to Moderate",
        "clearance_rate_unmodified": "2-4 hours",
        "mps_recognition": "Moderate (material-dependent)",
        "complement_activation": "Moderate",
        "cytokine_response": "TNF-α, IL-6 (low to moderate)",
        "peg_responsive": True,
        "optimal_peg_density": "5-10% (w/w)",
        "peg_chain_length": "2000-5000 Da",
        "with_peg": {
            "stealth_effect": "Moderate to High",
            "circulation_time_extended": "3-6 hours",
            "mps_uptake_reduced": "60-75% reduction",
            "immunogenicity": "Low"
        }
    },
    "Albumin NP": {
        "base_immunogenicity": "Very Low (natural protein)",
        "clearance_rate_unmodified": "12-24 hours (natural circulation)",
        "mps_recognition": "No (opsonized by native pathways)",
        "complement_activation": "Very Low",
        "cytokine_response": "Minimal",
        "peg_responsive": False,
        "optimal_peg_density": "Not needed (already stealth)",
        "peg_chain_length": "N/A",
        "with_peg": {
            "stealth_effect": "Already present",
            "circulation_time_extended": "Already 12-24 hours",
            "mps_uptake_reduced": "Already low",
            "immunogenicity": "Very Low"
        }
    }
}

# Disease-specific immunogenicity requirements
DISEASE_IMMUNOGENICITY_REQUIREMENTS = {
    "Liver Cancer (HCC)": {
        "immune_activation_needed": "Immunotherapy drugs only",
        "peg_requirement": "Required for most TKIs",
        "macrophage_targeting": "Not desired for TKIs (may reduce efficacy)",
        "liver_specific_concerns": "Avoid strong MPS activation in liver",
        "optimal_approach": "PEGylated NPs with minimal immunogenicity for TKIs; selective activation for immunotherapy"
    },
    "Pancreatic Cancer": {
        "immune_activation_needed": "May help with immunotherapy; undesired for chemotherapy",
        "peg_requirement": "Required for all drugs",
        "macrophage_targeting": "Can be beneficial (M1 macrophages)",
        "tumor_microenvironment": "Highly immunosuppressive; may need immune priming",
        "optimal_approach": "PEGylated NPs for most drugs; consider immunomodulatory formulations for checkpoint inhibitors"
    },
    "Breast Cancer": {
        "immune_activation_needed": "Variable (depends on drug class)",
        "peg_requirement": "Required for most chemotherapy",
        "macrophage_targeting": "Can be beneficial (tumor-associated macrophages)",
        "hormone_response": "HER2+ tumors can use immunotherapy synergistically",
        "optimal_approach": "PEGylated NPs; combination targeting feasible"
    },
    "Lung Cancer": {
        "immune_activation_needed": "Important for immunotherapy efficacy",
        "peg_requirement": "Required for most chemotherapy",
        "macrophage_targeting": "Beneficial for immune checkpoint inhibitors",
        "microenvironment": "Varies (cold to hot tumors)",
        "optimal_approach": "PEGylated NPs for chemotherapy; dual targeting for immunotherapy"
    },
    "Colorectal Cancer": {
        "immune_activation_needed": "Moderate (varies by microsatellite status)",
        "peg_requirement": "Required for all drugs",
        "macrophage_targeting": "Can be beneficial",
        "microbiome_impact": "Important; intestinal absorption considerations",
        "optimal_approach": "PEGylated NPs with optional immune priming"
    }
}

# Drug-specific immunogenicity considerations
DRUG_IMMUNOGENICITY_MAPPING = {
    # TKIs - generally need high stealth
    "Sorafenib": {
        "drug_class": "Tyrosine Kinase Inhibitor",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Liposome-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "Very High"
    },
    "Lenvatinib": {
        "drug_class": "Tyrosine Kinase Inhibitor",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Polymeric NP-PEG", "Liposome-PEG"],
        "stealth_priority": "Very High"
    },
    "Regorafenib": {
        "drug_class": "Tyrosine Kinase Inhibitor",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "Very High"
    },
    # Checkpoint inhibitors - may benefit from targeted immunogenicity
    "Atezolizumab": {
        "drug_class": "PD-L1 Inhibitor (Monoclonal Antibody)",
        "additional_immunogenicity": "Moderate (antibody)",
        "peg_importance": "Moderate",
        "recommended_materials": ["Polymeric NP-PEG", "PLGA-PEG", "Liposome-PEG"],
        "stealth_priority": "Moderate (allow some immune activation)"
    },
    "Pembrolizumab": {
        "drug_class": "PD-1 Inhibitor (Monoclonal Antibody)",
        "additional_immunogenicity": "Moderate (antibody)",
        "peg_importance": "Moderate",
        "recommended_materials": ["Polymeric NP-PEG", "PLGA-PEG"],
        "stealth_priority": "Moderate"
    },
    "Nivolumab": {
        "drug_class": "PD-1 Inhibitor (Monoclonal Antibody)",
        "additional_immunogenicity": "Moderate (antibody)",
        "peg_importance": "Moderate",
        "recommended_materials": ["Polymeric NP-PEG", "PLGA-PEG"],
        "stealth_priority": "Moderate"
    },
    # Anti-angiogenic - need high stealth
    "Bevacizumab": {
        "drug_class": "Anti-VEGF Monoclonal Antibody",
        "additional_immunogenicity": "Moderate (antibody)",
        "peg_importance": "High",
        "recommended_materials": ["Liposome-PEG", "PLGA-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "High"
    },
    # Chemotherapy - generally need high stealth
    "Paclitaxel": {
        "drug_class": "Microtubule Stabilizer",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Albumin NP", "Liposome-PEG"],
        "stealth_priority": "Very High"
    },
    "Docetaxel": {
        "drug_class": "Microtubule Stabilizer",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Polymeric NP-PEG", "Albumin NP"],
        "stealth_priority": "Very High"
    },
    "Doxorubicin": {
        "drug_class": "Anthracycline",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["Liposome-PEG", "PLGA-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "Very High"
    },
    "Gemcitabine": {
        "drug_class": "Nucleoside Analog",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Liposome-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "Very High"
    },
    "Cisplatin": {
        "drug_class": "DNA Cross-linking Agent",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Polymeric NP-PEG", "Liposome-PEG"],
        "stealth_priority": "Very High"
    },
    "5-Fluorouracil": {
        "drug_class": "Antimetabolite",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "Very High"
    },
    "Pemetrexed": {
        "drug_class": "Antimetabolite",
        "additional_immunogenicity": "None (small molecule)",
        "peg_importance": "Critical",
        "recommended_materials": ["PLGA-PEG", "Polymeric NP-PEG"],
        "stealth_priority": "Very High"
    }
}


def get_material_immunogenicity_profile(material_name):
    """Get immunogenicity profile for a material"""
    return MATERIAL_IMMUNOGENICITY_PROFILES.get(material_name, {})


def get_disease_immunogenicity_requirements(disease_name):
    """Get immunogenicity requirements for a disease"""
    return DISEASE_IMMUNOGENICITY_REQUIREMENTS.get(disease_name, {})


def get_drug_immunogenicity_considerations(drug_name):
    """Get immunogenicity considerations for a drug"""
    return DRUG_IMMUNOGENICITY_MAPPING.get(drug_name, {})


def get_peg_recommendation(material_name, disease_name, drug_name):
    """Get PEGylation recommendation based on material, disease, and drug"""
    material_profile = get_material_immunogenicity_profile(material_name)
    drug_info = get_drug_immunogenicity_considerations(drug_name)
    
    return {
        "peg_required": material_profile.get("peg_responsive", False),
        "peg_density": material_profile.get("optimal_peg_density"),
        "peg_chain_length": material_profile.get("peg_chain_length"),
        "expected_circulation_time": material_profile.get("with_peg", {}).get("circulation_time_extended"),
        "mps_reduction": material_profile.get("with_peg", {}).get("mps_uptake_reduced"),
        "drug_stealth_priority": drug_info.get("stealth_priority"),
        "rationale": f"PEGylation critical for {drug_name} due to high stealth requirement. "
                    f"{material_name} with {material_profile.get('optimal_peg_density')} PEG "
                    f"achieves {material_profile.get('with_peg', {}).get('circulation_time_extended')} circulation time."
    }


def get_all_materials_ranked_by_immunogenicity():
    """Get materials ranked from lowest to highest immunogenicity"""
    ranking = [
        ("Albumin NP", "Very Low (natural protein)"),
        ("Gold NP", "Low to Moderate"),
        ("Polymeric NP", "Low to Moderate"),
        ("PLGA", "Moderate"),
        ("Silica NP", "Moderate to High"),
        ("DNA Origami", "Moderate (TLR9 activation)"),
        ("Liposome", "High (cationic); Low (neutral)"),
        ("Lipid NP", "Very High")
    ]
    return ranking
