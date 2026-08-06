"""
Mechanistic Engine for NanoBio Studio
Computes all 6 core mechanistic predictions with full transparency
"""

import math
from typing import Optional, Tuple
from models.scientific_assessment import (
    MechanisticPredictionResult,
    PredictionBasis,
    TrialDesignInputs,
)
from config.disease_profiles import DiseaseProfile
from config.scoring_config import (
    DEFAULT_DELIVERY_MODEL,
    DEFAULT_TOXICITY_MODEL,
    DEFAULT_MANUFACTURABILITY_MODEL,
    DEFAULT_DISEASE_FIT_MODEL,
    get_confidence_label,
)


class MechanisticEngine:
    """
    Core prediction engine for nanoparticle delivery systems.
    Provides transparent, assumption-aware predictions for 6 key dimensions.
    """

    # Size-based penalties and benefits
    OPTIMAL_SIZE_MIN = 80.0
    OPTIMAL_SIZE_MAX = 150.0
    SUBOPTIMAL_PENALTY = 15.0
    OVERSIZED_PENALTY = 20.0  # >200nm reduces efficacy significantly

    # PEG coating benefits
    PEG_COATING_BENEFIT = 8.0
    PEG_DENSITY_BENEFIT = 5.0

    # Targeting ligand benefit
    LIGAND_BENEFIT = 12.0

    @staticmethod
    def compute_delivery_efficacy(
        design_inputs: TrialDesignInputs,
        disease_profile: DiseaseProfile,
    ) -> PredictionBasis:
        """
        Predict delivery efficacy (0-100 scale).

        Key Factors:
        - Particle size (optimal window 80-150nm found in literature)
        - PEG coating (reduces RES uptake)
        - Surface charge (influences cellular uptake)
        - Targeting ligand (disease-specific)

        Assumptions:
        - Linear combination of weighted factors
        - Disease profile barriers partially addressable by formulation
        - Literature values from 2022-2024 nanoparticle delivery studies
        """
        base_score = 50.0
        adjustments = []

        # 1. Size optimization (basis: EPR effect literature)
        size_penalty = MechanisticEngine._evaluate_size_penalty(
            design_inputs.nanoparticle_size_nm
        )
        adjustments.append((f"Size {design_inputs.nanoparticle_size_nm}nm penalty", -size_penalty))

        # 2. PEG surface coating
        if design_inputs.peg_surface_coating:
            peg_benefit = (
                MechanisticEngine.PEG_COATING_BENEFIT
                + MechanisticEngine.PEG_DENSITY_BENEFIT * (design_inputs.peg_density_percent / 50.0)
            )
            adjustments.append(("PEG coating and density", peg_benefit))

        # 3. Targeting ligand
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            adjustments.append(("Targeting ligand", MechanisticEngine.LIGAND_BENEFIT))

        # 4. Disease-specific barrier consideration
        if hasattr(disease_profile, 'encapsulation_dependency'):
            if design_inputs.encapsulation_method not in ["passive_loading", "none"]:
                disease_barrier_adjustment = 5.0
                adjustments.append((f"Active encapsulation for {disease_profile.disease_name}", disease_barrier_adjustment))

        # Calculate final score
        final_score = max(0.0, min(100.0, base_score + sum(adj[1] for adj in adjustments)))

        confidence_score = MechanisticEngine._calculate_confidence(
            data_completeness=0.95,
            model_type="mechanistic_physics"
        )

        rationale = "Score based on nanoparticle size optimization, PEG surface engineering, "
        rationale += "and targeting ligand presence. Applies principles from passive/active targeting literature. "
        rationale += f"Adjustments: {', '.join([f'{name}({val:+.1f})' for name, val in adjustments])}"

        assumptions = [
            "Assumes EPR effect dominant for disease site accumulation",
            "PEG density monotonically improves RES evasion (literature-supported)",
            "Targeting ligand efficacy domain-specific but universally beneficial",
            "Encapsulation method affects loading efficiency, not delivery per se",
        ]

        return PredictionBasis(
            value=final_score,
            basis="mechanistic_physics_principles",
            rationale=rationale,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def compute_toxicity_prediction(
        design_inputs: TrialDesignInputs,
    ) -> PredictionBasis:
        """
        Predict safety/toxicity risk (0-100 scale, where 100 = very safe, 0 = very toxic).

        Key Factors:
        - Nanoparticle size (optimal < 200nm for clearance)
        - Surface charge (neutral preferred)
        - PEG coating (reduces immune activation)
        - Material composition

        Assumptions:
        - Inverse relationship: higher safety score = lower risk
        - Size <50nm may increase cellular uptake of toxic degradation products
        - Highly positive/negative charged NPs prone to protein corona + immune activation
        """
        base_score = 60.0  # Moderate baseline safety
        safety_adjustments = []

        # 1. Size-based toxicity (too small = unpredictable uptake; too large = clearance issues)
        size_safety = 0.0
        if 80 <= design_inputs.nanoparticle_size_nm <= 150:
            size_safety = 10.0
            reason = "Size in optimal range (80-150nm) for rapid hepatic clearance"
        elif design_inputs.nanoparticle_size_nm < 50:
            size_safety = -8.0
            reason = "Size <50nm may increase off-target cellular uptake"
        elif design_inputs.nanoparticle_size_nm > 200:
            size_safety = -12.0
            reason = "Size >200nm may cause prolonged circulation + accumulation"
        else:
            size_safety = 2.0
            reason = "Size suboptimal for rapid clearance"
        safety_adjustments.append((reason, size_safety))

        # 2. Surface charge
        abs_charge = abs(design_inputs.surface_charge_mv)
        if abs_charge < 10:
            safety_adjustments.append(("Neutral charge reduces protein corona formation", 8.0))
        elif abs_charge < 25:
            safety_adjustments.append(("Moderate charge acceptable", 3.0))
        else:
            safety_adjustments.append((f"High charge ({abs_charge}mV) promotes immune activation", -10.0))

        # 3. PEG coating reduces immune response
        if design_inputs.peg_surface_coating:
            safety_adjustments.append(("PEG coating suppresses RES recognition", 12.0))

        final_score = max(0.0, min(100.0, base_score + sum(adj[1] for adj in safety_adjustments)))

        confidence_score = MechanisticEngine._calculate_confidence(
            data_completeness=0.90,
            model_type="empirical_literature"
        )

        rationale = "Safety score inverts toxicity risk. Based on size-dependent clearance kinetics, "
        rationale += "charge-protein corona phenomena, and PEG immunoevading properties from peer-reviewed literature. "
        rationale += "Score is PREDICTIVE, not validated in this specific formulation."

        assumptions = [
            "Assumes standard mammalian RES clearance mechanisms",
            "Does not account for material-specific toxicity (e.g., certain metal nanoparticles)",
            "Protein corona coating assumed to be protein-only (no drug-protein interactions)",
            "PEG effect assumed additive, not synergistic with other modifications",
        ]

        return PredictionBasis(
            value=final_score,
            basis="empirical_literature_clearance_kinetics",
            rationale=rationale,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def compute_manufacturability(
        design_inputs: TrialDesignInputs,
    ) -> PredictionBasis:
        """
        Predict manufacturability difficulty (0-100 scale, where 100 = easy, 0 = very difficult).

        Key Factors:
        - Size control precision requirement (smaller = harder)
        - Surface coating complexity (PEG > plain)
        - Encapsulation method complexity (active > passive)
        - Batch reproducibility likelihood
        """
        base_score = 70.0
        mfg_adjustments = []

        # 1. Size control difficulty
        size = design_inputs.nanoparticle_size_nm
        if 100 <= size <= 200:
            mfg_adjustments.append(("Size range achievable with standard techniques", 8.0))
        elif size < 80:
            mfg_adjustments.append((f"Size {size}nm requires tight process control", -12.0))
        elif size > 200:
            mfg_adjustments.append((f"Size {size}nm easier but requires aggregation control", -5.0))

        # 2. PEG surface coating (adds complexity)
        if design_inputs.peg_surface_coating:
            mfg_adjustments.append(("PEG grafting adds purification step", -8.0))
            mfg_adjustments.append((f"PEG density {design_inputs.peg_density_percent}% adds quality control parameter", -3.0))

        # 3. Encapsulation method
        enc_method = design_inputs.encapsulation_method.lower()
        if enc_method == "passive_loading":
            mfg_adjustments.append(("Passive loading is robust, reproducible", 5.0))
        elif enc_method == "active_loading":
            mfg_adjustments.append(("Active loading requires pH/temp gradient control", -15.0))
        elif enc_method == "nanoprecipitation":
            mfg_adjustments.append(("Nanoprecipitation high-throughput but sensitive to parameters", -10.0))

        # 4. Targeting ligand attachment
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            mfg_adjustments.append(("Ligand conjugation adds coupling + purification steps", -12.0))

        final_score = max(0.0, min(100.0, base_score + sum(adj[1] for adj in mfg_adjustments)))

        confidence_score = MechanisticEngine._calculate_confidence(
            data_completeness=0.85,
            model_type="process_engineering"
        )

        rationale = "Score reflects expected manufacturing complexity based on formulation parameters. "
        rationale += "Higher score = easier production. Based on pharmaceutical manufacturing best practices. "
        rationale += "PREDICTIVE - actual feasibility requires detailed process development."

        assumptions = [
            "Assumes access to standard pharmaceutical manufacturing equipment",
            "Does not account for material sourcing availability",
            "Cost estimation excluded (manufacturability score is feasibility only)",
            "Quality control parameters assumed to be standard analytical methods",
        ]

        return PredictionBasis(
            value=final_score,
            basis="pharmaceutical_process_engineering",
            rationale=rationale,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def compute_storage_stability(
        design_inputs: TrialDesignInputs,
    ) -> PredictionBasis:
        """
        Predict long-term storage stability (0-100 scale, where 100 = highly stable).

        Key Factors:
        - Particle size (smaller = faster aggregation)
        - PEG coating (protects from aggregation)
        - Encapsulation (protects drug from degradation)
        - Lyophilization feasibility
        """
        base_score = 65.0
        stability_adjustments = []

        # 1. PEG coating protective effect
        if design_inputs.peg_surface_coating:
            stability_adjustments.append(
                ("PEG steric barrier prevents aggregation during storage", 15.0)
            )
        else:
            stability_adjustments.append(
                ("Bare nanoparticles prone to aggregation over months", -15.0)
            )

        # 2. Encapsulation benefit
        if design_inputs.encapsulation_method and design_inputs.encapsulation_method.lower() != "passive_loading":
            stability_adjustments.append(
                ("Active encapsulation protects drug from degradation", 8.0)
            )

        # 3. Size factor (aggregation kinetics)
        if design_inputs.nanoparticle_size_nm > 150:
            stability_adjustments.append(
                (f"Larger particles ({design_inputs.nanoparticle_size_nm}nm) more prone to settling", -8.0)
            )

        final_score = max(0.0, min(100.0, base_score + sum(adj[1] for adj in stability_adjustments)))

        confidence_score = MechanisticEngine._calculate_confidence(
            data_completeness=0.70,
            model_type="colloid_science"
        )

        rationale = "Based on colloidal stability principles and polymer protective effects. "
        rationale += "Score assumes ambient storage conditions. Stability under refrigeration or freeze-drying "
        rationale += "may significantly improve scores. PREDICTIVE - requires accelerated stability testing."

        assumptions = [
            "Assumes ambient (25°C, 60% RH) storage conditions",
            "Does not model specific pH, osmolarity, or ionic strength effects",
            "Drug degradation pathways not explicitly modeled",
            "Assumes standard pharmaceutical excipients for pH buffering",
        ]

        return PredictionBasis(
            value=final_score,
            basis="colloid_science_aggregation_kinetics",
            rationale=rationale,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def compute_targeting_efficacy(
        design_inputs: TrialDesignInputs,
        disease_profile: DiseaseProfile,
    ) -> PredictionBasis:
        """
        Predict targeting specificity (0-100 scale, where 100 = highly specific).

        Key Factors:
        - Presence of targeting ligand
        - Diseasespecific protein expression in disease profile
        - Size appropriate for extravasation
        - Passive targeting (EPR) vs active
        """
        base_score = 40.0  # Without active targeting, only passive (EPR)
        targeting_adjustments = []

        # 1. Passive targeting (EPR effect)
        if 80 <= design_inputs.nanoparticle_size_nm <= 150:
            targeting_adjustments.append(
                ("Optimal size for EPR effect in tumor microenvironment", 15.0)
            )
            base_score = 55.0
        else:
            targeting_adjustments.append(
                (f"Size {design_inputs.nanoparticle_size_nm}nm suboptimal for EPR", -8.0)
            )

        # 2. Active targeting ligand
        ligand = design_inputs.targeting_ligand
        if ligand and ligand.lower() != "none":
            # Generic ligand benefit (specificity depends on biology)
            ligand_benefit = 30.0
            targeting_adjustments.append(
                (f"Active targeting with {ligand} provides receptor-mediated uptake", ligand_benefit)
            )

        # 3. Disease-specific expression (if available in profile)
        if hasattr(disease_profile, 'target_receptor_expression'):
            if disease_profile.target_receptor_expression == "high":
                targeting_adjustments.append(
                    (f"{disease_profile.disease_name}: target receptor highly expressed", 5.0)
                )

        final_score = max(0.0, min(100.0, base_score + sum(adj[1] for adj in targeting_adjustments)))

        confidence_score = MechanisticEngine._calculate_confidence(
            data_completeness=0.75,
            model_type="molecular_targeting_biology"
        )

        rationale = "Combines passive targeting (EPR effect) and active targeting (ligand-receptor). "
        rationale += "Specificity score assumes disease-appropriate target selection. "
        rationale += "PREDICTIVE - actual targeting validated only through in vivo biodistribution."

        assumptions = [
            "Assumes functional targeting ligand-receptor binding",
            "Disease profile target receptor assumed appropriately selected",
            "Off-target binding not explicitly modeled (see Safety engine)",
            "Assumes sufficient ligand density for multivalent binding",
        ]

        return PredictionBasis(
            value=final_score,
            basis="passive_EPR_plus_active_molecular_targeting",
            rationale=rationale,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def compute_payload_release(
        design_inputs: TrialDesignInputs,
    ) -> PredictionBasis:
        """
        Predict payload release kinetics appropriateness (0-100 scale).

        Key Factors:
        - Encapsulation method determines release profile
        - PEG density affects release (higher = slower)
        - Disease/cell type drives release requirement (in vivo model dependent)
        """
        base_score = 60.0
        release_adjustments = []

        # 1. Encapsulation method determines release
        enc_method = design_inputs.encapsulation_method.lower()
        if enc_method == "passive_loading":
            release_adjustments.append(
                ("Passive loading: rapid initial release, then slower", -5.0)
            )
        elif enc_method == "active_loading":
            release_adjustments.append(
                ("Active loading: sustained release profile, ~24-72hr", 10.0)
            )
        elif enc_method == "nanoprecipitation":
            release_adjustments.append(
                ("Nanoprecipitation: depends on polymer degradation rate", 3.0)
            )

        # 2. PEG coating slows release slightly
        if design_inputs.peg_surface_coating:
            release_adjustments.append(
                (f"PEG density {design_inputs.peg_density_percent}% creates diffusion barrier", 5.0)
            )

        final_score = max(0.0, min(100.0, base_score + sum(adj[1] for adj in release_adjustments)))

        confidence_score = MechanisticEngine._calculate_confidence(
            data_completeness=0.65,
            model_type="biopharmaceutics_kinetics"
        )

        rationale = "Score reflects expected release kinetics based on encapsulation method. "
        rationale += "Appropriateness depends on in vivo disease model and target cell response requirements. "
        rationale += "PREDICTIVE - in vitro release testing required for validation."

        assumptions = [
            "Assumes aqueous in vivo environment (pH 7.4, 37°C)",
            "Does not model lysosomal degradation pathways",
            "Release profile robustness across pH ranges not assessed",
            "Assumes release intended; does not model protective scenarios",
        ]

        return PredictionBasis(
            value=final_score,
            basis="biopharmaceutical_encapsulation_kinetics",
            rationale=rationale,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def compute_all_predictions(
        design_inputs: TrialDesignInputs,
        disease_profile: DiseaseProfile,
    ) -> MechanisticPredictionResult:
        """
        Orchestrate all 6 mechanistic predictions into unified result.
        """
        return MechanisticPredictionResult(
            delivery_efficacy=MechanisticEngine.compute_delivery_efficacy(design_inputs, disease_profile),
            toxicity_safety=MechanisticEngine.compute_toxicity_prediction(design_inputs),
            manufacturability=MechanisticEngine.compute_manufacturability(design_inputs),
            storage_stability=MechanisticEngine.compute_storage_stability(design_inputs),
            targeting_efficacy=MechanisticEngine.compute_targeting_efficacy(design_inputs, disease_profile),
            payload_release=MechanisticEngine.compute_payload_release(design_inputs),
        )

    # ========== HELPER METHODS ==========

    @staticmethod
    def _evaluate_size_penalty(size_nm: float) -> float:
        """Calculate size-based penalty (0 = optimal, higher = worse)"""
        if MechanisticEngine.OPTIMAL_SIZE_MIN <= size_nm <= MechanisticEngine.OPTIMAL_SIZE_MAX:
            return 0.0
        elif size_nm < MechanisticEngine.OPTIMAL_SIZE_MIN:
            return MechanisticEngine.SUBOPTIMAL_PENALTY + (MechanisticEngine.OPTIMAL_SIZE_MIN - size_nm) * 0.1
        else:  # too large
            if size_nm > 200:
                return MechanisticEngine.OVERSIZED_PENALTY
            else:
                return MechanisticEngine.SUBOPTIMAL_PENALTY + (size_nm - MechanisticEngine.OPTIMAL_SIZE_MAX) * 0.05

    @staticmethod
    def _calculate_confidence(data_completeness: float, model_type: str) -> float:
        """
        Calculate confidence score based on data availability and model maturity.
        
        Args:
            data_completeness: Fraction of required inputs provided (0-1)
            model_type: Type of model (mechanistic_physics, empirical_literature, etc.)
        
        Returns:
            Confidence score 0-1
        """
        # Model maturity factors (based on literature support)
        model_maturity = {
            "mechanistic_physics": 0.85,
            "empirical_literature": 0.75,
            "process_engineering": 0.70,
            "colloid_science": 0.70,
            "molecular_targeting_biology": 0.65,
            "biopharmaceutics_kinetics": 0.70,
        }

        maturity = model_maturity.get(model_type, 0.70)
        return data_completeness * maturity
