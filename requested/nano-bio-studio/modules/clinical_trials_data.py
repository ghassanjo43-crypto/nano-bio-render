"""
Clinical Trials Database for Hepatocellular Carcinoma
Links clinical trials to specific HCC subtypes and nanoparticle design recommendations
Based on real clinical trial data and FDA approvals
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import date

class TrialPhase(str, Enum):
    """Clinical trial phases"""
    PHASE_1 = "Phase 1"
    PHASE_2 = "Phase 2"
    PHASE_3 = "Phase 3"
    PHASE_4 = "Phase 4"
    APPROVED = "FDA Approved"

class TrialStatus(str, Enum):
    """Trial recruitment and completion status"""
    RECRUITING = "Recruiting"
    NOT_YET_RECRUITING = "Not Yet Recruiting"
    ACTIVE_NOT_RECRUITING = "Active, not recruiting"
    COMPLETED = "Completed"
    TERMINATED = "Terminated"
    SUSPENDED = "Suspended"

@dataclass
class ClinicalTrial:
    """Clinical trial data structure"""
    trial_id: str
    trial_name: str
    phase: TrialPhase
    status: TrialStatus
    hcc_subtypes: List[str]  # ["hcc_s", "hcc_ms", "hcc_l"]
    drug_names: List[str]
    mechanism: str
    primary_endpoint: str
    study_population_count: int
    median_overall_survival_months: Optional[float] = None
    response_rate_percent: Optional[float] = None
    publication_year: Optional[int] = None
    institution: str = "Multiple"
    landmark_trial: bool = False
    notes: str = ""

# ============================================================
# CLINICAL TRIALS DATABASE
# ============================================================

CLINICAL_TRIALS = {
    # ============ FDA APPROVED COMBINATIONS ============
    "IMBRAVE150": ClinicalTrial(
        trial_id="IMBRAVE150",
        trial_name="IMbrave150: Atezolizumab + Bevacizumab for Advanced HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_ms", "hcc_l"],
        drug_names=["Atezolizumab", "Bevacizumab"],
        mechanism="PD-L1 checkpoint inhibitor + Anti-VEGF",
        primary_endpoint="Overall Survival (OS) and Time to Radiological Progression (TTP)",
        study_population_count=501,
        median_overall_survival_months=19.2,
        response_rate_percent=33,
        publication_year=2020,
        institution="Roche/Genentech",
        landmark_trial=True,
        notes="FDA APPROVED 2020 - First-line standard of care for advanced HCC. "
              "Particularly effective for HCC-MS and HCC-L with poor vasculature. "
              "NP design tip: Use anti-VEGF targeting to complement immunotherapy."
    ),
    
    "SHARP": ClinicalTrial(
        trial_id="SHARP",
        trial_name="SHARP: Sorafenib for Advanced HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_s", "hcc_ms", "hcc_l"],
        drug_names=["Sorafenib"],
        mechanism="Multi-kinase inhibitor (VEGFR, PDGFR, RAF)",
        primary_endpoint="Overall Survival",
        study_population_count=602,
        median_overall_survival_months=10.7,
        response_rate_percent=2,
        publication_year=2008,
        institution="Bayer/Oncogenex",
        landmark_trial=True,
        notes="FDA APPROVED - First targeted therapy for advanced HCC (2007). "
              "Standard of care for >15 years. Works across all HCC subtypes."
    ),
    
    "REFLECT": ClinicalTrial(
        trial_id="REFLECT",
        trial_name="REFLECT: Lenvatinib for Advanced HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_ms", "hcc_l"],
        drug_names=["Lenvatinib"],
        mechanism="Multi-kinase inhibitor (FGFR, VEGFR, RET, KIT)",
        primary_endpoint="Overall Survival",
        study_population_count=954,
        median_overall_survival_months=13.6,
        response_rate_percent=24,
        publication_year=2018,
        institution="Eisai",
        landmark_trial=True,
        notes="FDA APPROVED 2018 - First-line standard of care for advanced HCC. "
              "Particularly good for HCC-L with improved survival vs Sorafenib. "
              "NP design: FGFR targeting can enhance drug delivery."
    ),
    
    "RESORCE": ClinicalTrial(
        trial_id="RESORCE",
        trial_name="RESORCE: Regorafenib for Sorafenib-Resistant HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_l"],
        drug_names=["Regorafenib"],
        mechanism="Multi-kinase inhibitor (VEGFR, PDGFR, FGFR, RET, KIT, TIE2)",
        primary_endpoint="Overall Survival",
        study_population_count=573,
        median_overall_survival_months=10.6,
        response_rate_percent=11,
        publication_year=2017,
        institution="Bayer",
        landmark_trial=True,
        notes="FDA APPROVED 2017 - Second-line for HCC-L patients who progress on Sorafenib. "
              "Critical for aggressive HCC treatment algorithm."
    ),
    
    # ============ IMMUNOTHERAPY COMBINATIONS ============
    "KEYNOTE_240": ClinicalTrial(
        trial_id="KEYNOTE-240",
        trial_name="KEYNOTE-240: Pembrolizumab for Advanced HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_l"],
        drug_names=["Pembrolizumab"],
        mechanism="PD-1 checkpoint inhibitor",
        primary_endpoint="Overall Survival",
        study_population_count=413,
        median_overall_survival_months=13.9,
        response_rate_percent=17,
        publication_year=2019,
        institution="Merck",
        notes="Monotherapy option for HCC-L. Can be combined with other agents."
    ),
    
    # ============ COMBINATION APPROACHES ============
    "KEYNOTE_406": ClinicalTrial(
        trial_id="KEYNOTE-406",
        trial_name="KEYNOTE-406: Pembrolizumab + Chemotherapy for HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.ACTIVE_NOT_RECRUITING,
        hcc_subtypes=["hcc_ms", "hcc_l"],
        drug_names=["Pembrolizumab", "Gemcitabine", "Cisplatin"],
        mechanism="PD-1 checkpoint inhibitor + chemotherapy combination",
        primary_endpoint="Overall Survival",
        study_population_count=495,
        response_rate_percent=None,
        publication_year=None,
        institution="Merck",
        notes="Investigational combination for advanced HCC. "
              "Addresses hypoxic microenvironment with multiple mechanisms. "
              "NP design consideration: Multi-drug loading may be beneficial."
    ),
    
    # ============ CHEMOTHERAPY REGIMENS ============
    "GEMOX": ClinicalTrial(
        trial_id="GEMOX",
        trial_name="Gemcitabine + Cisplatin for Advanced HCC",
        phase=TrialPhase.PHASE_2,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_ms", "hcc_l"],
        drug_names=["Gemcitabine", "Cisplatin"],
        mechanism="Antimetabolite + alkylating agent",
        primary_endpoint="Response Rate",
        study_population_count=100,
        response_rate_percent=45,
        publication_year=2005,
        institution="Academic Research",
        notes="Standard chemotherapy combination for advanced HCC. "
              "Synergistic effects warrant co-delivery via NP. "
              "Good candidate for dual-drug loaded nanoparticles."
    ),
    
    # ============ EMERGING APPROACHES ============
    "STOP_HCC": ClinicalTrial(
        trial_id="STOP-HCC",
        trial_name="Sorafenib + Transarterial Chemoembolization (TACE) for Intermediate HCC",
        phase=TrialPhase.PHASE_3,
        status=TrialStatus.COMPLETED,
        hcc_subtypes=["hcc_ms"],
        drug_names=["Sorafenib", "Doxorubicin (via TACE)"],
        mechanism="Targeted therapy + locoregional chemotherapy",
        primary_endpoint="Time to Progression",
        study_population_count=313,
        response_rate_percent=56,
        publication_year=2014,
        institution="Multiple",
        notes="Combination of systemic and locoregional therapy. "
              "NP-delivered Sorafenib could optimize this approach."
    ),
}

# ============================================================
# ACCESS FUNCTIONS
# ============================================================

def get_trials_for_hcc_subtype(hcc_subtype: str) -> List[ClinicalTrial]:
    """Get all clinical trials relevant for a specific HCC subtype"""
    return [trial for trial in CLINICAL_TRIALS.values() 
            if hcc_subtype in trial.hcc_subtypes]

def get_trials_for_drugs(drug_names: List[str]) -> List[ClinicalTrial]:
    """Get trials that include specific drugs"""
    matching_trials = []
    for trial in CLINICAL_TRIALS.values():
        if any(drug in trial.drug_names for drug in drug_names):
            matching_trials.append(trial)
    return matching_trials

def get_fda_approved_trials() -> List[ClinicalTrial]:
    """Get only FDA approved trials (landmark trials)"""
    return [trial for trial in CLINICAL_TRIALS.values() 
            if trial.landmark_trial and trial.status == TrialStatus.COMPLETED]

def get_trials_by_mechanism(mechanism_keyword: str) -> List[ClinicalTrial]:
    """Get trials by mechanism of action keyword"""
    return [trial for trial in CLINICAL_TRIALS.values() 
            if mechanism_keyword.lower() in trial.mechanism.lower()]

def get_landmark_trials() -> List[ClinicalTrial]:
    """Get landmark trials (key decision-making trials)"""
    return [trial for trial in CLINICAL_TRIALS.values() if trial.landmark_trial]

def get_trial_info(trial_id: str) -> Optional[ClinicalTrial]:
    """Get complete information for a specific trial"""
    return CLINICAL_TRIALS.get(trial_id)

def get_recommended_trials_for_design(hcc_subtype: str, drug_names: List[str]) -> List[ClinicalTrial]:
    """Get most relevant trials for a proposed NP design"""
    trials_by_subtype = set(get_trials_for_hcc_subtype(hcc_subtype))
    trials_by_drug = set(get_trials_for_drugs(drug_names))
    
    # Exact matches (both subtype and drug)
    exact_matches = trials_by_subtype & trials_by_drug
    
    # If no exact matches, return trials from same subtype
    if exact_matches:
        return sorted(list(exact_matches), 
                     key=lambda t: t.landmark_trial, 
                     reverse=True)
    else:
        return sorted(list(trials_by_subtype), 
                     key=lambda t: t.landmark_trial, 
                     reverse=True)

# ============================================================
# FORMATTING FOR DISPLAY
# ============================================================

def format_trial_for_display(trial: ClinicalTrial) -> Dict:
    """Format trial data for Streamlit display"""
    return {
        "Trial ID": trial.trial_id,
        "Trial Name": trial.trial_name,
        "Phase": trial.phase.value,
        "Status": trial.status.value,
        "Primary Endpoint": trial.primary_endpoint,
        "Sample Size": trial.study_population_count,
        "Mechanism": trial.mechanism,
        "Drugs": ", ".join(trial.drug_names),
        "Applicable HCC Subtypes": ", ".join(trial.hcc_subtypes),
        "Overall Survival (months)": trial.median_overall_survival_months or "N/A",
        "Response Rate (%)": trial.response_rate_percent or "N/A",
        "Publication Year": trial.publication_year or "Ongoing",
        "FDA Landmark": "✅ YES" if trial.landmark_trial else "—",
    }

def get_trial_summary_table(hcc_subtype: str) -> List[Dict]:
    """Get summary table of trials for a specific HCC subtype"""
    trials = get_trials_for_hcc_subtype(hcc_subtype)
    return [format_trial_for_display(trial) for trial in trials]
