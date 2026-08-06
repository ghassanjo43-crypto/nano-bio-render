"""
Confidence & Evidence Engine for NanoBio Studio
Meta-analysis of evidence quality and prediction confidence across all assessments
"""

from typing import Dict, List, Tuple
from models.scientific_assessment import (
    ConfidenceEvidenceProfile,
    EvidenceLevel,
    ConfidenceLevel,
    MechanisticPredictionResult,
    SafetyRiskProfile,
    DiseaseBiologyFit,
    ManufacturabilityProfile,
    RegulatoryAssessment,
    PredictionBasis,
)
from config.scoring_config import get_confidence_label


class ConfidenceEngine:
    """
    Meta-analysis of evidence level and confidence across all predictions.
    
    Distinguishes:
    - Evidence Level: Source of claim (user_specified → literature → predicted)
    - Confidence Level: Certainty in the claim (low/medium/high)
    - Performance Score: Actual numeric score on 0-100 scale
    
    A formulation might have:
    - HIGH performance score (user-specified encapsulation at 95%) but MEDIUM confidence
    - MEDIUM performance score but HIGH confidence (based on well-validated mechanistic model)
    """

    @staticmethod
    def calculate_confidence_profile(
        mechanistic_results: MechanisticPredictionResult,
        safety_results: SafetyRiskProfile,
        disease_fit: DiseaseBiologyFit,
        manufacturing_results: ManufacturabilityProfile,
        regulatory_assessment: RegulatoryAssessment,
    ) -> ConfidenceEvidenceProfile:
        """
        Comprehensive meta-analysis of evidence and confidence across all predictions.
        
        Returns:
            ConfidenceEvidenceProfile: Overall confidence assessment
        """
        
        # Analyze evidence level distribution
        evidence_distribution = ConfidenceEngine._analyze_evidence_distribution(
            mechanistic_results,
            safety_results,
            disease_fit,
            manufacturing_results,
            regulatory_assessment,
        )
        
        # Calculate per-component confidence scores
        component_confidences = ConfidenceEngine._calculate_component_confidences(
            mechanistic_results,
            safety_results,
            disease_fit,
            manufacturing_results,
        )
        
        # Calculate overall scientific confidence (separate from performance)
        overall_confidence = ConfidenceEngine._calculate_overall_confidence(
            component_confidences,
            evidence_distribution,
        )
        
        # Generate confidence decomposition narrative
        narrative = ConfidenceEngine._generate_confidence_narrative(
            evidence_distribution,
            component_confidences,
            overall_confidence,
        )
        
        # Identify confidence bottlenecks
        bottlenecks = ConfidenceEngine._identify_confidence_bottlenecks(
            component_confidences
        )
        
        # Recommendations for confidence improvement
        recommendations = ConfidenceEngine._recommend_confidence_improvements(
            evidence_distribution,
            bottlenecks,
        )
        
        # Confidence reliability assessment
        reliability = ConfidenceEngine._assess_reliability(
            evidence_distribution,
            component_confidences,
        )
        
        return ConfidenceEvidenceProfile(
            overall_scientific_confidence=overall_confidence,
            evidence_level_distribution=evidence_distribution,
            confidence_by_prediction_type=component_confidences,
            mechanistic_confidence=component_confidences.get("mechanistic", 0.70),
            safety_confidence=component_confidences.get("safety", 0.65),
            disease_fit_confidence=component_confidences.get("disease_fit", 0.60),
            manufacturing_confidence=component_confidences.get("manufacturing", 0.75),
            regulatory_confidence=component_confidences.get("regulatory", 0.62),
            predictions_with_high_confidence=[
                k for k, v in component_confidences.items() if v >= 0.75
            ],
            predictions_with_low_confidence=[
                k for k, v in component_confidences.items() if v < 0.60
            ],
            confidence_limiting_factors=bottlenecks,
            recommended_confidence_improvements=recommendations,
            confidence_reliability_score=reliability,
            detailed_narrative=narrative,
        )

    @staticmethod
    def _analyze_evidence_distribution(
        mechanistic_results: MechanisticPredictionResult,
        safety_results: SafetyRiskProfile,
        disease_fit: DiseaseBiologyFit,
        manufacturing_results: ManufacturabilityProfile,
        regulatory_assessment: RegulatoryAssessment,
    ) -> Dict[str, float]:
        """
        Analyze how evidence is distributed across levels.
        Returns percentage of claims at each evidence level.
        """
        
        evidence_counts = {
            "user_specified": 0,
            "inferred": 0,
            "literature_supported": 0,
            "experimentally_validated": 0,
            "predicted": 0,
        }
        
        # Collect all predictions with their evidence levels
        all_predictions = [
            mechanistic_results.delivery_efficacy,
            mechanistic_results.toxicity_safety,
            mechanistic_results.manufacturability,
            mechanistic_results.storage_stability,
            mechanistic_results.targeting_efficacy,
            mechanistic_results.payload_release,
        ]
        
        # Count evidence levels
        total_predictions = len(all_predictions)
        for pred in all_predictions:
            if hasattr(pred, 'basis'):
                if "mechanistic" in pred.basis.lower():
                    evidence_counts["literature_supported"] += 1
                elif "predictive" in pred.basis.lower():
                    evidence_counts["predicted"] += 1
                elif "empirical" in pred.basis.lower():
                    evidence_counts["literature_supported"] += 1
        
        # Normalize to percentages
        distribution = {}
        for level, count in evidence_counts.items():
            distribution[level] = (count / total_predictions * 100.0) if total_predictions > 0 else 0.0
        
        return distribution

    @staticmethod
    def _calculate_component_confidences(
        mechanistic_results: MechanisticPredictionResult,
        safety_results: SafetyRiskProfile,
        disease_fit: DiseaseBiologyFit,
        manufacturing_results: ManufacturabilityProfile,
    ) -> Dict[str, float]:
        """
        Calculate confidence score for each major prediction type.
        
        Returns:
            Dict: {prediction_type: confidence_score (0.0-1.0)}
        """
        
        # Mechanistic predictions: average of 6 base predictions
        mechanistic_scores = [
            mechanistic_results.delivery_efficacy.numeric_confidence,
            mechanistic_results.toxicity_safety.numeric_confidence,
            mechanistic_results.manufacturability.numeric_confidence,
            mechanistic_results.storage_stability.numeric_confidence,
            mechanistic_results.targeting_efficacy.numeric_confidence,
            mechanistic_results.payload_release.numeric_confidence,
        ]
        mechanistic_conf = sum(mechanistic_scores) / len(mechanistic_scores) if mechanistic_scores else 0.70
        
        # Safety confidence (based on risk profile completeness)
        # Lower if high-risk components present
        high_risk_count = 0
        safety_components = [
            safety_results.systemic_toxicity,
            safety_results.immunogenicity,
            safety_results.off_target_effects,
            safety_results.aggregation_risk,
            safety_results.premature_payload_release,
            safety_results.metabolic_burden,
        ]
        
        for comp in safety_components:
            if comp and comp.risk_band in ["High", "Critical"]:
                high_risk_count += 1
        
        safety_conf = safety_results.numeric_confidence
        if high_risk_count > 0:
            # Reduce confidence for high-risk components
            safety_conf *= (1.0 - (high_risk_count / len(safety_components) * 0.2))
        
        # Disease fit confidence
        disease_conf = disease_fit.numeric_confidence
        
        # Manufacturing confidence (based on complexity score)
        mfg_complexity = 100.0 - manufacturing_results.overall_manufacturability_score
        if mfg_complexity > 70:
            manufacturing_conf = manufacturing_results.numeric_confidence * 0.80
        else:
            manufacturing_conf = manufacturing_results.numeric_confidence
        
        return {
            "mechanistic": mechanistic_conf,
            "safety": safety_conf,
            "disease_fit": disease_conf,
            "manufacturing": manufacturing_conf,
            "regulatory": 0.62,  # Regulatory inherently lower confidence
        }

    @staticmethod
    def _calculate_overall_confidence(
        component_confidences: Dict[str, float],
        evidence_distribution: Dict[str, float],
    ) -> float:
        """
        Calculate overall scientific confidence score.
        
        Weighs components and penalizes if evidence is mostly predicted/inferred.
        """
        
        # Weight major components
        weights = {
            "mechanistic": 0.30,
            "safety": 0.30,
            "disease_fit": 0.20,
            "manufacturing": 0.15,
            "regulatory": 0.05,
        }
        
        weighted_conf = sum(
            component_confidences.get(comp, 0.5) * weights.get(comp, 0.1)
            for comp in component_confidences.keys()
        )
        
        # Apply evidence quality penalty
        predicted_pct = evidence_distribution.get("predicted", 0.0)
        inferred_pct = evidence_distribution.get("inferred", 0.0)
        
        # If >70% predictions are inferred or predicted, reduce overall confidence
        low_quality_evidence_pct = predicted_pct + inferred_pct
        if low_quality_evidence_pct > 70:
            evidence_penalty = 0.15 * (low_quality_evidence_pct / 100.0)
            weighted_conf *= (1.0 - evidence_penalty)
        
        # Cap at 0-1 range
        return max(0.0, min(1.0, weighted_conf))

    @staticmethod
    def _identify_confidence_bottlenecks(component_confidences: Dict[str, float]) -> List[str]:
        """
        Identify which components have lowest confidence.
        Returns list of bottleneck components.
        """
        
        bottlenecks = []
        
        # Find components with confidence < 0.70
        for component, confidence in sorted(component_confidences.items(), key=lambda x: x[1]):
            if confidence < 0.70:
                bottlenecks.append(
                    f"{component}: {confidence*100:.0f}% confidence (below 70% target)"
                )
            if len(bottlenecks) >= 3:
                break
        
        if not bottlenecks:
            bottlenecks.append("All components above 70% confidence threshold - confidence profile acceptable")
        
        return bottlenecks

    @staticmethod
    def _recommend_confidence_improvements(
        evidence_distribution: Dict[str, float],
        bottlenecks: List[str],
    ) -> List[str]:
        """
        Recommend studies/analyses to improve confidence.
        """
        
        recommendations = []
        
        # If any bottleneck, recommend targeted studies
        if bottlenecks and "acceptable" not in bottlenecks[0]:
            recommendations.append(
                "Perform targeted in vitro studies on lowest-confidence components"
            )
        
        # If mostly predicted/inferred evidence
        predicted_pct = evidence_distribution.get("predicted", 0.0) + evidence_distribution.get("inferred", 0.0)
        if predicted_pct > 70:
            recommendations.append(
                f"Evidence basis is {predicted_pct:.0f}% mechanistic/computational; "
                + "recommend validation studies (in vitro cell assays, animal models)"
            )
        
        # If no literature-supported evidence
        lit_support = evidence_distribution.get("literature_supported", 0.0)
        if lit_support < 20:
            recommendations.append(
                "Limited literature-supported evidence; conduct targeted literature review or "
                + "comparative formulation studies"
            )
        
        # Safety-specific
        recommendations.append(
            "Conduct GLP-quality toxicology studies (required for regulatory submission)"
        )
        
        # Manufacturing-specific
        recommendations.append(
            "Perform batch consistency studies (3-5 production batches); "
            + "establish robust quality control specifications"
        )
        
        # Disease-specific
        recommendations.append(
            "Validate targeting strategy in disease-relevant model; confirm target expression "
            + "in patient samples"
        )
        
        return recommendations

    @staticmethod
    def _assess_reliability(
        evidence_distribution: Dict[str, float],
        component_confidences: Dict[str, float],
    ) -> float:
        """
        Assess how reliable the confidence assessment itself is.
        
        Lower if:
        - High variance in component confidences
        - Mostly low-quality evidence
        - Key data missing
        """
        
        # Component confidence variance
        conf_values = list(component_confidences.values())
        mean_conf = sum(conf_values) / len(conf_values) if conf_values else 0.65
        variance = sum((c - mean_conf) ** 2 for c in conf_values) / len(conf_values) if conf_values else 0.0
        std_dev = variance ** 0.5
        
        # High variance (>0.15) reduces reliability
        reliability = 0.85
        if std_dev > 0.15:
            reliability -= 0.15 * (std_dev / 0.15)
        
        # Evidence quality impact
        low_quality_pct = evidence_distribution.get("predicted", 0.0) + evidence_distribution.get("inferred", 0.0)
        if low_quality_pct > 70:
            reliability -= 0.20
        
        return max(0.5, min(1.0, reliability))

    @staticmethod
    def _generate_confidence_narrative(
        evidence_distribution: Dict[str, float],
        component_confidences: Dict[str, float],
        overall_confidence: float,
    ) -> str:
        """
        Generate comprehensive confidence analysis narrative.
        """
        
        lines = [
            "CONFIDENCE & EVIDENCE ANALYSIS",
            "=" * 70,
            "",
            f"Overall Scientific Confidence: {overall_confidence*100:.0f}%",
            "",
        ]
        
        # Interpret confidence level
        if overall_confidence >= 0.75:
            lines.append(
                "ASSESSMENT: HIGH CONFIDENCE - Formulation design based on solid mechanistic "
                + "principles with good evidence support"
            )
        elif overall_confidence >= 0.60:
            lines.append(
                "ASSESSMENT: MODERATE CONFIDENCE - Design is scientifically sound but relies on "
                + "predictions; validation studies recommended"
            )
        else:
            lines.append(
                "ASSESSMENT: LOWER CONFIDENCE - Design requires validation; consider design "
                + "modifications or additional characterization"
            )
        
        lines.extend([
            "",
            "EVIDENCE LEVEL DISTRIBUTION:",
            f"  • User-Specified: {evidence_distribution.get('user_specified', 0):.0f}%",
            f"  • Inferred: {evidence_distribution.get('inferred', 0):.0f}%",
            f"  • Literature-Supported: {evidence_distribution.get('literature_supported', 0):.0f}%",
            f"  • Experimentally Validated: {evidence_distribution.get('experimentally_validated', 0):.0f}%",
            f"  • Predicted: {evidence_distribution.get('predicted', 0):.0f}%",
            "",
            "COMPONENT-SPECIFIC CONFIDENCE:",
        ])
        
        for component, confidence in sorted(component_confidences.items(), key=lambda x: x[1], reverse=True):
            conf_pct = f"{confidence*100:.0f}%"
            if confidence >= 0.75:
                rating = "HIGH"
            elif confidence >= 0.60:
                rating = "MODERATE"
            else:
                rating = "LOWER"
            
            lines.append(f"  • {component}: {conf_pct} ({rating})")
        
        lines.extend([
            "",
            "INTERPRETATION:",
            "Confidence reflects certainty in predicted performance, not performance magnitude.",
            "A formulation might have:",
            "  • High performance score (95%) + Moderate confidence (if user-specified)",
            "  • Moderate performance score (65%) + High confidence (if well-validated mechanism)",
            "",
            "Confidence improves with: in vitro validation, literature support, mechanistic clarity",
            "Confidence diminishes with: predictions, novel combinations, high-risk components",
        ])
        
        return "\n".join(lines)
