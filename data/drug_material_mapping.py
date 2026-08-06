"""
Drug-to-Nanoparticle Material Mapping
Recommends optimal and alternative materials based on drug selected
"""

DRUG_MATERIAL_MAPPING = {
    # HCC Drugs
    "Sorafenib": {
        "optimal": ["PLGA", "Lipid NP", "Liposome"],
        "suitable": ["Gold NP", "Polymeric NP"],
        "rationale": "Lipophilic TKI - works well in lipid and polymeric carriers"
    },
    "Lenvatinib": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Liposome", "Polymeric NP"],
        "rationale": "Hydrophobic TKI - best in lipophilic systems"
    },
    "Atezolizumab + Bevacizumab": {
        "optimal": ["Liposome", "Lipid NP"],
        "suitable": ["PLGA", "Silica NP"],
        "rationale": "Antibodies - Lipid carriers provide stability and immunogenicity"
    },
    "Durvalumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "Monoclonal antibody - Liposomes preserve protein structure"
    },
    "Nivolumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "Checkpoint inhibitor antibody - needs gentle handling"
    },
    "Pembrolizumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "anti-PD-1 antibody - Liposomes ideal for protein preservation"
    },
    
    # Pancreatic Cancer Drugs
    "Gemcitabine": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Silica NP", "Polymeric NP"],
        "rationale": "Hydrophilic nucleoside - works in polymeric and lipid systems"
    },
    "Abraxane (Albumin-bound Paclitaxel)": {
        "optimal": ["Albumin NP"],
        "suitable": ["PLGA", "Liposome"],
        "rationale": "Already nanoparticle formulated - can be further encapsulated or used as reference"
    },
    "FOLFIRINOX": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Polymeric NP", "Liposome"],
        "rationale": "Chemotherapy combination - needs robust carrier"
    },
    "Somatostatin Analogs": {
        "optimal": ["Lipid NP", "Liposome"],
        "suitable": ["PLGA", "Polymeric NP"],
        "rationale": "Peptide analog - peptide-friendly carriers preferred"
    },
    
    # Breast Cancer Drugs
    "Tamoxifen": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Liposome", "Gold NP"],
        "rationale": "Lipophilic estrogen modulator - polymeric/lipid carriers ideal"
    },
    "Trastuzumab (Herceptin)": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "Monoclonal antibody - gentle carriers preserve structure"
    },
    "Pertuzumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "Anti-HER2 antibody - Liposomes maintain antibody function"
    },
    "Lapatinib": {
        "optimal": ["PLGA"],
        "suitable": ["Lipid NP", "Polymeric NP"],
        "rationale": "Oral TKI - polymeric carriers enhance oral bioavailability"
    },
    "Paclitaxel": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Liposome", "Albumin NP"],
        "rationale": "Lipophilic antimirotubule - excellent in polymeric/lipid systems"
    },
    "Atezolizumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "PD-L1 checkpoint antibody - Liposomes ideal"
    },
    
    # Lung Cancer Drugs
    "Pembrolizumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "PD-1 inhibitor - Liposomes preserve antibody"
    },
    "Nivolumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "PD-1 checkpoint inhibitor - needs gentle carrier"
    },
    "Erlotinib": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Polymeric NP", "Liposome"],
        "rationale": "Hydrophobic EGFR inhibitor - lipophilic carriers ideal"
    },
    "Gefitinib": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Polymeric NP"],
        "rationale": "EGFR TKI - polymeric systems enhance solubility"
    },
    "Crizotinib": {
        "optimal": ["PLGA"],
        "suitable": ["Lipid NP", "Polymeric NP"],
        "rationale": "ALK inhibitor - PLGA provides sustained release"
    },
    "Pemetrexed": {
        "optimal": ["Lipid NP", "PLGA"],
        "suitable": ["Polymeric NP", "Liposome"],
        "rationale": "Antifolate - benefits from polymeric stabilization"
    },
    
    # Colorectal Cancer Drugs
    "5-Fluorouracil (5-FU)": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Polymeric NP", "Liposome"],
        "rationale": "Hydrophilic nucleotide - works in polymeric systems"
    },
    "Oxaliplatin": {
        "optimal": ["PLGA"],
        "suitable": ["Lipid NP", "Polymeric NP"],
        "rationale": "Platinum agent - robust polymeric carriers preferred"
    },
    "Cetuximab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "Anti-EGFR antibody - Liposomes preserve structure"
    },
    "Bevacizumab": {
        "optimal": ["Liposome"],
        "suitable": ["Lipid NP", "PLGA"],
        "rationale": "Anti-VEGF antibody - needs careful handling"
    },
    "Irinotecan": {
        "optimal": ["PLGA", "Lipid NP"],
        "suitable": ["Polymeric NP", "Liposome"],
        "rationale": "Topoisomerase inhibitor - needs robust carrier"
    }
}

# Available materials in the system
AVAILABLE_MATERIALS = [
    "Lipid NP",
    "PLGA",
    "Gold NP",
    "Silica NP",
    "DNA Origami",
    "Liposome",
    "Polymeric NP",
    "Albumin NP"
]

# Material descriptions for education
MATERIAL_INFO = {
    "Lipid NP": {
        "description": "Ionizable lipid-based nanoparticles - excellent for nucleic acids and hydrophobic drugs",
        "best_payload": "mRNA, siRNA, lipophilic drugs",
        "biodegradation": "7 days"
    },
    "PLGA": {
        "description": "Polymeric biodegradable nanoparticles - versatile for many drug types",
        "best_payload": "Small molecules, proteins, hydrophobic/hydrophilic drugs",
        "biodegradation": "30 days"
    },
    "Liposome": {
        "description": "Phospholipid bilayer vesicles - gentle carriers for proteins and antibodies",
        "best_payload": "Proteins, antibodies, peptides, hydrophobic drugs",
        "biodegradation": "14 days"
    },
    "Gold NP": {
        "description": "Noble metal nanoparticles - excellent for imaging and photothermal therapy",
        "best_payload": "Small molecules, imaging agents, photothermal agents",
        "biodegradation": "180 days"
    },
    "Silica NP": {
        "description": "Silicon dioxide nanoparticles - stable, tunable porosity for drug loading",
        "best_payload": "Small molecules, proteins in mesoporous form",
        "biodegradation": "365+ days"
    },
    "DNA Origami": {
        "description": "Self-assembled DNA structures - programmable, addresses specific cells",
        "best_payload": "Proteins, small molecules, nucleic acids",
        "biodegradation": "1 day"
    },
    "Polymeric NP": {
        "description": "Synthetic polymer-based particles - tunable properties for oral delivery",
        "best_payload": "Small molecules, peptides",
        "biodegradation": "30-60 days"
    },
    "Albumin NP": {
        "description": "Protein-based nanoparticles - biocompatible, FDA-approved (Abraxane)",
        "best_payload": "Hydrophobic drugs, especially paclitaxel",
        "biodegradation": "7-14 days"
    }
}

def get_recommended_materials(drug_name):
    """Get optimal and suitable materials for a drug"""
    if drug_name in DRUG_MATERIAL_MAPPING:
        return DRUG_MATERIAL_MAPPING[drug_name]
    return None

def is_material_recommended(drug_name, material_name):
    """Check if a material is recommended for a drug"""
    mapping = get_recommended_materials(drug_name)
    if mapping:
        return material_name in mapping["optimal"] or material_name in mapping["suitable"]
    return True  # Default: all materials allowed if not specified

def get_recommendation_level(drug_name, material_name):
    """Get the recommendation level: 'optimal', 'suitable', 'not_recommended'"""
    mapping = get_recommended_materials(drug_name)
    if mapping:
        if material_name in mapping["optimal"]:
            return "optimal"
        elif material_name in mapping["suitable"]:
            return "suitable"
        else:
            return "not_recommended"
    return "unknown"

def get_material_info(material_name):
    """Get detailed information about a material"""
    return MATERIAL_INFO.get(material_name, {})

def order_materials_by_recommendation(drug_name):
    """Return materials ordered by recommendation level for a drug"""
    mapping = get_recommended_materials(drug_name)
    if mapping:
        optimal = mapping.get("optimal", [])
        suitable = mapping.get("suitable", [])
        not_recommended = [m for m in AVAILABLE_MATERIALS if m not in optimal and m not in suitable]
        return optimal, suitable, not_recommended
    return AVAILABLE_MATERIALS, [], []
