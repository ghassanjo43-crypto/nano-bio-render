"""
Disease-Specific Nanoparticle Design Database
Comprehensive parameters for cancer subtypes targeting with therapeutic drugs
Supports HCC, other liver cancers, and expandable to other disease types
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ============================================================
# ENUMS for Type Safety
# ============================================================

class CancerType(str, Enum):
    """Primary cancer types supported"""
    LUNG = "lung"
    BREAST = "breast"
    LIVER = "liver"
    PANCREATIC = "pancreatic"
    BRAIN = "brain"
    COLORECTAL = "colorectal"
    OVARIAN = "ovarian"

class LiverCancerSubtype(str, Enum):
    """Liver cancer subtypes"""
    HCC_S = "hcc_s"  # Well-differentiated
    HCC_MS = "hcc_ms"  # Mixed/intermediate
    HCC_L = "hcc_l"  # Poorly differentiated, aggressive
    CHOLANGIOCARCINOMA_INTRA = "cholangio_intra"
    CHOLANGIOCARCINOMA_EXTRA = "cholangio_extra"
    HEPATOBLASTOMA = "hepatoblastoma"

class TargetingLigand(str, Enum):
    """Targeting ligands for nanoparticles"""
    ASGPR = "asialoglycoprotein"
    ASGPR_PEPTIDE = "asgpr_peptide"
    FOLATE = "folate"
    RGD = "rgd"
    EGFR = "egfr"
    TRANSFERRIN = "transferrin"
    NEUTRAL = "neutral"

# ============================================================
# Data Classes
# ============================================================

@dataclass
class NPDesignParameters:
    """Nanoparticle design constraints for a cancer subtype"""
    size_nm_min: int
    size_nm_max: int
    size_nm_optimal: int
    surface_charge: str
    charge_value: int
    peg_coating_percent: float
    targeting_ligand: TargetingLigand
    drug_loading_percent_min: int
    drug_loading_percent_max: int
    biodegradation_hours_min: int
    biodegradation_hours_max: int
    renal_clearance_nm_threshold: int = 40  # <40nm typically cleared

@dataclass
class ClinicalContext:
    """Clinical characteristics of cancer subtype"""
    name: str
    prevalence_percent: float
    five_year_survival_percent: float
    growth_pattern: str  # "slow", "moderate", "aggressive"
    vascularization: str  # "good", "moderate", "poor", "hypoxic"
    median_size_at_diagnosis_cm: float
    median_time_to_progression_months: int

@dataclass
class TherapeuticRecommendation:
    """Drug recommendation for specific cancer subtype"""
    drug_name: str
    drug_type: str  # "chemotherapy", "immunotherapy", "targeted", "anti-angiogenic"
    mechanism: str
    reason_for_subtype: str
    typical_dose: str
    clinical_trials: List[str] = None

# ============================================================
# PRIMARY DATABASE: LIVER CANCER
# ============================================================

LIVER_CANCER_DATABASE = {
    "hcc_s": {
        "display_name": "HCC-S (Well-differentiated)",
        "description": "Hepatocellular Carcinoma - Subclass S: Better prognosis, slower growth",
        
        "clinical_context": ClinicalContext(
            name="HCC-S (Well-differentiated)",
            prevalence_percent=15,
            five_year_survival_percent=30,
            growth_pattern="slow",
            vascularization="good",
            median_size_at_diagnosis_cm=3.5,
            median_time_to_progression_months=20
        ),
        
        "design_parameters": NPDesignParameters(
            size_nm_min=100,
            size_nm_max=150,
            size_nm_optimal=120,
            surface_charge="neutral",
            charge_value=0,
            peg_coating_percent=5,
            targeting_ligand=TargetingLigand.ASGPR,
            drug_loading_percent_min=20,
            drug_loading_percent_max=30,
            biodegradation_hours_min=24,
            biodegradation_hours_max=48
        ),
        
        "design_rationale": [
            "Better vascularization → larger particles acceptable",
            "Use ASGPR targeting for hepatocyte-specific uptake",
            "Neutral charge reduces immune activation in slower-growing tumors",
            "Moderate PEG (5%) for some stealth without excessive impact",
            "Longer circulation window due to slower progression"
        ],
        
        "tissue_barriers": {
            "difficulty_level": 3,
            "difficulty": "Moderate",
            "description": "Good blood supply, normal vascularization",
            "key_challenges": ["Hepatic clearance", "immune recognition", "tumor penetration"],
            "advanced_strategies": [
                "Standard NP design with moderate targeting",
                "Focus on hepatocyte-specific ASGPR ligands",
                "Optimize for systemic circulation time",
                "Consider drug combination for enhanced efficacy"
            ]
        },
        
        "recommended_drugs": [
            TherapeuticRecommendation(
                drug_name="Sorafenib",
                drug_type="targeted",
                mechanism="Multi-kinase inhibitor (VEGFR, PDGFR, RAF)",
                reason_for_subtype="Slows growth in early-stage HCC, well-tolerated",
                typical_dose="400mg BID",
                clinical_trials=["SHARP trial", "ASIA-PACIFIC trial"]
            ),
            TherapeuticRecommendation(
                drug_name="Lenvatinib",
                drug_type="targeted",
                mechanism="Multi-kinase inhibitor (FGFR, VEGFR, RET)",
                reason_for_subtype="First-line for advanced HCC, improves survival",
                typical_dose="8-12mg daily",
                clinical_trials=["REFLECT trial"]
            ),
            TherapeuticRecommendation(
                drug_name="Doxorubicin",
                drug_type="chemotherapy",
                mechanism="DNA intercalating agent",
                reason_for_subtype="Systemic option for well-differentiated tumors",
                typical_dose="60mg/m² IV",
                clinical_trials=["TACE + Doxorubicin combinations"]
            )
        ]
    },
    
    "hcc_ms": {
        "display_name": "HCC-MS (Intermediate)",
        "description": "Hepatocellular Carcinoma - Mixed Subclass: Intermediate aggressiveness",
        
        "clinical_context": ClinicalContext(
            name="HCC-MS (Intermediate)",
            prevalence_percent=45,
            five_year_survival_percent=15,
            growth_pattern="moderate",
            vascularization="moderate",
            median_size_at_diagnosis_cm=4.0,
            median_time_to_progression_months=12
        ),
        
        "design_parameters": NPDesignParameters(
            size_nm_min=80,
            size_nm_max=120,
            size_nm_optimal=100,
            surface_charge="slightly_negative",
            charge_value=-5,
            peg_coating_percent=7,
            targeting_ligand=TargetingLigand.ASGPR,
            drug_loading_percent_min=25,
            drug_loading_percent_max=35,
            biodegradation_hours_min=12,
            biodegradation_hours_max=24
        ),
        
        "design_rationale": [
            "Moderate vasculature → need smaller particles for penetration",
            "Slight negative charge facilitates tumor interstitial penetration",
            "Increased PEG (7%) for better immune evasion",
            "Faster degradation needed for timely drug release",
            "Balance speed of delivery with tumor penetration"
        ],
        
        "tissue_barriers": {
            "difficulty_level": 4,
            "difficulty": "Moderate-High",
            "description": "Variable vasculature, some hypoxic regions",
            "key_challenges": ["Hypoxic regions", "stromal barriers", "immune infiltration"],
            "advanced_strategies": [
                "Increase PEG coating for immune evasion",
                "Use slight negative charge for stromal penetration",
                "Consider anti-angiogenic agents in combination",
                "Optimize for variable vascularization regions"
            ]
        },
        
        "recommended_drugs": [
            TherapeuticRecommendation(
                drug_name="Atezolizumab + Bevacizumab",
                drug_type="immunotherapy + anti-angiogenic",
                mechanism="PD-L1 checkpoint inhibitor + anti-VEGF",
                reason_for_subtype="FDA-approved combination, effective for intermediate HCC",
                typical_dose="Atezolizumab 840mg IV + Bevacizumab 15mg/kg IV Q3W",
                clinical_trials=["IMbrave150 (Phase 3)"]
            ),
            TherapeuticRecommendation(
                drug_name="Sorafenib + Pembrolizumab",
                drug_type="targeted + immunotherapy",
                mechanism="Multi-kinase + PD-1 checkpoint inhibitor",
                reason_for_subtype="Combination improves outcomes in intermediate HCC",
                typical_dose="Sorafenib 400mg BID + Pembrolizumab 200mg IV Q3W",
                clinical_trials=["KEYNOTE-240"]
            ),
            TherapeuticRecommendation(
                drug_name="Gemcitabine + Cisplatin",
                drug_type="chemotherapy",
                mechanism="Antimetabolite + alkylating agent",
                reason_for_subtype="Effective for intermediate-advanced disease",
                typical_dose="Gemcitabine 1000mg/m² + Cisplatin 25mg/m² IV",
                clinical_trials=["GEMOX regimen studies"]
            )
        ]
    },
    
    "hcc_l": {
        "display_name": "HCC-L (Poorly differentiated, Aggressive)",
        "description": "Hepatocellular Carcinoma - Subclass L: Worst prognosis, highly aggressive",
        
        "clinical_context": ClinicalContext(
            name="HCC-L (Poorly differentiated, Aggressive)",
            prevalence_percent=40,
            five_year_survival_percent=10,
            growth_pattern="aggressive",
            vascularization="hypoxic",
            median_size_at_diagnosis_cm=5.5,
            median_time_to_progression_months=6
        ),
        
        "design_parameters": NPDesignParameters(
            size_nm_min=50,
            size_nm_max=80,
            size_nm_optimal=65,
            surface_charge="more_negative",
            charge_value=-10,
            peg_coating_percent=10,
            targeting_ligand=TargetingLigand.ASGPR_PEPTIDE,
            drug_loading_percent_min=30,
            drug_loading_percent_max=40,
            biodegradation_hours_min=6,
            biodegradation_hours_max=12
        ),
        
        "design_rationale": [
            "⚠️ CRITICAL: Poor vasculature (hypoxic) → MUST use smaller particles",
            "Smaller NPs (50-80nm) penetrate through dense stromal barriers",
            "Higher negative charge (-10) enhances penetration through ECM",
            "Maximum PEG (10%) critical for immune invisibility",
            "Faster degradation (6-12h) needed in hostile hypoxic environment",
            "Higher drug loading (30-40%) compensates for poor delivery efficiency",
            "Choose drugs that work in hypoxic conditions"
        ],
        
        "tissue_barriers": {
            "difficulty_level": 5,
            "difficulty": "VERY HIGH - Design Challenging",
            "description": "Hypoxic core, dense stromal barrier, poor vascularization",
            "key_challenges": [
                "Hypoxia reduces drug efficacy",
                "Dense desmoplastic stroma blocks NP penetration",
                "High interstitial fluid pressure",
                "Rapid growth limits circulation time",
                "Strong immune infiltration",
                "Necrotic regions within tumor"
            ],
            "advanced_strategies": [
                "Consider carrier-free drug or combinatorial therapy",
                "Use angioptin-targeting ligands",
                "Consider immunotherapy + chemotherapy combination",
                "May require matrix-degrading enzymes on NP surface"
            ]
        },
        
        "recommended_drugs": [
            TherapeuticRecommendation(
                drug_name="Atezolizumab + Bevacizumab",
                drug_type="immunotherapy + anti-angiogenic",
                mechanism="PD-L1 checkpoint inhibitor + anti-VEGF",
                reason_for_subtype="Restores angiogenesis in hypoxic HCC-L + breaks immune tolerance",
                typical_dose="Atezolizumab 840mg IV + Bevacizumab 15mg/kg IV Q3W",
                clinical_trials=["IMbrave150 (Phase 3) - significant benefit in advanced HCC"]
            ),
            TherapeuticRecommendation(
                drug_name="Sorafenib",
                drug_type="targeted",
                mechanism="Multi-kinase inhibitor targeting angiogenesis",
                reason_for_subtype="Targets VEGF/RAF in hypoxic microenvironment",
                typical_dose="400mg BID",
                clinical_trials=["SHARP - standard of care for 15+ years"]
            ),
            TherapeuticRecommendation(
                drug_name="Regorafenib",
                drug_type="targeted",
                mechanism="Multi-kinase inhibitor (VEGFR, PDGFR, FGFR, RET)",
                reason_for_subtype="Second-line after Sorafenib failure in aggressive HCC",
                typical_dose="160mg daily × 3 weeks on, 1 week off",
                clinical_trials=["RESORCE trial"]
            ),
            TherapeuticRecommendation(
                drug_name="Tirzepatide (experimental for HCC-L)",
                drug_type="hormone-based",
                mechanism="GLP-1/GIP dual agonist - improves metabolic factors",
                reason_for_subtype="Emerging option, addresses metabolic dysfunction in aggressive HCC",
                typical_dose="2.5-15mg weekly SC",
                clinical_trials=["Early phase studies in HCC"]
            )
        ],
        
        "special_notes": {
            "challenge_level": "★★★★★ (Highest difficulty)",
            "why_challenging": "Hypoxic environment, dense stroma, poor vascularization",
            "clinical_reality": "5-year survival only 10% - requires aggressive multimodal therapy",
            "np_design_strategy": "Size is critical parameter - cannot exceed 80nm",
            "recommended_approach": "Combination therapy (immunotherapy + anti-angiogenic + chemotherapy)"
        }
    }
}

# ============================================================
# DISEASE DATABASE ACCESS FUNCTIONS
# ============================================================

def get_liver_cancer_subtypes() -> List[str]:
    """Get list of available liver cancer subtypes"""
    return list(LIVER_CANCER_DATABASE.keys())

def get_disease_design_parameters(subtype: str) -> Optional[NPDesignParameters]:
    """Get design parameters for a specific cancer subtype"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype]["design_parameters"]
    return None

def get_disease_clinical_context(subtype: str) -> Optional[ClinicalContext]:
    """Get clinical background for a specific cancer subtype"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype]["clinical_context"]
    return None

def get_disease_name(subtype: str) -> str:
    """Get human-readable disease name"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype]["display_name"]
    return "Unknown Disease"

def get_recommended_drugs(subtype: str) -> List[TherapeuticRecommendation]:
    """Get recommended drugs for a specific cancer subtype"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype]["recommended_drugs"]
    return []

def get_design_rationale(subtype: str) -> List[str]:
    """Get design rationale for a specific cancer subtype"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype]["design_rationale"]
    return []

def get_tissue_barrier_analysis(subtype: str) -> Dict:
    """Get tissue barrier information for a specific cancer subtype"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype]["tissue_barriers"]
    return {}

def get_special_notes(subtype: str) -> Optional[Dict]:
    """Get special design notes for challenging cases"""
    if subtype in LIVER_CANCER_DATABASE:
        return LIVER_CANCER_DATABASE[subtype].get("special_notes")
    return None

def get_all_disease_info(subtype: str) -> Optional[Dict]:
    """Get complete information for a disease subtype"""
    return LIVER_CANCER_DATABASE.get(subtype)

# ============================================================
# HELPER: Format for Streamlit Display
# ============================================================

def format_np_params_for_display(params: NPDesignParameters) -> Dict:
    """Format NP parameters nicely for Streamlit display"""
    return {
        "Size Range": f"{params.size_nm_min}-{params.size_nm_max} nm (optimal: {params.size_nm_optimal} nm)",
        "Surface Charge": f"{params.surface_charge} ({params.charge_value})",
        "PEG Coating": f"{params.peg_coating_percent}%",
        "Targeting Ligand": params.targeting_ligand.value,
        "Drug Loading": f"{params.drug_loading_percent_min}-{params.drug_loading_percent_max}%",
        "Biodegradation": f"{params.biodegradation_hours_min}-{params.biodegradation_hours_max} hours"
    }

def format_clinical_context_for_display(context: ClinicalContext) -> Dict:
    """Format clinical context nicely for display"""
    return {
        "Prevalence": f"{context.prevalence_percent}% of HCC cases",
        "5-Year Survival": f"{context.five_year_survival_percent}%",
        "Growth Pattern": context.growth_pattern.upper(),
        "Vascularization": context.vascularization.upper(),
        "Median Size at Diagnosis": f"{context.median_size_at_diagnosis_cm} cm",
        "Median Progression Time": f"{context.median_time_to_progression_months} months"
    }
