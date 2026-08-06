"""
Disease-Drug Mapping Database
Maps diseases to their appropriate therapeutic drugs with clinical context
"""

DISEASE_DRUG_MAPPING = {
    "Liver Cancer (HCC)": {
        "subtypes": [
            "AFP-high HCC",
            "Immune-active HCC",
            "Immune-excluded HCC",
            "Immune-desert HCC"
        ],
        "drugs": [
            {
                "name": "Sorafenib",
                "type": "Tyrosine Kinase Inhibitor",
                "mechanism": "Inhibits VEGFR, PDGFR, RAF kinase",
                "approved": True,
                "suitable_for": ["AFP-high HCC", "Immune-excluded HCC", "Immune-desert HCC"],
                "description": "First-line TKI for HCC - Best for high AFP and immune-cold tumors"
            },
            {
                "name": "Lenvatinib",
                "type": "Tyrosine Kinase Inhibitor",
                "mechanism": "Multi-targeted TKI (FGFR, VEGFR, RET, KIT)",
                "approved": True,
                "suitable_for": ["AFP-high HCC", "Immune-active HCC", "Immune-excluded HCC", "Immune-desert HCC"],
                "description": "Broader kinase inhibition - Excellent for AFP-high and immune-cold tumors"
            },
            {
                "name": "Atezolizumab + Bevacizumab",
                "type": "Checkpoint Inhibitor + Anti-angiogenic",
                "mechanism": "PD-L1 inhibitor + VEGF inhibition",
                "approved": True,
                "suitable_for": ["Immune-active HCC"],
                "description": "First-line combination - Optimal for immune-active tumors"
            },
            {
                "name": "Durvalumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-L1 inhibition",
                "approved": True,
                "suitable_for": ["Immune-active HCC", "Immune-excluded HCC"],
                "description": "PD-L1 checkpoint inhibitor - Good for active and transitional immune states"
            },
            {
                "name": "Nivolumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Immune-active HCC"],
                "description": "PD-1 inhibitor - Optimal for immune-active, PD-1+ tumors"
            },
            {
                "name": "Pembrolizumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Immune-active HCC", "Immune-excluded HCC"],
                "description": "PD-1 inhibitor - Potential for combination in immune-active and excluded"
            }
        ],
        "epidemiology": {
            "incidence": "870,000 new cases annually",
            "mortality": "830,000 deaths annually",
            "5yr_survival": "18%"
        },
        "unmet_needs": "Early detection, improved response rates, combination therapies"
    },

    "Pancreatic Cancer": {
        "subtypes": [
            "Ductal Adenocarcinoma",
            "Neuroendocrine Tumor",
            "Acinar Cell Carcinoma"
        ],
        "drugs": [
            {
                "name": "Gemcitabine",
                "type": "Nucleoside Analog",
                "mechanism": "Inhibits ribonucleotide reductase, deoxycytidine kinase substrate",
                "approved": True,
                "suitable_for": ["Ductal Adenocarcinoma"],
                "description": "Standard chemotherapy for pancreatic cancer"
            },
            {
                "name": "Abraxane (Albumin-bound Paclitaxel)",
                "type": "Microtubule Stabilizer",
                "mechanism": "Albumin-nanoparticle formulation of paclitaxel",
                "approved": True,
                "suitable_for": ["Ductal Adenocarcinoma"],
                "description": "Nanoparticle-based chemotherapy - excellent case for NanoBio application!"
            },
            {
                "name": "FOLFIRINOX",
                "type": "Chemotherapy Combination",
                "mechanism": "5-FU + Leucovorin + Irinotecan + Oxaliplatin",
                "approved": True,
                "suitable_for": ["Ductal Adenocarcinoma"],
                "description": "Aggressive combination for fit patients"
            },
            {
                "name": "Durvalumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-L1 inhibition",
                "approved": True,
                "suitable_for": ["Ductal Adenocarcinoma", "Neuroendocrine Tumor"],
                "description": "Maintenance therapy post-chemotherapy"
            },
            {
                "name": "Somatostatin Analogs",
                "type": "Peptide Analog",
                "mechanism": "Somatostatin receptor agonists (SSA2, SSA5)",
                "approved": True,
                "suitable_for": ["Neuroendocrine Tumor"],
                "description": "Treatment for neuroendocrine pancreatic tumors"
            }
        ],
        "epidemiology": {
            "incidence": "500,000 new cases annually",
            "mortality": "440,000 deaths annually",
            "5yr_survival": "11%"
        },
        "unmet_needs": "Early detection, immunotherapy combinations, delivery to fibrotic stroma"
    },

    "Breast Cancer": {
        "subtypes": [
            "Luminal A (ER/PR+, HER2-)",
            "Luminal B (ER/PR+, HER2+)",
            "HER2-enriched (ER-, PR-, HER2+)",
            "Triple-Negative (ER-, PR-, HER2-)"
        ],
        "drugs": [
            {
                "name": "Tamoxifen",
                "type": "Estrogen Receptor Modulator",
                "mechanism": "Selective ER antagonist",
                "approved": True,
                "suitable_for": ["Luminal A", "Luminal B"],
                "description": "Endocrine therapy for ER+ breast cancer"
            },
            {
                "name": "Trastuzumab (Herceptin)",
                "type": "Monoclonal Antibody",
                "mechanism": "Anti-HER2 antibody",
                "approved": True,
                "suitable_for": ["Luminal B", "HER2-enriched"],
                "description": "HER2-targeting therapy - pioneering cancer nanoparticle application"
            },
            {
                "name": "Pertuzumab",
                "type": "Monoclonal Antibody",
                "mechanism": "Anti-HER2 antibody (different epitope)",
                "approved": True,
                "suitable_for": ["Luminal B", "HER2-enriched"],
                "description": "Dual HER2 blockade with trastuzumab"
            },
            {
                "name": "Lapatinib",
                "type": "Tyrosine Kinase Inhibitor",
                "mechanism": "Dual EGFR/HER2 inhibitor",
                "approved": True,
                "suitable_for": ["Luminal B", "HER2-enriched"],
                "description": "Oral HER2 and EGFR inhibitor"
            },
            {
                "name": "Paclitaxel",
                "type": "Microtubule Stabilizer",
                "mechanism": "Binds beta-tubulin, prevents microtubule depolymerization",
                "approved": True,
                "suitable_for": ["Luminal A", "Luminal B", "HER2-enriched", "Triple-Negative"],
                "description": "Standard chemotherapy agent"
            },
            {
                "name": "Pembrolizumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Triple-Negative"],
                "description": "Immunotherapy for triple-negative breast cancer"
            },
            {
                "name": "Atezolizumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-L1 inhibition",
                "approved": True,
                "suitable_for": ["Triple-Negative"],
                "description": "Approved in combination with chemotherapy for TNBC"
            }
        ],
        "epidemiology": {
            "incidence": "2.2 million new cases annually",
            "mortality": "620,000 deaths annually",
            "5yr_survival": "90%"
        },
        "unmet_needs": "TNBC treatment, resistance to HER2 therapy, cardiac toxicity mitigation"
    },

    "Lung Cancer": {
        "subtypes": [
            "Non-Small Cell Lung Cancer (NSCLC)",
            "Small Cell Lung Cancer (SCLC)",
            "Adenocarcinoma",
            "Squamous Cell Carcinoma"
        ],
        "drugs": [
            {
                "name": "Pembrolizumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Non-Small Cell Lung Cancer (NSCLC)"],
                "description": "First-line immunotherapy for PD-L1+ NSCLC"
            },
            {
                "name": "Nivolumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Non-Small Cell Lung Cancer (NSCLC)", "Small Cell Lung Cancer (SCLC)"],
                "description": "PD-1 inhibitor for advanced NSCLC and SCLC"
            },
            {
                "name": "Atezolizumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-L1 inhibition",
                "approved": True,
                "suitable_for": ["Non-Small Cell Lung Cancer (NSCLC)"],
                "description": "PD-L1 inhibitor, approved as monotherapy and with chemotherapy"
            },
            {
                "name": "Erlotinib",
                "type": "Tyrosine Kinase Inhibitor",
                "mechanism": "EGFR inhibitor",
                "approved": True,
                "suitable_for": ["Adenocarcinoma"],
                "description": "Oral EGFR inhibitor for EGFR-mutant NSCLC"
            },
            {
                "name": "Gefitinib",
                "type": "Tyrosine Kinase Inhibitor",
                "mechanism": "EGFR inhibitor",
                "approved": True,
                "suitable_for": ["Adenocarcinoma"],
                "description": "Oral EGFR inhibitor"
            },
            {
                "name": "Crizotinib",
                "type": "Tyrosine Kinase Inhibitor",
                "mechanism": "ALK and ROS1 inhibitor",
                "approved": True,
                "suitable_for": ["Adenocarcinoma"],
                "description": "ALK-inhibitor for ALK+ NSCLC"
            },
            {
                "name": "Pemetrexed",
                "type": "Antifolate",
                "mechanism": "Blocks multiple folate-dependent enzymes",
                "approved": True,
                "suitable_for": ["Non-Small Cell Lung Cancer (NSCLC)"],
                "description": "Chemotherapy for non-squamous NSCLC"
            }
        ],
        "epidemiology": {
            "incidence": "2.2 million new cases annually",
            "mortality": "1.8 million deaths annually",
            "5yr_survival": "21% (NSCLC), 7% (SCLC)"
        },
        "unmet_needs": "Brain metastasis treatment, overcoming resistance, combination therapies"
    },

    "Colorectal Cancer": {
        "subtypes": [
            "Adenocarcinoma",
            "Mucinous Adenocarcinoma",
            "Neuroendocrine Tumor",
            "Microsatellite Unstable (MSI-H)"
        ],
        "drugs": [
            {
                "name": "5-Fluorouracil (5-FU)",
                "type": "Antimetabolite",
                "mechanism": "Inhibits thymidylate synthase",
                "approved": True,
                "suitable_for": ["Adenocarcinoma", "Mucinous Adenocarcinoma"],
                "description": "Backbone of most colorectal cancer chemotherapy"
            },
            {
                "name": "Oxaliplatin",
                "type": "Platinum Agent",
                "mechanism": "DNA cross-linking",
                "approved": True,
                "suitable_for": ["Adenocarcinoma", "Mucinous Adenocarcinoma"],
                "description": "Third-generation platinum for colorectal cancer"
            },
            {
                "name": "Cetuximab",
                "type": "Monoclonal Antibody",
                "mechanism": "Anti-EGFR antibody",
                "approved": True,
                "suitable_for": ["Adenocarcinoma"],
                "description": "EGFR-targeting for KRAS wild-type CRC"
            },
            {
                "name": "Bevacizumab",
                "type": "Monoclonal Antibody",
                "mechanism": "Anti-VEGF antibody",
                "approved": True,
                "suitable_for": ["Adenocarcinoma", "Mucinous Adenocarcinoma"],
                "description": "Anti-angiogenic therapy"
            },
            {
                "name": "Pembrolizumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Microsatellite Unstable (MSI-H)"],
                "description": "Immunotherapy for MSI-H colorectal cancer"
            },
            {
                "name": "Nivolumab",
                "type": "Checkpoint Inhibitor",
                "mechanism": "PD-1 inhibition",
                "approved": True,
                "suitable_for": ["Microsatellite Unstable (MSI-H)"],
                "description": "PD-1 inhibitor for MSI-H CRC"
            },
            {
                "name": "Irinotecan",
                "type": "Topoisomerase I Inhibitor",
                "mechanism": "Stabilizes DNA-topoisomerase I complex",
                "approved": True,
                "suitable_for": ["Adenocarcinoma"],
                "description": "Chemotherapy for advanced CRC"
            }
        ],
        "epidemiology": {
            "incidence": "1.9 million new cases annually",
            "mortality": "935,000 deaths annually",
            "5yr_survival": "65%"
        },
        "unmet_needs": "Immunotherapy combinations, delivery to colon, metastatic disease treatment"
    }
}

# Utility functions

def get_diseases():
    """Get list of all available diseases"""
    return list(DISEASE_DRUG_MAPPING.keys())

def get_subtypes_for_disease(disease):
    """Get subtypes for a specific disease"""
    if disease in DISEASE_DRUG_MAPPING:
        return DISEASE_DRUG_MAPPING[disease]["subtypes"]
    return []

def get_drugs_for_disease(disease):
    """Get drugs for a specific disease"""
    if disease in DISEASE_DRUG_MAPPING:
        return [drug["name"] for drug in DISEASE_DRUG_MAPPING[disease]["drugs"]]
    return []

def get_drug_details(disease, drug_name):
    """Get detailed information about a specific drug for a disease"""
    if disease in DISEASE_DRUG_MAPPING:
        for drug in DISEASE_DRUG_MAPPING[disease]["drugs"]:
            if drug["name"] == drug_name:
                return drug
    return None

def get_disease_info(disease):
    """Get disease epidemiology and unmet needs"""
    if disease in DISEASE_DRUG_MAPPING:
        data = DISEASE_DRUG_MAPPING[disease]
        return {
            "epidemiology": data.get("epidemiology", {}),
            "unmet_needs": data.get("unmet_needs", "")
        }
    return None

def get_drugs_for_subtype(disease, subtype):
    """Get drugs suitable for a specific disease subtype"""
    if disease in DISEASE_DRUG_MAPPING:
        drugs = []
        for drug in DISEASE_DRUG_MAPPING[disease]["drugs"]:
            if subtype in drug["suitable_for"]:
                drugs.append(drug["name"])
        return drugs
    return []
