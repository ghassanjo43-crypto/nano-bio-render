"""
Scientific Assessment Models for NanoBio Studio
Comprehensive dataclasses for rigorous scientific reporting
Aligned with mechanistic engines and transparency requirements
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


# ========== ENUMERATIONS ==========

class EvidenceLevel(str, Enum):
    """Classification of evidence basis for predictions"""
    USER_SPECIFIED = "user_specified"
    INFERRED = "inferred"
    LITERATURE_SUPPORTED = "literature_supported"
    EXPERIMENTALLY_VALIDATED = "experimentally_validated"
    PREDICTED = "predicted"


class ConfidenceLevel(str, Enum):
    """Confidence classification for predictions"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RegulatoryStage(str, Enum):
    """Development stage for regulatory positioning"""
    CONCEPT = "concept"
    IN_SILICO_DESIGN = "in_silico_design"
    FORMULATION_SCREENING = "formulation_screening"
    PRECLINICAL_CANDIDATE = "preclinical_candidate"
    REGULATORY_ENABLING = "regulatory_enabling"
    CLINICAL_PHASE_I = "clinical_phase_i"
    CLINICAL_PHASE_II = "clinical_phase_ii"
    CLINICAL_PHASE_III = "clinical_phase_iii"


# ========== INPUT & DESIGN DATACLASSES ==========

@dataclass
class TrialDesignInputs:
    """
    Structured trial design inputs
    Core formulation parameters specified by user or inferred
    """
    case_id: str
    disease_code: str
    trial_name: str = ""
    trial_description: str = ""
    
    # Nanoparticle properties
    nanoparticle_size_nm: float = 100.0
    surface_charge_mv: float = 0.0
    peg_surface_coating: bool = False
    peg_density_percent: float = 0.0
    
    # Encapsulation & drug
    encapsulation_method: str = "passive_loading"
    payload_drug: str = ""
    payload_loading_percent: float = 0.0
    
    # Targeting
    targeting_ligand: str = "None"
    
    # Manufacturing context
    manufacturing_scale_target: str = "mg"  # mg, g, kg, etc.
    notes: str = ""


@dataclass
class FormulationArchitecture:
    """
    Detailed nanoparticle design breakdown
    """
    platform_type: str = "polymeric"
    core_material: str = ""
    shell_material: str = ""
    surface_modifications: List[str] = field(default_factory=list)
    peg_grafting_density: float = 0.0
    ligands_per_particle: float = 0.0
    composition_details: Dict[str, float] = field(default_factory=dict)


@dataclass
class PredictionBasis:
    """
    Transparent explanation of prediction methodology
    """
    value: float  # 0-100 typically
    basis: str  # e.g., "mechanistic_physics_principles", "empirical_literature"
    rationale: str  # Human-readable explanation
    assumptions: List[str] = field(default_factory=list)
    confidence_level: str = "medium"  # low, medium, high
    numeric_confidence: float = 0.65  # 0-1scale


@dataclass
class MechanisticPredictionResult:
    """
    6 core mechanistic predictions with full transparency
    """
    delivery_efficacy: PredictionBasis
    toxicity_safety: PredictionBasis
    manufacturability: PredictionBasis
    storage_stability: PredictionBasis
    targeting_efficacy: PredictionBasis
    payload_release: PredictionBasis


@dataclass
class DiseaseBiologyFit:
    """
    Disease-specific biological fit assessment
    """
    disease_name: str
    overall_fit_score: float  # 0-100
    barrier_mitigation_scores: Dict[str, float] = field(default_factory=dict)
    barrier_rationales: Dict[str, str] = field(default_factory=dict)
    size_appropriateness: str = ""
    charge_appropriateness: str = ""
    targeting_strategy_fit: str = ""
    formulation_approach_fit: str = ""
    critical_mismatches: List[str] = field(default_factory=list)
    detailed_rationale: str = ""
    assumptions: List[str] = field(default_factory=list)
    confidence_level: str = "medium"
    numeric_confidence: float = 0.70

    # --- Verdict calibration status (Step 1, DECISION 6) --------------------
    # `overall_fit_score` and `barrier_mitigation_scores` above remain VALID
    # computed values and are still returned (DECISION 6.7). What is withheld is
    # any favourable/unfavourable *verdict* derived from the uncalibrated >70
    # threshold. These fields keep the two clearly separated.

    #: False while the favourable-verdict threshold is uncalibrated.
    verdict_available: bool = False
    verdict_status: str = "calibration_required"
    verdict_status_detail: str = ""

    #: The threshold the score would have to cross, recorded for transparency.
    favourable_verdict_threshold: Optional[float] = None

    #: Highest score observed across an exhaustive parameter sweep. Documents that
    #: the threshold is unreachable under the current model.
    observed_model_ceiling: Optional[float] = None


@dataclass
class AIModelTransparency:
    """
    Explanation of AI model basis and limitations
    """
    model_basis: str = ""
    prediction_basis_for_each_module: List[str] = field(default_factory=list)
    calibration_data_source: str = ""
    model_performance_on_known_systems: str = ""
    limitations_of_ai_predictions: List[str] = field(default_factory=list)
    input_sensitivity: str = ""
    recommendation: str = ""


@dataclass
class SafetyRiskComponent:
    """
    Individual safety risk assessment
    """
    component_name: str
    risk_score: float  # 0-100, higher = more risk
    risk_band: str  # Critical, High, Moderate, Low, Minimal
    primary_drivers: Dict[str, float] = field(default_factory=dict)
    rationale: str = ""
    mitigation_strategies: List[str] = field(default_factory=list)


@dataclass
class SafetyRiskProfile:
    """
    6-component safety decomposition
    """
    overall_safety_score: float  # 0-100, higher is safer
    systemic_toxicity: SafetyRiskComponent = field(default_factory=lambda: SafetyRiskComponent("systemic_toxicity", 50.0, "Moderate"))
    immunogenicity: SafetyRiskComponent = field(default_factory=lambda: SafetyRiskComponent("immunogenicity", 50.0, "Moderate"))
    off_target_effects: SafetyRiskComponent = field(default_factory=lambda: SafetyRiskComponent("off_target_effects", 50.0, "Moderate"))
    aggregation_risk: SafetyRiskComponent = field(default_factory=lambda: SafetyRiskComponent("aggregation_risk", 50.0, "Moderate"))
    premature_payload_release: SafetyRiskComponent = field(default_factory=lambda: SafetyRiskComponent("premature_payload_release", 50.0, "Moderate"))
    metabolic_burden: SafetyRiskComponent = field(default_factory=lambda: SafetyRiskComponent("metabolic_burden", 50.0, "Moderate"))
    risk_summary_narrative: str = ""
    highest_risk_component: str = ""
    mitigation_priorities: List[SafetyRiskComponent] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    confidence_level: str = "medium"
    numeric_confidence: float = 0.68


@dataclass
class ManufacturabilityProfile:
    """
    Manufacturing feasibility and complexity assessment
    """
    overall_manufacturability_score: float  # 0-100, higher = easier
    size_control_difficulty: float = 50.0
    process_complexity_score: float = 50.0
    qc_complexity_score: float = 50.0
    scale_up_risk_score: float = 50.0
    estimated_cost_per_dose_usd: float = 0.0
    batch_consistency_prediction: float = 8.0  # CV %
    primary_manufacturing_risks: List[Tuple[str, float, str]] = field(default_factory=list)
    batch_cycle_time_days: float = 5.0
    gmp_pathway_readiness: str = ""
    critical_process_parameters: List[str] = field(default_factory=list)
    manufacturing_roadmap: str = ""
    detailed_rationale: str = ""
    assumptions: List[str] = field(default_factory=list)
    confidence_level: str = "medium"
    numeric_confidence: float = 0.75


@dataclass
class RegulatoryAssessment:
    """
    Regulatory positioning with evidence-appropriate language
    """
    current_regulatory_stage: str
    proposed_regulatory_pathway: List[Tuple[str, List[str]]] = field(default_factory=list)
    regulatory_category: str = ""
    primary_regulatory_strategy: str = ""
    key_regulatory_assertions: List[Tuple[str, str, float]] = field(default_factory=list)
    critical_regulatory_risks: List[str] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)
    unmet_regulatory_needs: List[str] = field(default_factory=list)
    recommended_next_studies: List[str] = field(default_factory=list)
    quality_overall_summary: str = ""
    nonclinical_summary: str = ""
    clinical_strategy: str = ""
    detailed_regulatory_narrative: str = ""
    assumptions: List[str] = field(default_factory=list)
    confidence_level: str = "low"
    numeric_confidence: float = 0.62

    # --- Provenance and calibration status (Step 1, DECISION 5 & 6) ----------
    # Added with defaults so existing consumers are unaffected.

    #: Version of the regulatory calculation that produced this assessment.
    calculation_version: str = "unknown"

    #: Rule-based manufacturing complexity indicator, integer 0-2 (DECISION 5).
    #: NOT validated manufacturability, NOT a regulatory approval probability,
    #: NOT evidence of production success.
    manufacturing_complexity: Optional[int] = None
    manufacturing_complexity_basis: str = ""

    #: DECISION 6: False while the favourable disease-fit verdict is disabled
    #: pending a scientifically reviewed calibration decision. Component and fit
    #: scores remain available and valid; only the *verdict* is withheld.
    verdict_available: bool = False
    verdict_status: str = "calibration_required"
    verdict_status_detail: str = ""


@dataclass
class ReportLimitations:
    """
    Comprehensive documentation of report limitations
    """
    data_limitations: List[str] = field(default_factory=list)
    model_limitations: List[str] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)
    regulatory_caveats: List[str] = field(default_factory=list)
    assumption_risks: List[str] = field(default_factory=list)
    not_addressed: List[str] = field(default_factory=list)


@dataclass
class ConfidenceEvidenceProfile:
    """
    Meta-analysis of confidence and evidence across predictions
    """
    overall_scientific_confidence: float = 0.65  # 0-1 scale
    evidence_level_distribution: Dict[str, float] = field(default_factory=dict)
    confidence_by_prediction_type: Dict[str, float] = field(default_factory=dict)
    mechanistic_confidence: float = 0.70
    safety_confidence: float = 0.65
    disease_fit_confidence: float = 0.60
    manufacturing_confidence: float = 0.75
    regulatory_confidence: float = 0.62
    predictions_with_high_confidence: List[str] = field(default_factory=list)
    predictions_with_low_confidence: List[str] = field(default_factory=list)
    confidence_limiting_factors: List[str] = field(default_factory=list)
    recommended_confidence_improvements: List[str] = field(default_factory=list)
    confidence_reliability_score: float = 0.75
    detailed_narrative: str = ""


@dataclass
class ScientificReport:
    """
    Complete scientific report container
    Aggregates all assessment components
    """
    report_id: str
    generated_at: str
    disease_profile: Optional[object] = None  # DiseaseProfile object
    trial_design_inputs: Optional[TrialDesignInputs] = None
    mechanistic_predictions: Optional[MechanisticPredictionResult] = None
    disease_biology_fit: Optional[DiseaseBiologyFit] = None
    safety_risk_profile: Optional[SafetyRiskProfile] = None
    manufacturability_assessment: Optional[ManufacturabilityProfile] = None
    regulatory_assessment: Optional[RegulatoryAssessment] = None
    confidence_evidence_profile: Optional[ConfidenceEvidenceProfile] = None
    ai_model_transparency: Optional[AIModelTransparency] = None
    report_limitations: Optional[ReportLimitations] = None
    overall_scientific_quality_score: float = 0.0
    report_mode: str = "scientific_full"  # scientific_full, investor_summary, technical_appendix
    
    def is_complete(self) -> bool:
        """Check if all major sections populated"""
        return all([
            self.trial_design_inputs,
            self.mechanistic_predictions,
            self.disease_biology_fit,
            self.safety_risk_profile,
            self.manufacturability_assessment,
            self.regulatory_assessment,
            self.confidence_evidence_profile,
        ])
    
    def completeness_percentage(self) -> float:
        """Calculate report completeness as percentage"""
        required = [
            self.trial_design_inputs,
            self.mechanistic_predictions,
            self.disease_biology_fit,
            self.safety_risk_profile,
            self.manufacturability_assessment,
            self.regulatory_assessment,
            self.confidence_evidence_profile,
        ]
        completed = sum(1 for item in required if item is not None)
        return (completed / len(required) * 100) if required else 0.0
