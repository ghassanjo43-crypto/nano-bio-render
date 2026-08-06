"""
Disease Profile Configuration for NanoBio Studio
Defines disease-specific biological parameters and assessment logic
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class DiseaseProfile:
    """Configuration for a target disease"""
    disease_code: str
    disease_name: str
    biological_barriers: List[str]
    primary_clearance_mechanism: str
    immune_involvement_level: str  # low, moderate, high
    vascular_permeability: str  # low, moderate, high
    tissue_retention_difficulty: str  # easy, moderate, difficult
    typical_nanoparticle_uptake_rationale: str
    size_considerations: str
    charge_considerations: str
    pegylation_importance: str  # critical, important, beneficial, optional
    targeting_ligand_benefit: str  # critical, important, beneficial, optional
    typical_formulation_class: str
    regulatory_precedent: str
    clinically_advanced_examples: List[str] = field(default_factory=list)


DISEASE_PROFILES: Dict[str, DiseaseProfile] = {
    "HCC-S": DiseaseProfile(
        disease_code="HCC-S",
        disease_name="Hepatocellular Carcinoma (Spontaneous)",
        biological_barriers=[
            "Hepatic sinusoidal endothelium with fenestrations (50-200 nm)",
            "High Kupffer cell density (80% RES uptake without PEG)",
            "Tumor microenvironment with variable vascularization",
            "Acidic tumor microenvironment (pH 6.5-6.8)",
            "Dense extracellular matrix in desmoplastic regions"
        ],
        primary_clearance_mechanism="Hepatic RES (Kupffer cells) and hepatic sinusoidal uptake",
        immune_involvement_level="high",
        vascular_permeability="moderate",
        tissue_retention_difficulty="moderate",
        typical_nanoparticle_uptake_rationale=(
            "HCC tumors have enhanced permeability and retention effect; "
            "however, high Kupffer cell density necessitates immune evasion via PEGylation"
        ),
        size_considerations="Optimal range 80-150 nm for sinusoidal transport and EPR exploitation",
        charge_considerations="Neutral to slightly negative preferred to minimize opsonization; avoid highly positive",
        pegylation_importance="critical",
        targeting_ligand_benefit="important",
        typical_formulation_class="PEGylated lipid nanoparticle or polymer nanoparticle",
        regulatory_precedent="Multiple lipid NP programs in clinical development for HCC",
        clinically_advanced_examples=["Onpattro (patisiran)", "Givlaari (givosiran)", "Sprout HCC programs"]
    ),
    "PDAC-I": DiseaseProfile(
        disease_code="PDAC-I",
        disease_name="Pancreatic Ductal Adenocarcinoma (Induced)",
        biological_barriers=[
            "Extensive fibrous stroma (>80% of tumor mass)",
            "Poor tumor vascularization with high interstitial pressure",
            "Limited passive diffusion due to dense extracellular matrix",
            "Highly immunosuppressive microenvironment",
            "Pancreatic enzymes may degrade formulations"
        ],
        primary_clearance_mechanism="Reticuloendothelial system and pancreatic drainage",
        immune_involvement_level="high",
        vascular_permeability="low",
        tissue_retention_difficulty="difficult",
        typical_nanoparticle_uptake_rationale=(
            "PDAC represents a highly challenging delivery target due to desmoplasia; "
            "passive EPR effect is minimal; active targeting and stromal modulation may be required"
        ),
        size_considerations="Smaller particles (60-100 nm) preferred to penetrate dense stroma",
        charge_considerations="Moderate positive charge may enhance cellular uptake and penetration",
        pegylation_importance="important",
        targeting_ligand_benefit="critical",
        typical_formulation_class="Actively targeted polymer nanoparticle or neutral liposome",
        regulatory_precedent="Several programs in preclinical/early clinical development",
        clinically_advanced_examples=["CallisteNano CRLX101", "Abraxane (paclitaxel-albumin)"]
    ),
}


def get_disease_profile(disease_code: str) -> DiseaseProfile:
    """
    Retrieve disease profile by code
    Returns default HCC profile if disease not found
    """
    return DISEASE_PROFILES.get(disease_code, DISEASE_PROFILES["HCC-S"])


def list_supported_diseases() -> List[str]:
    """Get list of supported disease codes"""
    return list(DISEASE_PROFILES.keys())
