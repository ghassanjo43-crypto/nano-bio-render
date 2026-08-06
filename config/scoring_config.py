"""
Scoring Configuration for NanoBio Studio
Centralized weights, thresholds, and scoring methodology
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class ScoringWeights:
    """Weights for overall score calculation"""
    delivery_weight: float = 0.35
    safety_weight: float = 0.25
    manufacturability_weight: float = 0.20
    disease_fit_weight: float = 0.15
    stability_weight: float = 0.05

    def validate(self) -> bool:
        """Ensure weights sum to 1.0"""
        total = (self.delivery_weight + self.safety_weight +
                self.manufacturability_weight + self.disease_fit_weight +
                self.stability_weight)
        return abs(total - 1.0) < 0.01


@dataclass
class ConfidenceThresholds:
    """Thresholds for confidence classification"""
    high_confidence_min: float = 0.75
    medium_confidence_min: float = 0.50
    low_confidence_max: float = 0.49


@dataclass
class PerformanceScoreBands:
    """Score bands for performance levels"""
    excellent_min: int = 85
    good_min: int = 75
    acceptable_min: int = 65
    requires_revision_min: int = 0
    requires_revision_max: int = 64


@dataclass
class DeliveryEfficacyModel:
    """Parameters for delivery efficiency prediction"""
    optimal_size_min_nm: float = 80.0
    optimal_size_max_nm: float = 150.0
    size_penalty_factor: float = 0.8
    peg_density_importance: float = 0.35
    charge_importance: float = 0.25
    size_importance: float = 0.40
    encapsulation_importance: float = 0.15


@dataclass
class ToxicityModel:
    """Parameters for toxicity prediction"""
    base_toxicity_score: float = 3.0
    size_toxicity_factor: float = 0.01
    charge_toxicity_factor: float = 0.05
    encapsulation_effect: float = 0.8
    peg_protective_factor: float = 0.6


@dataclass
class ManufacturabilityModel:
    """Parameters for manufacturability assessment"""
    size_control_difficulty_threshold: float = 50.0
    consistency_target_cv_percent: float = 5.0
    encapsulation_difficulty_threshold: float = 90.0
    batch_reproducibility_penalty: float = 0.15
    storage_stability_penalty: float = 0.10


@dataclass
class DiseaseFilModel:
    """Parameters for disease-fit assessment"""
    size_fit_importance: float = 0.30
    charge_fit_importance: float = 0.20
    targeting_fit_importance: float = 0.25
    formulation_fit_importance: float = 0.25


# Default configuration
DEFAULT_SCORING_WEIGHTS = ScoringWeights()
DEFAULT_CONFIDENCE_THRESHOLDS = ConfidenceThresholds()
DEFAULT_PERFORMANCE_BANDS = PerformanceScoreBands()
DEFAULT_DELIVERY_MODEL = DeliveryEfficacyModel()
DEFAULT_TOXICITY_MODEL = ToxicityModel()
DEFAULT_MANUFACTURABILITY_MODEL = ManufacturabilityModel()
DEFAULT_DISEASE_FIT_MODEL = DiseaseFilModel()


def get_confidence_label(confidence_score: float) -> str:
    """Convert numeric confidence to label"""
    thresholds = DEFAULT_CONFIDENCE_THRESHOLDS
    if confidence_score >= thresholds.high_confidence_min:
        return "high"
    elif confidence_score >= thresholds.medium_confidence_min:
        return "medium"
    else:
        return "low"


def get_performance_label(score: float) -> str:
    """Convert numeric score to performance label"""
    bands = DEFAULT_PERFORMANCE_BANDS
    if score >= bands.excellent_min:
        return "Excellent"
    elif score >= bands.good_min:
        return "Good"
    elif score >= bands.acceptable_min:
        return "Acceptable"
    else:
        return "Requires Revision"
