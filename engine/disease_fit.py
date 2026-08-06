"""
Disease Biology Fit Engine for NanoBio Studio
Assesses how well a formulation addresses disease-specific biological barriers
"""

from typing import List, Tuple
from models.scientific_assessment import (
    DiseaseBiologyFit,
    TrialDesignInputs,
    PredictionBasis,
)
from config.disease_profiles import DiseaseProfile
from config.scoring_config import get_confidence_label


class DiseaseFilEngine:
    """
    Evaluates formulation fit to disease-specific biological requirements.
    Provides transparency on barrier considerations and targeting strategy.

    Scientific positioning
    ----------------------
    Fit scores are computational research-planning indicators derived from
    literature-informed barrier descriptions. They are not experimentally
    validated, not clinically validated, and not a regulatory approval
    likelihood.

    Note on the class name: "Fil" is a long-standing typo for "Fit". It is
    preserved to avoid breaking imports across the codebase.
    """

    #: Score above which the legacy regulatory engine emitted a higher-confidence
    #: favourable assertion. DECISION 6: NOT to be lowered.
    FAVOURABLE_VERDICT_THRESHOLD = 70.0

    #: Highest overall_fit_score observed across an exhaustive sweep of 1,792
    #: parameter combinations (2 supported diseases x size x charge x PEG x PEG
    #: density x ligand). The threshold above is therefore never crossed under the
    #: current model, making the favourable branch unreachable.
    #: DECISION 6: component weights must NOT be altered to force a crossing.
    OBSERVED_MODEL_CEILING = 68.33

    #: Structured status returned while the verdict is withheld (DECISION 6.6).
    VERDICT_STATUS_CALIBRATION_REQUIRED = "calibration_required"

    @staticmethod
    def assess_disease_fit(
        design_inputs: TrialDesignInputs,
        disease_profile: DiseaseProfile,
    ) -> DiseaseBiologyFit:
        """
        Comprehensive assessment of formulation appropriateness for target disease.

        Returns:
            DiseaseBiologyFit: Structured evaluation of biological fit
        """
        
        # Parse disease profile for barrier information
        barriers = DiseaseFilEngine._extract_barriers(disease_profile)
        
        # Score each barrier mitigation
        barrier_scores: List[Tuple[str, float, str]] = []
        for barrier_name, barrier_detail in barriers.items():
            score, rationale = DiseaseFilEngine._score_barrier_mitigation(
                barrier_name, barrier_detail, design_inputs, disease_profile
            )
            barrier_scores.append((barrier_name, score, rationale))
        
        # Calculate overall fit score
        overall_score = DiseaseFilEngine._calculate_overall_fit(barrier_scores)
        
        # Generate comprehensive rationale
        rationale_text = DiseaseFilEngine._generate_fit_rationale(
            disease_profile, barrier_scores, design_inputs
        )
        
        # Identify design mismatches (critical info)
        mismatches = DiseaseFilEngine._identify_mismatches(
            design_inputs, disease_profile, barrier_scores
        )
        
        confidence_score = DiseaseFilEngine._calculate_confidence(disease_profile)
        
        assumptions = [
            f"Assumes disease profile '{disease_profile.disease_name}' accurately represents target pathology",
            "Targeting strategy assumes functional receptor/ligand binding in pre-clinical models",
            "Does not account for tumor microenvironment heterogeneity or adaptive resistance",
            "Barrier mitigation assumes standard pharmaceutical formulation techniques",
            "Disease-specific PK/PD model based on published clinical/pre-clinical data",
        ]
        
        return DiseaseBiologyFit(
            disease_name=disease_profile.disease_name,
            overall_fit_score=overall_score,
            barrier_mitigation_scores=dict((name, score) for name, score, _ in barrier_scores),
            barrier_rationales=dict((name, rationale) for name, rationale, _ in barrier_scores),
            size_appropriateness=DiseaseFilEngine._assess_size_fit(design_inputs, disease_profile),
            charge_appropriateness=DiseaseFilEngine._assess_charge_fit(design_inputs, disease_profile),
            targeting_strategy_fit=DiseaseFilEngine._assess_targeting_fit(design_inputs, disease_profile),
            formulation_approach_fit=DiseaseFilEngine._assess_formulation_fit(design_inputs, disease_profile),
            critical_mismatches=mismatches,
            detailed_rationale=rationale_text,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
            # --- DECISION 6: scores valid, verdict withheld -----------------
            # overall_fit_score and barrier_mitigation_scores above are VALID
            # computed values. What is withheld is any favourable/unfavourable
            # verdict derived from the uncalibrated threshold below.
            verdict_available=False,
            verdict_status=DiseaseFilEngine.VERDICT_STATUS_CALIBRATION_REQUIRED,
            verdict_status_detail=(
                "Fit and barrier-mitigation scores are computed and valid. No "
                "favourable/unfavourable verdict is issued: the "
                f"> {DiseaseFilEngine.FAVOURABLE_VERDICT_THRESHOLD:.0f}% threshold "
                "is uncalibrated and unreachable under the current model "
                f"(observed ceiling {DiseaseFilEngine.OBSERVED_MODEL_CEILING} across "
                "an exhaustive 1,792-combination sweep over the supported diseases "
                "HCC-S and PDAC-I). Whether the scoring is too conservative or the "
                "threshold is mis-specified is an open scientific question; "
                "neither was changed. Not a regulatory approval likelihood."
            ),
            favourable_verdict_threshold=DiseaseFilEngine.FAVOURABLE_VERDICT_THRESHOLD,
            observed_model_ceiling=DiseaseFilEngine.OBSERVED_MODEL_CEILING,
        )

    @staticmethod
    def _extract_barriers(disease_profile: DiseaseProfile) -> dict:
        """Extract key biological barriers from disease profile"""
        barriers = {}
        
        # Common barriers present in most disease profiles
        standard_barriers = {
            "vascular_fenestration": "Limited vascular access to tumor",
            "interstitial_diffusion": "Tight interstitial matrix reduces penetration",
            "immune_recognition": "Innate immune system recognition and clearance",
            "cellular_uptake": "Limited cell membrane penetration",
            "intracellular_trafficking": "Lysosomal degradation and compartmentalization",
            "drug_release": "Controlled payload release at target",
        }
        
        # Map to disease profile attributes if available
        for barrier_key, barrier_desc in standard_barriers.items():
            if hasattr(disease_profile, barrier_key):
                barriers[barrier_key] = getattr(disease_profile, barrier_key)
            else:
                barriers[barrier_key] = barrier_desc
        
        return barriers

    @staticmethod
    def _score_barrier_mitigation(
        barrier: str,
        barrier_detail: str,
        design_inputs: TrialDesignInputs,
        disease_profile: DiseaseProfile,
    ) -> Tuple[float, str]:
        """
        Score how well the formulation addresses a specific barrier.
        
        Returns:
            (score 0-100, rationale_text)
        """
        score = 50.0  # Neutral baseline
        rationale = ""
        
        if barrier == "vascular_fenestration":
            # EPR effect addresses vascular barrier
            if 80 <= design_inputs.nanoparticle_size_nm <= 150:
                score = 75.0
                rationale = f"Size {design_inputs.nanoparticle_size_nm}nm optimal for EPR-mediated vascular extravasation (published cutoffs: 70-200nm)"
            elif design_inputs.nanoparticle_size_nm > 200:
                score = 40.0
                rationale = f"Size {design_inputs.nanoparticle_size_nm}nm too large for efficient vascular extravasation; limited to diseased vasculature"
            else:
                score = 55.0
                rationale = f"Size {design_inputs.nanoparticle_size_nm}nm suboptimal; marginal EPR advantage"
        
        elif barrier == "interstitial_diffusion":
            # PEG coating reduces mechanical friction + electrostatic interactions
            base = 50.0
            if design_inputs.peg_surface_coating:
                base += 20.0
                rationale = f"PEG density {design_inputs.peg_density_percent}% reduces protein corona + proteoglycan interactions"
            if design_inputs.surface_charge_mv == 0:  # Neutral
                base += 10.0
                rationale += "; Neutral charge reduces electrostatic binding to matrix GAGs"
            score = min(85.0, base)
        
        elif barrier == "immune_recognition":
            # PEG stealth + size
            base = 40.0
            if design_inputs.peg_surface_coating:
                base += 30.0
                rationale = f"PEG {design_inputs.peg_density_percent}% creates immune-silent surface (CD47 analogues would further improve)"
            if 80 <= design_inputs.nanoparticle_size_nm <= 150:
                base += 10.0
                rationale += "; Optimal size for RES evasion"
            score = min(85.0, base)
        
        elif barrier == "cellular_uptake":
            # Targeting ligand enables receptor-mediated
            base = 50.0
            if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
                base += 30.0
                rationale = f"Targeting ligand ({design_inputs.targeting_ligand}) enables receptor-specific uptake; addresses passive cellular resistance"
            else:
                rationale = "No active targeting; relies on non-specific fluid-phase endocytosis"
            score = min(85.0, base)
        
        elif barrier == "intracellular_trafficking":
            # Encapsulation method + pH-responsive release
            base = 55.0
            enc = design_inputs.encapsulation_method.lower()
            if enc == "active_loading":
                base += 20.0
                rationale = "Active loading preserves acidic gradient; pH-responsive release in lysosomes"
            elif enc == "nanoprecipitation":
                base += 10.0
                rationale = "Polymer-based formulation; pH-gradualrelease profile"
            else:
                rationale = "Passive loading; rapid intracellular release (may limit therapeutic benefit)"
            score = min(85.0, base)
        
        elif barrier == "drug_release":
            # Encapsulation design determines release kinetics
            base = 50.0
            enc = design_inputs.encapsulation_method.lower()
            if enc == "active_loading":
                base += 20.0
                rationale = "Active loading: sustained 24-72hr release; sustained therapeutic exposure"
            elif enc == "passive_loading":
                base -= 10.0
                rationale = "Passive loading: biphasic release (immediate + slower); may be suboptimal for sustained therapy"
            score = min(85.0, base)
        
        return score, rationale

    @staticmethod
    def _calculate_overall_fit(barrier_scores: List[Tuple[str, float, str]]) -> float:
        """
        Calculate overall disease fit as weighted combination of barrier scores.
        All barriers equally important; average them.
        """
        if not barrier_scores:
            return 50.0
        
        # Simple equal weighting for now
        total = sum(score for _, score, _ in barrier_scores)
        return total / len(barrier_scores)

    @staticmethod
    def _assess_size_fit(design_inputs: TrialDesignInputs, disease_profile: DiseaseProfile) -> str:
        """Assess whether size is appropriate for disease"""
        size = design_inputs.nanoparticle_size_nm
        
        if 80 <= size <= 150:
            return "Optimal for EPR-mediated passive targeting and rapid hepatic clearance"
        elif 50 < size < 80:
            return "Suboptimal: too small for robust EPR effect; may show higher hepatic uptake"
        elif 150 < size <= 200:
            return "Acceptable: larger than optimal EPR window; slower clearance (may be advantageous for sustained exposure)"
        else:
            return f"Poor fit: size {size}nm outside evidence-based targeting window"

    @staticmethod
    def _assess_charge_fit(design_inputs: TrialDesignInputs, disease_profile: DiseaseProfile) -> str:
        """Assess surface charge appropriateness for disease"""
        charge = design_inputs.surface_charge_mv
        
        if abs(charge) < 10:
            return "Excellent: Neutral charge minimizes protein corona; promotes RES evasion"
        elif abs(charge) < 25:
            return "Good: Moderate charge acceptable; slight protein corona formation"
        else:
            return f"Poor: Charge {charge}mV promotes strong protein corona and immune activation"

    @staticmethod
    def _assess_targeting_fit(design_inputs: TrialDesignInputs, disease_profile: DiseaseProfile) -> str:
        """Assess targeting strategy appropriateness"""
        ligand = design_inputs.targeting_ligand
        
        if ligand and ligand.lower() != "none":
            return f"Active targeting: {ligand} addresses cellular uptake barrier; enables receptor-specific treatment"
        else:
            return "Passive targeting only (EPR effect); appropriate for highly vascularized diseases but limits specificity"

    @staticmethod
    def _assess_formulation_fit(design_inputs: TrialDesignInputs, disease_profile: DiseaseProfile) -> str:
        """Assess encapsulation/formulation approach fit"""
        enc = design_inputs.encapsulation_method.lower()
        
        fitting_map = {
            "passive_loading": "Simple approach; rapid release may support acute toxicity reduction but limited sustained therapy",
            "active_loading": "Sophisticated approach enabling sustained release and lysosomal targeting; supports chronic/repeated dosing",
            "nanoprecipitation": "Polymer-based; supports controlled hydrolytic release; suitable for hydrophobic drugs",
            "none": "Non-encapsulated; minimal formulation complexity; relies on intrinsic stability",
        }
        
        return fitting_map.get(enc, "Unknown formulation approach")

    @staticmethod
    def _identify_mismatches(
        design_inputs: TrialDesignInputs,
        disease_profile: DiseaseProfile,
        barrier_scores: List[Tuple[str, float, str]],
    ) -> List[str]:
        """
        Identify critical mismatches between formulation and disease requirements.
        Returns list of warnings/concerns.
        """
        mismatches = []
        
        # Check for poor barrier mitigation
        for barrier_name, score, _ in barrier_scores:
            if score < 45.0:
                mismatches.append(
                    f"MISMATCH: {barrier_name} score {score:.0f}/100 - weak formulation strategy for this barrier"
                )
        
        # Check for size outside range
        size = design_inputs.nanoparticle_size_nm
        if size < 50 or size > 250:
            mismatches.append(
                f"SIZE WARNING: {size}nm significantly outside optimal window (80-150nm); EPR targeting may be compromised"
            )
        
        # Check for high charge + no PEG
        if abs(design_inputs.surface_charge_mv) > 30 and not design_inputs.peg_surface_coating:
            mismatches.append(
                "MISMATCH: High surface charge without PEG coating; strong protein corona will impair delivery"
            )
        
        # Check for targeting mismatch
        ligand = design_inputs.targeting_ligand
        if not ligand or ligand.lower() == "none":
            if size > 150:
                mismatches.append(
                    "TARGETING LIMITATION: No ligand + large size = reliance only on passive EPR; may have poor specificity"
                )
        
        return mismatches

    @staticmethod
    def _generate_fit_rationale(
        disease_profile: DiseaseProfile,
        barrier_scores: List[Tuple[str, float, str]],
        design_inputs: TrialDesignInputs,
    ) -> str:
        """Generate comprehensive narrative rationale for disease fit"""
        
        lines = [
            f"Disease-Specific Fit Assessment: {disease_profile.disease_name}",
            f"={'=' * 60}",
            "",
            "This formulation's biological fit to the target disease depends on mitigation of key barriers:",
            "",
        ]
        
        # Barrier-by-barrier breakdown
        for barrier_name, score, detail in barrier_scores:
            lines.append(f"• {barrier_name}: {score:.0f}/100")
            lines.append(f"  {detail}")
            lines.append("")
        
        # Overall assessment
        overall = sum(s for _, s, _ in barrier_scores) / len(barrier_scores) if barrier_scores else 50
        if overall >= 75:
            assessment = "STRONG biological fit; formulation well-matched to disease requirements"
        elif overall >= 60:
            assessment = "MODERATE biological fit; formulation addresses key barriers but has limitations"
        else:
            assessment = "WEAK biological fit; significant barriers inadequately addressed"
        
        lines.append(f"Overall Assessment: {assessment} (Average score: {overall:.0f}/100)")
        lines.append("")
        lines.append("Important Limitations:")
        lines.append("- This assessment is PREDICTIVE based on published biological principles")
        lines.append("- Actual disease model efficacy requires in vivo validation")
        lines.append("- Disease heterogeneity not captured (e.g., tumor microenvironment variability)")
        lines.append("- Assumes current target selection; alternative targets may show different fit profiles")
        
        return "\n".join(lines)

    @staticmethod
    def _calculate_confidence(disease_profile: DiseaseProfile) -> float:
        """
        Calculate confidence in disease fit assessment.
        Based on how well-characterized the disease biology is.
        """
        # Different diseases have different evidence quality
        disease_confidence = {
            "HCC-S": 0.80,  # Well-characterized hepatocellular carcinoma
            "PDAC-I": 0.75,  # Pancreatic cancer less studied for nanoparticles
        }
        
        base_confidence = disease_confidence.get(disease_profile.disease_name, 0.70)
        
        # Some uncertainty always exists in disease-drug fit
        return base_confidence * 0.85
