"""
Stability Profile Module
Maps materials and drugs to stability requirements and testing parameters
"""

# Stability profiles by material
MATERIAL_STABILITY_PROFILES = {
    "PLGA": {
        "ph_stability_range": "5.5-8.0",
        "optimal_ph": "6.5-7.4",
        "temperature_stability": "-20°C to 4°C (optimal)",
        "shelf_life_unopened": "6-12 months",
        "freeze_thaw_tolerance": "Moderate (1-3 cycles)",
        "osmotic_stress_tolerance": "Moderate",
        "oxidative_stress_sensitivity": "Moderate",
        "hydrolysis_risk": "High (ester bonds)",
        "burst_release_risk": "Yes (initial 24-48 hours)",
        "storage_conditions": "2-8°C, protected from light",
        "critical_concerns": [
            "Polymer degradation at acidic pH",
            "Burst release of encapsulated drug",
            "Hydrolysis of ester linkages"
        ],
        "stability_testing_required": [
            "pH stability at pH 5.5, 6.5, 7.4, 8.0",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Freeze-thaw cycles (3 cycles)",
            "Drug released over 30 days",
            "Particle size change over 30 days"
        ]
    },
    "Lipid NP": {
        "ph_stability_range": "5.0-8.5",
        "optimal_ph": "7.0-7.4",
        "temperature_stability": "-80°C to -20°C (optimal)",
        "shelf_life_unopened": "1-2 years (if frozen)",
        "freeze_thaw_tolerance": "Low (1 cycle maximum)",
        "osmotic_stress_tolerance": "Low",
        "oxidative_stress_sensitivity": "Very High (lipid peroxidation)",
        "hydrolysis_risk": "High (ester bonds in lipids)",
        "burst_release_risk": "Yes (rapid initial release)",
        "storage_conditions": "-80°C to -20°C, or 2-8°C for 2-6 weeks",
        "critical_concerns": [
            "Lipid peroxidation",
            "Particle aggregation",
            "mRNA degradation",
            "Loss of ionic balance"
        ],
        "stability_testing_required": [
            "Oxidation testing under light/heat",
            "pH stability testing",
            "Osmotic stress (hypotonic/hypertonic)",
            "Particle size and concentration over time",
            "Cargo integrity (mRNA/payload)",
            "Frozen storage stability"
        ]
    },
    "Gold NP": {
        "ph_stability_range": "3.0-11.0",
        "optimal_ph": "5.0-8.0",
        "temperature_stability": "-20°C to 25°C",
        "shelf_life_unopened": "1-2 years",
        "freeze_thaw_tolerance": "High (5+ cycles)",
        "osmotic_stress_tolerance": "Very High",
        "oxidative_stress_sensitivity": "Very Low",
        "hydrolysis_risk": "Very Low",
        "burst_release_risk": "No (physical adsorption)",
        "storage_conditions": "4°C or 25°C, protected from light",
        "critical_concerns": [
            "Aggregation at high ionic strength",
            "Collection at low pH"
        ],
        "stability_testing_required": [
            "pH stability at 3, 5, 7, 9, 11",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Freeze-thaw cycles (5 cycles)",
            "Salt stability (various ionic strengths)",
            "Particle size and aggregation"
        ]
    },
    "Silica NP": {
        "ph_stability_range": "4.0-9.0",
        "optimal_ph": "6.5-8.0",
        "temperature_stability": "4°C to 25°C",
        "shelf_life_unopened": "1-2 years",
        "freeze_thaw_tolerance": "High (3-5 cycles)",
        "osmotic_stress_tolerance": "High",
        "oxidative_stress_sensitivity": "Very Low",
        "hydrolysis_risk": "Low (silica is stable)",
        "burst_release_risk": "No (physical adsorption)",
        "storage_conditions": "4°C or 25°C, in aqueous solution",
        "critical_concerns": [
            "Silica gel formation at very high pH",
            "Leaching at very low pH"
        ],
        "stability_testing_required": [
            "pH stability at 4, 6.5, 7.4, 9",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Freeze-thaw cycles (5 cycles)",
            "Long-term storage (6-12 months)",
            "Particle size and aggregation"
        ]
    },
    "DNA Origami": {
        "ph_stability_range": "6.0-8.5",
        "optimal_ph": "7.0-7.5",
        "temperature_stability": "-20°C to 4°C",
        "shelf_life_unopened": "6-12 months",
        "freeze_thaw_tolerance": "Moderate (1-2 cycles)",
        "osmotic_stress_tolerance": "Moderate",
        "oxidative_stress_sensitivity": "Moderate (nucleic acid degradation)",
        "hydrolysis_risk": "Moderate (phosphodiester bonds)",
        "burst_release_risk": "Variable (strand displacement)",
        "storage_conditions": "-20°C, or 4°C for < 2 weeks",
        "critical_concerns": [
            "Nuclease degradation",
            "Strand hybridization loss",
            "Changes in 3D structure"
        ],
        "stability_testing_required": [
            "Nuclease stability testing",
            "pH stability at 6, 7, 8, 8.5",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Structural integrity (gel electrophoresis)",
            "Freeze-thaw cycles (2 cycles)"
        ]
    },
    "Liposome": {
        "ph_stability_range": "4.5-8.5",
        "optimal_ph": "6.5-7.4",
        "temperature_stability": "-80°C to 2-8°C",
        "shelf_life_unopened": "6-18 months (depending on lipid composition)",
        "freeze_thaw_tolerance": "Low to Moderate",
        "osmotic_stress_tolerance": "Low (osmotic lysis)",
        "oxidative_stress_sensitivity": "High (lipid peroxidation)",
        "hydrolysis_risk": "Moderate (ester bonds in some lipids)",
        "burst_release_risk": "Yes (pH-sensitive)",
        "storage_conditions": "2-8°C or -20°C, protected from light",
        "critical_concerns": [
            "Lipid oxidation",
            "Aggregation",
            "Leakage of encapsulated cargo",
            "Loss of membrane integrity"
        ],
        "stability_testing_required": [
            "Liposome integrity (ζ-potential, size)",
            "pH stability testing",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Cargo leakage over time",
            "Oxidative stability",
            "Freeze-thaw tolerance"
        ]
    },
    "Polymeric NP": {
        "ph_stability_range": "5.0-8.5",
        "optimal_ph": "6.5-7.4",
        "temperature_stability": "4°C to 25°C",
        "shelf_life_unopened": "6-12 months",
        "freeze_thaw_tolerance": "Moderate (2-3 cycles)",
        "osmotic_stress_tolerance": "Moderate",
        "oxidative_stress_sensitivity": "Low to Moderate",
        "hydrolysis_risk": "Variable (polymer-dependent)",
        "burst_release_risk": "Yes (initial release)",
        "storage_conditions": "4°C or 25°C, dry state preferred",
        "critical_concerns": [
            "Polymer degradation",
            "Burst release",
            "Aggregation in suspension"
        ],
        "stability_testing_required": [
            "pH stability at 5, 6.5, 7.4, 8.5",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Freeze-thaw cycles (3 cycles)",
            "Drug release profiles",
            "Particle size change over 30 days"
        ]
    },
    "Albumin NP": {
        "ph_stability_range": "5.5-8.5",
        "optimal_ph": "6.8-7.4",
        "temperature_stability": "2-8°C optimal",
        "shelf_life_unopened": "12-24 months",
        "freeze_thaw_tolerance": "Moderate (2-3 cycles)",
        "osmotic_stress_tolerance": "High",
        "oxidative_stress_sensitivity": "Moderate (protein oxidation)",
        "hydrolysis_risk": "Low",
        "burst_release_risk": "No (covalent binding)",
        "storage_conditions": "2-8°C, may contain preservatives",
        "critical_concerns": [
            "Protein aggregation",
            "Microbial contamination",
            "Loss of protein function"
        ],
        "stability_testing_required": [
            "pH stability at 6, 7, 8, 8.5",
            "Temperature stability at 4°C, 25°C, 37°C",
            "Protein integrity (gel electrophoresis)",
            "Freeze-thaw cycles (3 cycles)",
            "Microbial contamination (if applicable)"
        ]
    }
}

# Drug-specific stability requirements
DRUG_STABILITY_REQUIREMENTS = {
    "Sorafenib": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Moderate (sensitive to extreme pH)",
        "temperature_sensitivity": "Moderate (room temperature stable)",
        "light_sensitivity": "No",
        "critical_concerns": ["Hydrolysis at pH > 8"],
        "recommended_carriers": ["PLGA", "Polymeric NP"]
    },
    "Lenvatinib": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Moderate",
        "temperature_sensitivity": "Moderate",
        "light_sensitivity": "No",
        "critical_concerns": ["Limited aqueous solubility"],
        "recommended_carriers": ["PLGA", "Liposome", "Polymeric NP"]
    },
    "Regorafenib": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Moderate",
        "temperature_sensitivity": "Moderate",
        "light_sensitivity": "No",
        "critical_concerns": ["Very poor aqueous solubility"],
        "recommended_carriers": ["PLGA", "Polymeric NP", "Liposome"]
    },
    "Atezolizumab": {
        "optimal_pH": "6.8-7.4",
        "pH_sensitivity": "High (protein)",
        "temperature_sensitivity": "High (protein)",
        "light_sensitivity": "No",
        "critical_concerns": ["Protein aggregation", "Denaturation at extreme conditions"],
        "recommended_carriers": ["Polymeric NP", "Liposome"]
    },
    "Bevacizumab": {
        "optimal_pH": "6.8-7.4",
        "pH_sensitivity": "High (protein)",
        "temperature_sensitivity": "High (protein)",
        "light_sensitivity": "No",
        "critical_concerns": ["Protein stability critical"],
        "recommended_carriers": ["Liposome", "Polymeric NP"]
    },
    "Paclitaxel": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Low",
        "temperature_sensitivity": "Low",
        "light_sensitivity": "No",
        "critical_concerns": ["Hydrophobic (poor solubility)"],
        "recommended_carriers": ["PLGA", "Albumin NP", "Liposome"]
    },
    "Docetaxel": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Low",
        "temperature_sensitivity": "Low",
        "light_sensitivity": "No",
        "critical_concerns": ["Hydrophobic", "Poor aqueous solubility"],
        "recommended_carriers": ["PLGA", "Polymeric NP", "Albumin NP"]
    },
    "Doxorubicin": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Moderate (pH affects charge)",
        "temperature_sensitivity": "Moderate",
        "light_sensitivity": "Yes (photosensitive)",
        "critical_concerns": ["Light degradation", "pH-dependent charge"],
        "recommended_carriers": ["Liposome", "PLGA", "Polymeric NP"]
    },
    "Gemcitabine": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "High (nucleoside)",
        "temperature_sensitivity": "Moderate",
        "light_sensitivity": "Yes",
        "critical_concerns": ["Nuclease susceptibility", "Light sensitivity"],
        "recommended_carriers": ["PLGA", "Liposome", "Polymeric NP"]
    },
    "Cisplatin": {
        "optimal_pH": "6.0-7.0",
        "pH_sensitivity": "Very High (hydration)",
        "temperature_sensitivity": "Moderate",
        "light_sensitivity": "No",
        "critical_concerns": ["Hydration to Pt(II)", "Limited stability in aqueous solution"],
        "recommended_carriers": ["PLGA", "Polymeric NP", "Liposome"]
    },
    "5-Fluorouracil": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Moderate",
        "temperature_sensitivity": "Low",
        "light_sensitivity": "Yes",
        "critical_concerns": ["Light sensitivity", "Nuclease degradation"],
        "recommended_carriers": ["PLGA", "Polymeric NP"]
    },
    "Pemetrexed": {
        "optimal_pH": "6.5-7.4",
        "pH_sensitivity": "Moderate (aminoacid derivative)",
        "temperature_sensitivity": "Moderate",
        "light_sensitivity": "Yes",
        "critical_concerns": ["pH and light sensitivity"],
        "recommended_carriers": ["PLGA", "Polymeric NP"]
    },
    "Pembrolizumab": {
        "optimal_pH": "6.8-7.4",
        "pH_sensitivity": "High (protein)",
        "temperature_sensitivity": "High (protein)",
        "light_sensitivity": "No",
        "critical_concerns": ["Protein denaturation", "Aggregation risk"],
        "recommended_carriers": ["Polymeric NP", "Liposome"]
    },
    "Nivolumab": {
        "optimal_pH": "6.8-7.4",
        "pH_sensitivity": "High (protein)",
        "temperature_sensitivity": "High (protein)",
        "light_sensitivity": "No",
        "critical_concerns": ["Protein stability", "Requires cold chain"],
        "recommended_carriers": ["Polymeric NP", "Liposome"]
    }
}

# Comprehensive stability testing protocols
STABILITY_TESTING_PROTOCOLS = {
    "Accelerated Stability (3 months)": {
        "temperature": "40°C ± 2°C",
        "humidity": "75% RH ± 5%",
        "light": "1.2 million lux·hours",
        "frequency": "0, 1, 2, 3 months",
        "parameters": ["Size", "PDI", "ζ-potential", "Drug content", "Drug release", "Aggregation"]
    },
    "Long-term Stability (12 months)": {
        "temperature": "25°C ± 2°C",
        "humidity": "60% RH ± 5%",
        "light": "Protected from direct light",
        "frequency": "0, 3, 6, 9, 12 months",
        "parameters": ["Size", "PDI", "ζ-potential", "Drug content", "Sterility", "Aggregation"]
    },
    "Cold Storage Stability (24 months)": {
        "temperature": "2-8°C",
        "humidity": "Not controlled",
        "light": "Protected from light",
        "frequency": "0, 6, 12, 18, 24 months",
        "parameters": ["Size", "PDI", "ζ-potential", "Drug content", "Viability (if biological)"]
    },
    "Freeze-Thaw Stability": {
        "cycles": "3-5 cycles",
        "freeze_temp": "-20°C or -80°C",
        "thaw_temp": "25°C",
        "frequency": "After each cycle",
        "parameters": ["Size", "PDI", "Aggregation", "Drug release", "Integrity"]
    },
    "pH Stability": {
        "pH_values": "3, 5, 6.5, 7.4, 8, 9, 11",
        "incubation_time": "24 hours at 37°C",
        "frequency": "0, 24 hours",
        "parameters": ["Aggregation", "Size", "ζ-potential", "Drug release"]
    },
    "Osmotic Stress": {
        "solutions": ["0.9% NaCl (isotonic)", "0.3% NaCl (hypotonic)", "3% NaCl (hypertonic)"],
        "incubation_time": "24-72 hours at 37°C",
        "frequency": "0, 24, 48, 72 hours",
        "parameters": ["Size", "Aggregation", "Cargo leakage", "Integrity"]
    }
}


def get_material_stability_profile(material_name):
    """Get stability profile for a material"""
    return MATERIAL_STABILITY_PROFILES.get(material_name, {})


def get_drug_stability_requirements(drug_name):
    """Get stability requirements for a drug"""
    return DRUG_STABILITY_REQUIREMENTS.get(drug_name, {})


def get_combined_stability_recommendation(material_name, drug_name):
    """Get combined stability recommendation"""
    material_profile = get_material_stability_profile(material_name)
    drug_requirements = get_drug_stability_requirements(drug_name)
    
    # Safely combine critical concerns, defaulting to empty list if None
    material_concerns = material_profile.get("critical_concerns", []) or []
    drug_concerns = drug_requirements.get("critical_concerns", []) or []
    
    return {
        "optimal_pH": material_profile.get("optimal_pH"),
        "pH_range": material_profile.get("pH_stability_range"),
        "temperature": material_profile.get("temperature_stability"),
        "drug_pH_sensitivity": drug_requirements.get("pH_sensitivity"),
        "critical_concerns": material_concerns + drug_concerns,
        "required_tests": material_profile.get("stability_testing_required")
    }


def get_stability_testing_protocol(protocol_type):
    """Get detailed stability testing protocol"""
    return STABILITY_TESTING_PROTOCOLS.get(protocol_type, {})


def get_shelf_life_estimate(material_name, storage_condition):
    """Get estimated shelf life based on material and storage condition"""
    profile = get_material_stability_profile(material_name)
    shelf_life_unopened = profile.get("shelf_life_unopened", "Unknown")
    return f"{shelf_life_unopened} at {profile.get('storage_conditions')}"
