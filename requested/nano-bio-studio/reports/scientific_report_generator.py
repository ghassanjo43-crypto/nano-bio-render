"""
Report Generator - Orchestrates all engines into complete scientific report
"""

from typing import Optional
from datetime import datetime
from models.scientific_assessment import (
    ScientificReport,
    TrialDesignInputs,
    MechanisticPredictionResult,
    DiseaseBiologyFit,
    SafetyRiskProfile,
    ManufacturabilityProfile,
    RegulatoryAssessment,
    ConfidenceEvidenceProfile,
    ReportLimitations,
    AIModelTransparency,
)
from config.disease_profiles import get_disease_profile, DiseaseProfile
from engine.mechanistic_engine import MechanisticEngine
from engine.disease_fit import DiseaseFilEngine
from engine.safety_engine import SafetyEngine
from engine.manufacturing_engine import ManufacturingEngine
from engine.regulatory_engine import RegulatoryEngine
from engine.confidence_engine import ConfidenceEngine


class ScientificReportGenerator:
    """
    Orchestrates all prediction engines into a unified, transparent scientific report.

    Scientific positioning
    ----------------------
    Every output is a computational research-planning result. Nothing in this
    report is experimentally validated, clinically validated, a regulatory
    approval prediction, a diagnosis, a treatment recommendation, or a substitute
    for wet-lab testing.

    Execution flow:
    1. Parse trial design inputs
    2. Initialize disease context
    3. Run mechanistic predictions
    4. Assess disease-fit
    5. Evaluate safety risks
    6. Assess manufacturability
    7. Position regulatory strategy
    8. Calculate confidence/evidence profile
    9. Generate limitations
    10. Assemble final ScientificReport
    """

    #: Text used when an engine does not declare a structured prediction basis.
    #: Deliberately states the absence rather than inventing one.
    NO_DECLARED_BASIS = (
        "prediction basis not declared as a structured field by {type_name}; "
        "see that module's assumptions list"
    )

    @staticmethod
    def _describe_prediction_basis(module_name: str, result: object) -> str:
        """Report a module's declared prediction basis, or say it has none.

        Only ``PredictionBasis`` declares a ``basis`` field. For the four modules
        that do not, no basis is fabricated -- the absence is reported explicitly.
        """
        basis = getattr(result, "basis", None)
        if isinstance(basis, str) and basis.strip():
            return f"{module_name}: {basis}"
        return f"{module_name}: " + ScientificReportGenerator.NO_DECLARED_BASIS.format(
            type_name=type(result).__name__
        )

    @staticmethod
    def generate_full_report(
        trial_design_inputs: TrialDesignInputs,
        disease_code: str = "HCC-S",
        trial_id: Optional[str] = None,
        include_appendix_mode: bool = False,
    ) -> ScientificReport:
        """
        Generate comprehensive scientific report for a trial design.
        
        Args:
            trial_design_inputs: TrialDesignInputs dataclass with formulation parameters
            disease_code: Disease profile code (default: HCC-S)
            trial_id: Optional trial identifier for traceability
            include_appendix_mode: If True, include technical appendix sections
        
        Returns:
            ScientificReport: Complete structured report
        """
        
        # Step 1: Initialize disease context
        disease_profile = get_disease_profile(disease_code)
        
        # Step 2: Run mechanistic engine (6 core predictions)
        mechanistic_results = MechanisticEngine.compute_all_predictions(
            trial_design_inputs,
            disease_profile,
        )
        
        # Step 3: Assess disease fit
        disease_fit_results = DiseaseFilEngine.assess_disease_fit(
            trial_design_inputs,
            disease_profile,
        )
        
        # Step 4: Evaluate safety risks (6 components)
        safety_results = SafetyEngine.assess_safety_profile(trial_design_inputs)
        
        # Step 5: Assess manufacturability
        manufacturing_results = ManufacturingEngine.assess_manufacturability(trial_design_inputs)
        
        # Step 6: Position regulatory strategy
        regulatory_results = RegulatoryEngine.assess_regulatory_position(
            trial_design_inputs,
            disease_profile,
            mechanistic_results,
            safety_results,
            disease_fit_results,
        )
        
        # Step 7: Calculate confidence/evidence profile
        confidence_results = ConfidenceEngine.calculate_confidence_profile(
            mechanistic_results,
            safety_results,
            disease_fit_results,
            manufacturing_results,
            regulatory_results,
        )
        
        # Step 8: Generate report limitations
        limitations = ReportLimitations(
            data_limitations=ScientificReportGenerator._identify_data_gaps(trial_design_inputs),
            model_limitations=ScientificReportGenerator._identify_model_limitations(
                confidence_results,
                trial_design_inputs,
            ),
            evidence_gaps=confidence_results.confidence_limiting_factors,
            regulatory_caveats=regulatory_results.evidence_gaps,
            assumption_risks=ScientificReportGenerator._identify_assumption_risks(trial_design_inputs),
            not_addressed=[
                "Long-term (>6 months) safety and efficacy",
                "Human toxicology and PK/PD",
                "GLP toxicology studies",
                "Clinical trial design optimization",
                "Intellectual property landscape",
            ],
        )
        
        # Step 9: Generate AI model transparency statement
        ai_transparency = AIModelTransparency(
            model_basis="Mechanistic physics principles + empirical pharmaceutical literature",
            # STEP 1 FIX (previously masked by DEFECT-D8)
            # ------------------------------------------------------------------
            # This assumed all six objects expose `.basis`, but only
            # `PredictionBasis` declares that field. `DiseaseBiologyFit`,
            # `SafetyRiskProfile`, `ManufacturabilityProfile` and
            # `RegulatoryAssessment` do not, so this raised AttributeError for
            # every input. It was unreachable until DEFECT-D8 was corrected.
            #
            # No basis is invented for the four modules that do not declare one.
            # They are reported explicitly as "not declared", which is the honest
            # state. Giving those modules a structured prediction basis is an open
            # item for scientific review -- see docs/SCORING_CANONICALIZATION.md.
            prediction_basis_for_each_module=[
                ScientificReportGenerator._describe_prediction_basis(k, v)
                for k, v in {
                    "delivery_efficacy": mechanistic_results.delivery_efficacy,
                    "toxicity_safety": mechanistic_results.toxicity_safety,
                    "disease_fit": disease_fit_results,
                    "safety_decomposition": safety_results,
                    "manufacturability": manufacturing_results,
                    "regulatory_positioning": regulatory_results,
                }.items()
            ],
            calibration_data_source="Published pharmaceutical and nanoparticle literature (2015-2024)",
            model_performance_on_known_systems="Model architecture supports retrospective validation; not performed in this implementation",
            limitations_of_ai_predictions=[
                "Predictions are mechanistic approximations, not empirical fits",
                "Performance validated conceptually but not quantitatively",
                "Novel formulation combinations may perform differently than literature precedent",
            ],
            input_sensitivity="Predictions most sensitive to: particle size, PEG density, encapsulation method, targeting ligand presence",
            recommendation="Use AI predictions as design guidance; validate with in vitro and in vivo studies",
        )
        
        # Step 10: Assemble final report
        timestamp = datetime.now().isoformat()
        
        return ScientificReport(
            report_id=trial_id or f"REPORT-{timestamp}",
            generated_at=timestamp,
            disease_profile=disease_profile,
            trial_design_inputs=trial_design_inputs,
            mechanistic_predictions=mechanistic_results,
            disease_biology_fit=disease_fit_results,
            safety_risk_profile=safety_results,
            manufacturability_assessment=manufacturing_results,
            regulatory_assessment=regulatory_results,
            confidence_evidence_profile=confidence_results,
            ai_model_transparency=ai_transparency,
            report_limitations=limitations,
            overall_scientific_quality_score=ScientificReportGenerator._calculate_quality_score(
                mechanistic_results,
                safety_results,
                disease_fit_results,
                confidence_results,
            ),
            report_mode="scientific_full" if not include_appendix_mode else "scientific_full_with_appendix",
        )

    @staticmethod
    def generate_investor_summary(
        full_report: ScientificReport,
    ) -> str:
        """
        Generate executive summary suitable for investors/partners.
        Highlights commercial potential, regulatory pathway, manufacturing feasibility.
        """
        
        lines = [
            "NANOBIO STUDIO - INVESTOR SUMMARY",
            "=" * 70,
            "",
            f"Trial ID: {full_report.report_id}",
            f"Disease: {full_report.disease_profile.disease_name}",
            f"Report Generated: {full_report.generated_at}",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 70,
            "",
        ]
        
        # Commercial readiness
        quality = full_report.overall_scientific_quality_score
        if quality >= 75:
            lines.append("✓ COMMERCIAL POTENTIAL: HIGH - Formulation shows strong scientific merit")
        elif quality >= 60:
            lines.append("✓ COMMERCIAL POTENTIAL: MODERATE - Formulation is viable with further development")
        else:
            lines.append("⚠ COMMERCIAL POTENTIAL: LOWER - Consider design modifications or increased R&D investment")
        
        lines.extend([
            "",
            "KEY BUSINESS METRICS:",
            f"  • Overall Scientific Quality: {quality:.0f}/100",
            f"  • Scientific Confidence: {full_report.confidence_evidence_profile.overall_scientific_confidence*100:.0f}%",
            f"  • Manufacturability Score: {full_report.manufacturability_assessment.overall_manufacturability_score:.0f}/100",
            f"  • Est. Cost per Dose: ${full_report.manufacturability_assessment.estimated_cost_per_dose_usd:.2f}",
            f"  • Manufacturing Cycle Time: {full_report.manufacturability_assessment.batch_cycle_time_days:.1f} days",
            "",
            "REGULATORY PATHWAY:",
            f"  • Current Stage: {full_report.regulatory_assessment.current_regulatory_stage.replace('_', ' ').title()}",
            f"  • Category: {full_report.regulatory_assessment.regulatory_category}",
            f"  • Strategy: {full_report.regulatory_assessment.primary_regulatory_strategy}",
            "",
            "RISK ASSESSMENT:",
        ])
        
        # Highest safety risks
        safety = full_report.safety_risk_profile
        high_risk_components = [
            ("Systemic Toxicity", safety.systemic_toxicity),
            ("Immunogenicity", safety.immunogenicity),
            ("Off-Target Effects", safety.off_target_effects),
        ]
        
        high_risks = [
            (name, comp.risk_score) for name, comp in high_risk_components
            if comp and comp.risk_band in ["High", "Critical"]
        ]
        
        if high_risks:
            lines.append("  ⚠ HIGH-RISK COMPONENTS:")
            for name, score in high_risks:
                lines.append(f"    - {name}: {score:.0f}/100 risk")
        else:
            lines.append("  ✓ Safety profile acceptable across all components")
        
        lines.extend([
            "",
            "INVESTMENT HIGHLIGHTS:",
            f"  • Delivery Efficacy Target: {full_report.mechanistic_predictions.delivery_efficacy.value:.0f}/100",
            f"  • Disease Fit Score: {full_report.disease_biology_fit.overall_fit_score:.0f}/100",
            # STEP 1 FIX (previously masked by DEFECT-D8): `gmp_pathway_readiness`
            # is a field of ManufacturabilityProfile, not RegulatoryAssessment.
            # The reference pointed at the wrong object and raised AttributeError.
            f"  • Manufacturing (GMP) Readiness: {full_report.manufacturability_assessment.gmp_pathway_readiness}",
            "",
            "NEXT STEPS:",
            "  1. Finalize formulation and establish analytical specifications",
            "  2. Conduct preliminary in vitro studies to validate mechanistic predictions",
            "  3. Initiate GLP toxicology program design",
            "  4. Develop clinical strategy and trial design",
            "",
            "BASIS AND LIMITATIONS:",
            "  All figures above are COMPUTATIONAL RESEARCH-PLANNING ESTIMATES",
            "  produced by rule-based and mechanistic models. They are NOT",
            "  experimentally validated, NOT clinically validated, NOT regulatory",
            "  approval predictions, and NOT a substitute for wet-lab testing.",
            f"  Disease-fit verdict status: {full_report.disease_biology_fit.verdict_status}",
        ])
        
        return "\n".join(lines)

    @staticmethod
    def _identify_data_gaps(trial_design_inputs: TrialDesignInputs) -> list:
        """Identify gaps in input data provided"""
        gaps = []
        
        # Check for missing parameters
        if not trial_design_inputs.case_id:
            gaps.append("Case/Trial ID not provided")
        
        if trial_design_inputs.nanoparticle_size_nm is None:
            gaps.append("Nanoparticle size not specified")
        
        return gaps

    @staticmethod
    def _identify_model_limitations(
        confidence_results: ConfidenceEvidenceProfile,
        trial_design_inputs: TrialDesignInputs,
    ) -> list:
        """Identify limitations of mechanistic models used"""
        limitations = []
        
        # Low confidence components are a limitation
        for component in confidence_results.predictions_with_low_confidence:
            limitations.append(
                f"{component}: Prediction confidence <60%; model reflects design principles not empirical validation"
            )
        
        # Complex combinations are limitations
        if trial_design_inputs.peg_surface_coating and trial_design_inputs.targeting_ligand:
            limitations.append(
                "Combined PEG + targeting ligand: Limited literature on synergistic effects; "
                "predictions assume additive benefits"
            )
        
        return limitations

    @staticmethod
    def _identify_assumption_risks(trial_design_inputs: TrialDesignInputs) -> list:
        """Identify risks inherent in model assumptions"""
        risks = [
            "Assumes standard mammalian physiology; predictions may not translate to humans",
            "Assumes disease model vascularization matches clinical tumors",
            "Assumes quality manufacturing; process failures not modeled",
        ]
        
        if trial_design_inputs.nanoparticle_size_nm < 50 or trial_design_inputs.nanoparticle_size_nm > 250:
            risks.append(
                f"Size {trial_design_inputs.nanoparticle_size_nm}nm outside literature-validated range"
            )
        
        return risks

    @staticmethod
    def _calculate_quality_score(
        mechanistic_results: MechanisticPredictionResult,
        safety_results: SafetyRiskProfile,
        disease_fit_results: DiseaseBiologyFit,
        confidence_results: ConfidenceEvidenceProfile,
    ) -> float:
        """
        Calculate overall scientific quality score (0-100).
        
        Combines performance scores with confidence weighting.
        """
        
        # Performance scores
        mech_avg = (
            mechanistic_results.delivery_efficacy.value +
            mechanistic_results.toxicity_safety.value +
            mechanistic_results.manufacturability.value +
            mechanistic_results.targeting_efficacy.value
        ) / 4.0
        
        safety_score = 100.0 - safety_results.overall_safety_score
        disease_score = disease_fit_results.overall_fit_score
        
        # Weighted average of key scores
        quality = (
            mech_avg * 0.35 +           # Mechanistic: 35%
            safety_score * 0.25 +       # Safety: 25%
            disease_score * 0.20 +      # Disease fit: 20%
            (confidence_results.overall_scientific_confidence * 100.0) * 0.20  # Confidence: 20%
        )
        
        return min(100.0, max(0.0, quality))
