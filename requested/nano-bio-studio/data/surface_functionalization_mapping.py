"""
Surface Functionalization/Targeting Module
Maps diseases and drugs to optimal surface targeting strategies
"""

# Surface targeting ligands and their characteristics
SURFACE_TARGETING_LIGANDS = {
    "RGD Peptide": {
        "target_receptors": ["Integrin αvβ3", "Integrin αvβ5"],
        "suitable_diseases": ["Breast Cancer", "Lung Cancer", "Pancreatic Cancer", "Colorectal Cancer"],
        "suitable_drugs": [
            "Paclitaxel", "Docetaxel", "Gemcitabine", "5-Fluorouracil",
            "Doxorubicin", "Cisplatin", "Bevacizumab"
        ],
        "mechanism": "Binds to integrin receptors overexpressed on tumor cells and endothelial cells",
        "binding_strength": "High",
        "tissue_penetration": "Moderate to High",
        "immunogenicity": "Low",
        "approval_status": "Experimental/Clinical Trials"
    },
    "Folic Acid": {
        "target_receptors": ["Folate Receptor Alpha (FR-α)"],
        "suitable_diseases": ["Breast Cancer", "Ovarian Cancer", "Lung Cancer"],
        "suitable_drugs": [
            "Methotrexate", "Pemetrexed", "5-Fluorouracil",
            "Paclitaxel", "Doxorubicin"
        ],
        "mechanism": "Binds to FR-α overexpressed on cancer cells (100-1000x higher than normal cells)",
        "binding_strength": "Very High",
        "tissue_penetration": "High",
        "immunogenicity": "Very Low",
        "approval_status": "FDA Approved (clinical use since 2016)"
    },
    "Transferrin": {
        "target_receptors": ["Transferrin Receptor (CD71)"],
        "suitable_diseases": ["Hepatocellular Carcinoma", "Breast Cancer", "Pancreatic Cancer", "Colorectal Cancer"],
        "suitable_drugs": [
            "Doxorubicin", "Cisplatin", "Sorafenib", "Lenvatinib",
            "Regorafenib", "Atezolizumab", "Bevacizumab"
        ],
        "mechanism": "Binds to transferrin receptors highly expressed on rapidly dividing cancer cells",
        "binding_strength": "High",
        "tissue_penetration": "High",
        "immunogenicity": "Low (natural protein)",
        "approval_status": "Clinical Trials"
    },
    "Antibodies (Anti-HER2/Anti-EGFR)": {
        "target_receptors": ["HER2 (ErbB2)", "EGFR"],
        "suitable_diseases": ["Breast Cancer", "Lung Cancer", "Colorectal Cancer"],
        "suitable_drugs": [
            "Paclitaxel", "Docetaxel", "Trastuzumab", "Cetuximab",
            "Pembrolizumab", "Nivolumab", "Doxorubicin"
        ],
        "mechanism": "Monoclonal antibodies bind to specific cancer surface antigens",
        "binding_strength": "Very High",
        "tissue_penetration": "Moderate",
        "immunogenicity": "Moderate to High",
        "approval_status": "FDA Approved (Herceptin-conjugated nanoparticles in development)"
    },
    "Aptamers": {
        "target_receptors": ["Nucleolin", "PSMA", "EpCAM", "Mucin-1"],
        "suitable_diseases": ["Pancreatic Cancer", "Breast Cancer", "Lung Cancer", "Colorectal Cancer"],
        "suitable_drugs": [
            "Doxorubicin", "Camptothecin", "Cisplatin", "Gemcitabine",
            "Paclitaxel", "5-Fluorouracil"
        ],
        "mechanism": "Single-stranded DNA/RNA oligonucleotides fold into specific 3D structures",
        "binding_strength": "High",
        "tissue_penetration": "High",
        "immunogenicity": "Very Low",
        "approval_status": "Clinical Trials"
    },
    "Hyaluronic Acid": {
        "target_receptors": ["CD44"],
        "suitable_diseases": ["Breast Cancer", "Pancreatic Cancer", "Hepatocellular Carcinoma", "Colorectal Cancer"],
        "suitable_drugs": [
            "Doxorubicin", "Paclitaxel", "Gemcitabine", "Cisplatin",
            "Sorafenib", "Lenvatinib"
        ],
        "mechanism": "Binds to CD44 receptor overexpressed on cancer stem cells",
        "binding_strength": "Moderate to High",
        "tissue_penetration": "High",
        "immunogenicity": "Very Low (natural polymer)",
        "approval_status": "Clinical Trials"
    },
    "Peptide Ligands (LHRH, Bombesin)": {
        "target_receptors": ["LHRH Receptor", "Bombesin Receptor"],
        "suitable_diseases": ["Breast Cancer", "Pancreatic Cancer", "Lung Cancer"],
        "suitable_drugs": [
            "Doxorubicin", "Paclitaxel", "Docetaxel", "Cisplatin",
            "Gemcitabine"
        ],
        "mechanism": "Synthetic peptides bind to neuropeptide receptors overexpressed on tumors",
        "binding_strength": "High",
        "tissue_penetration": "Moderate to High",
        "immunogenicity": "Low",
        "approval_status": "Experimental"
    },
    "Galactose/Mannose": {
        "target_receptors": ["Asialoglycoprotein Receptor (ASGPR)", "Mannose Receptor"],
        "suitable_diseases": ["Hepatocellular Carcinoma", "Liver Cancer"],
        "suitable_drugs": [
            "Sorafenib", "Lenvatinib", "Regorafenib", "Atezolizumab",
            "Bevacizumab", "Doxorubicin", "Cisplatin"
        ],
        "mechanism": "Sugar moieties bind to lectins on liver cells",
        "binding_strength": "Moderate",
        "tissue_penetration": "High (liver-specific)",
        "immunogenicity": "Very Low",
        "approval_status": "Clinical Trials"
    }
}

# Ligand recommendations by disease
DISEASE_TARGETING_MAPPING = {
    "Liver Cancer (HCC)": {
        "primary_ligands": ["Galactose/Mannose", "Transferrin", "Hyaluronic Acid"],
        "secondary_ligands": ["Folic Acid", "Aptamers"],
        "explanation": "HCC is liver-specific; galactose/mannose reach liver directly. Transferrin targets dividing HCC cells. CD44 (HA) targets cancer stem cells."
    },
    "Pancreatic Cancer": {
        "primary_ligands": ["Folic Acid", "Hyaluronic Acid", "Aptamers"],
        "secondary_ligands": ["RGD Peptide", "Transferrin", "Peptide Ligands"],
        "explanation": "Pancreatic cancer shows high FR-α and CD44 expression. Aptamers provide alternative specificity."
    },
    "Breast Cancer": {
        "primary_ligands": ["Antibodies (Anti-HER2/Anti-EGFR)", "Folic Acid", "Transferrin"],
        "secondary_ligands": ["Hyaluronic Acid", "RGD Peptide", "Aptamers"],
        "explanation": "HER2+ breast cancers benefit from anti-HER2 targeting. FR-α and CD44 commonly overexpressed."
    },
    "Lung Cancer": {
        "primary_ligands": ["Antibodies (Anti-HER2/Anti-EGFR)", "RGD Peptide", "Folic Acid"],
        "secondary_ligands": ["Transferrin", "Hyaluronic Acid", "Peptide Ligands"],
        "explanation": "EGFR mutations common in lung cancer. High integrin and transferrin receptor expression."
    },
    "Colorectal Cancer": {
        "primary_ligands": ["RGD Peptide", "Transferrin", "Aptamers"],
        "secondary_ligands": ["Hyaluronic Acid", "Antibodies (Anti-HER2/Anti-EGFR)", "Folic Acid"],
        "explanation": "High integrin expression in colorectal tumors. CD44 and transferrin receptors often elevated."
    }
}

# Drug-specific targeting recommendations
DRUG_TARGETING_MAPPING = {
    "Sorafenib": {
        "optimal_ligands": ["Galactose/Mannose", "Transferrin", "Hyaluronic Acid"],
        "rationale": "Multi-kinase inhibitor for HCC; liver-targeted and cancer stem cell targeting preferred",
        "penetration_requirement": "Deep tissue penetration needed"
    },
    "Lenvatinib": {
        "optimal_ligands": ["Transferrin", "Hyaluronic Acid", "Galactose/Mannose"],
        "rationale": "Similar to sorafenib; targeting dividing cells and cancer stem cells critical",
        "penetration_requirement": "Deep tissue penetration needed"
    },
    "Regorafenib": {
        "optimal_ligands": ["Transferrin", "RGD Peptide", "Hyaluronic Acid"],
        "rationale": "Multi-kinase inhibitor; integrin and transferrin targeting enhance uptake",
        "penetration_requirement": "Moderate tissue penetration"
    },
    "Atezolizumab": {
        "optimal_ligands": ["Transferrin", "RGD Peptide"],
        "rationale": "Immunotherapy; minimal additional targeting may suffice, but transferrin reduces off-target clearance",
        "penetration_requirement": "Moderate tissue penetration"
    },
    "Bevacizumab": {
        "optimal_ligands": ["RGD Peptide", "Aptamers"],
        "rationale": "Anti-angiogenic; integrin targeting on endothelial cells",
        "penetration_requirement": "High tissue penetration"
    },
    "Paclitaxel": {
        "optimal_ligands": ["RGD Peptide", "Folic Acid", "Antibodies (Anti-HER2/Anti-EGFR)"],
        "rationale": "Broad cancer drug; multiple targeting strategies applicable",
        "penetration_requirement": "Deep tissue penetration needed"
    },
    "Docetaxel": {
        "optimal_ligands": ["Antibodies (Anti-HER2/Anti-EGFR)", "Folic Acid", "Hyaluronic Acid"],
        "rationale": "Similar to paclitaxel; HER2-targeting particularly valuable",
        "penetration_requirement": "Deep tissue penetration needed"
    },
    "Doxorubicin": {
        "optimal_ligands": ["Transferrin", "Hyaluronic Acid", "Folic Acid"],
        "rationale": "Anthracycline; multiple receptor targeting reduces systemic exposure",
        "penetration_requirement": "Deep tissue penetration needed"
    },
    "Gemcitabine": {
        "optimal_ligands": ["Folic Acid", "Transferrin", "Aptamers"],
        "rationale": "Nucleoside analog; FR-α and transferrin targeting enhance cancer cell uptake",
        "penetration_requirement": "Moderate tissue penetration"
    },
    "Cisplatin": {
        "optimal_ligands": ["Transferrin", "RGD Peptide", "Folic Acid"],
        "rationale": "DNA cross-linker; broad targeting useful for multi-drug resistance",
        "penetration_requirement": "Deep tissue penetration needed"
    },
    "5-Fluorouracil": {
        "optimal_ligands": ["RGD Peptide", "Hyaluronic Acid", "Aptamers"],
        "rationale": "Antimetabolite; integrin and CD44 targeting common in colorectal cancer",
        "penetration_requirement": "Moderate tissue penetration"
    },
    "Pemetrexed": {
        "optimal_ligands": ["Folic Acid", "Transferrin"],
        "rationale": "Folate antagonist; FR-α and transferrin receptors critical for uptake",
        "penetration_requirement": "Moderate tissue penetration"
    },
    "Pembrolizumab": {
        "optimal_ligands": ["Aptamers", "Transferrin"],
        "rationale": "Checkpoint inhibitor; selective targeting reduces systemic exposure",
        "penetration_requirement": "Moderate tissue penetration"
    },
    "Nivolumab": {
        "optimal_ligands": ["Aptamers", "Transferrin", "RGD Peptide"],
        "rationale": "Checkpoint inhibitor; targeting helps overcome tumor microenvironment",
        "penetration_requirement": "Moderate tissue penetration"
    }
}


def get_targeting_options_for_disease(disease_name):
    """Get recommended targeting ligands for a disease"""
    return DISEASE_TARGETING_MAPPING.get(disease_name, {})


def get_targeting_options_for_drug(drug_name):
    """Get recommended targeting ligands for a drug"""
    return DRUG_TARGETING_MAPPING.get(drug_name, {})


def get_ligand_details(ligand_name):
    """Get detailed information about a targeting ligand"""
    return SURFACE_TARGETING_LIGANDS.get(ligand_name, {})


def get_combined_targeting_recommendation(disease_name, drug_name):
    """Get combined targeting recommendation based on both disease and drug"""
    disease_ligands = get_targeting_options_for_disease(disease_name).get("primary_ligands", [])
    drug_ligands = get_targeting_options_for_drug(drug_name).get("optimal_ligands", [])
    
    # Find intersection (ligands appearing in both recommendations)
    optimal = list(set(disease_ligands) & set(drug_ligands))
    
    # If no intersection, use disease primary
    if not optimal:
        optimal = disease_ligands[:2] if disease_ligands else []
    
    return {
        "optimal": optimal,
        "all_options": list(set(disease_ligands + drug_ligands))
    }


def get_all_ligands():
    """Get list of all available targeting ligands"""
    return list(SURFACE_TARGETING_LIGANDS.keys())
