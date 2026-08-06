"""
Manufacturing Feasibility Assessment Engine for NanoBio Studio
Evaluates process scalability, QC complexity, and production risk
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict
from models.scientific_assessment import (
    ManufacturabilityProfile,
    TrialDesignInputs,
)
from config.scoring_config import get_confidence_label


@dataclass
class ManufacturingRisk:
    """Individual manufacturing risk factor"""
    aspect: str
    difficulty_score: float  # 0-100, higher = more difficult
    primary_driver: str
    scale_up_concern: bool  # Whether this becomes harder at production scale


class ManufacturingEngine:
    """
    Assesses manufacturability from perspective of:
    - Process scalability (lab → pilot → commercial)
    - Quality control complexity
    - Cost implications
    - Regulatory manufacturing pathway readiness
    """

    @staticmethod
    def assess_manufacturability(design_inputs: TrialDesignInputs) -> ManufacturabilityProfile:
        """
        Comprehensive manufacturing feasibility assessment.
        
        Evaluates 5 key dimensions:
        1. Size control and batch consistency
        2. Process complexity (encapsulation, coating, targeting)
        3. Quality control (analytical methods required)
        4. Scale-up risk and equipment requirements
        5. Cost estimation and economic viability
        """
        
        # Evaluate each manufacturing aspect
        size_control = ManufacturingEngine._assess_size_control(design_inputs)
        process_complexity = ManufacturingEngine._assess_process_complexity(design_inputs)
        qc_requirements = ManufacturingEngine._assess_qc_requirements(design_inputs)
        scale_up_risk = ManufacturingEngine._assess_scale_up_risk(design_inputs)
        cost_estimate = ManufacturingEngine._assess_cost_profile(design_inputs)
        
        # Calculate overall manufacturability score
        overall_score = ManufacturingEngine._calculate_overall_manufacturability([
            size_control,
            process_complexity,
            qc_requirements,
            scale_up_risk,
        ])
        
        # Identify process bottlenecks
        bottlenecks = ManufacturingEngine._identify_bottlenecks([
            size_control,
            process_complexity,
            qc_requirements,
            scale_up_risk,
        ])
        
        confidence_score = ManufacturingEngine._calculate_mfg_confidence()
        
        assumptions = [
            "Assumes standard pharmaceutical manufacturing facility (GMP-capable)",
            "Cost estimates use 2023-2024 generic material pricing; APIs add 20-40%",
            "Scale-up assumptions: lab batch 100mg, pilot 1kg, commercial 100kg/batch",
            "Does not model regulatory approval pathway complexity",
            "Encapsulation efficiency assumed 70-90% based on published literature",
        ]
        
        narrative = ManufacturingEngine._generate_manufacturability_narrative(
            design_inputs,
            overall_score,
            size_control,
            process_complexity,
            qc_requirements,
            scale_up_risk,
            bottlenecks
        )
        
        return ManufacturabilityProfile(
            overall_manufacturability_score=overall_score,
            size_control_difficulty=size_control["score"],
            process_complexity_score=process_complexity["score"],
            qc_complexity_score=qc_requirements["score"],
            scale_up_risk_score=scale_up_risk["score"],
            estimated_cost_per_dose_usd=cost_estimate["cost_per_dose"],
            batch_consistency_prediction=size_control.get("consistency_cv", 8.0),
            primary_manufacturing_risks=bottlenecks,
            batch_cycle_time_days=ManufacturingEngine._estimate_cycle_time(design_inputs),
            gmp_pathway_readiness=ManufacturingEngine._assess_gmp_readiness(design_inputs),
            critical_process_parameters=ManufacturingEngine._identify_crit_params(design_inputs),
            manufacturing_roadmap=ManufacturingEngine._generate_roadmap(design_inputs),
            detailed_rationale=narrative,
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def _assess_size_control(design_inputs: TrialDesignInputs) -> Dict:
        """
        Assess difficulty of achieving and maintaining target size.
        Returns expected coefficient of variation (CV%) for batch consistency.
        """
        target_size = design_inputs.nanoparticle_size_nm
        base_cv = 8.0  # Baseline CV% from literature
        difficulty = 50.0
        
        if target_size < 50:
            # Ultra-small particles very difficult
            difficulty = 75.0
            base_cv = 15.0
            driver = "Ultra-small size requires tight process parameters; high failure rate"
        elif 80 <= target_size <= 150:
            # Optimal range: achievable with good control
            difficulty = 40.0
            base_cv = 6.0
            driver = "Size in optimal range (80-150nm) achievable with standard techniques"
        elif target_size > 200:
            # Large particles: opposite problem (preventing aggregation)
            difficulty = 55.0
            base_cv = 10.0
            driver = "Large particles: aggregate suppression during production adds complexity"
        else:
            # Suboptimal range
            difficulty = 60.0
            base_cv = 10.0
            driver = "Size suboptimal: requires process optimization"
        
        # PEG coating adds complexity
        if design_inputs.peg_surface_coating:
            difficulty += 15.0
            base_cv += 3.0
            driver += "; PEG grafting adds purification step"
        
        return {
            "score": min(100.0, difficulty),
            "consistency_cv": base_cv,
            "primary_driver": driver,
        }

    @staticmethod
    def _assess_process_complexity(design_inputs: TrialDesignInputs) -> Dict:
        """
        Assess manufacturing process complexity and number of steps required.
        """
        base_complexity = 30.0
        steps = ["Core synthesis"]  # Always have core synthesis
        
        # 1. Core material synthesis
        # (already counted)
        
        # 2. Encapsulation method
        enc_method = design_inputs.encapsulation_method.lower()
        if enc_method == "passive_loading":
            steps.append("Simple mixing")
            base_complexity += 5.0
        elif enc_method == "active_loading":
            steps.append("pH-gradient active loading")
            base_complexity += 35.0  # Significantly more complex
        elif enc_method == "nanoprecipitation":
            steps.append("Nanoprecipitation/solvent exchange")
            base_complexity += 25.0
        
        # 3. PEG surface coating
        if design_inputs.peg_surface_coating:
            steps.append(f"PEG grafting ({design_inputs.peg_density_percent}% target)")
            base_complexity += 20.0
        
        # 4. Targeting ligand attachment
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            steps.append(f"Ligand coupling ({design_inputs.targeting_ligand})")
            base_complexity += 25.0
        
        # 5. Purification/formulation
        steps.append("Purification and formulation")
        base_complexity += 10.0
        
        complexity = min(100.0, base_complexity)
        
        return {
            "score": complexity,
            "process_steps": steps,
            "num_steps": len(steps),
            "primary_driver": f"{len(steps)} manufacturing steps; most complex is " + 
                             (enc_method if enc_method != "passive_loading" else "encapsulation"),
        }

    @staticmethod
    def _assess_qc_requirements(design_inputs: TrialDesignInputs) -> Dict:
        """
        Assess quality control testing requirements and analytical complexity.
        """
        base_qc_complexity = 35.0
        qc_tests = [
            "Particle size distribution (DLS, TEM)",
            "Zeta potential",
            "Encapsulation efficiency",
            "Sterility and endotoxin",
        ]
        
        # PEG adds QC
        if design_inputs.peg_surface_coating:
            qc_tests.append(f"PEG surface density verification (NMR or {design_inputs.peg_density_percent}% target)")
            base_qc_complexity += 15.0
        
        # Targeting ligand adds QC
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            qc_tests.append(f"Ligand coupling efficiency ({design_inputs.targeting_ligand})")
            base_qc_complexity += 15.0
        
        # Encapsulation method affects QC
        enc_method = design_inputs.encapsulation_method.lower()
        if enc_method == "active_loading":
            qc_tests.append("Internal pH gradient confirmation (NMR or ion-selective electrode)")
            base_qc_complexity += 10.0
        
        # Stability testing
        qc_tests.append("Stability under storage conditions (3-month accelerated)")
        base_qc_complexity += 10.0
        
        qc_complexity = min(100.0, base_qc_complexity)
        
        return {
            "score": qc_complexity,
            "required_tests": qc_tests,
            "num_tests": len(qc_tests),
            "primary_driver": f"{len(qc_tests)} critical test methods required for batch release",
        }

    @staticmethod
    def _assess_scale_up_risk(design_inputs: TrialDesignInputs) -> Dict:
        """
        Assess risk and complexity of scaling from lab → pilot → commercial.
        """
        base_scale_risk = 40.0
        risk_factors = []
        
        # Size control becomes harder at scale
        size = design_inputs.nanoparticle_size_nm
        if size < 80:
            risk_factors.append("Ultra-small size: difficult to maintain during scale-up")
            base_scale_risk += 20.0
        elif size > 180:
            risk_factors.append("Large size: aggregation control at scale challenging")
            base_scale_risk += 15.0
        
        # PEG coating process scalability
        if design_inputs.peg_surface_coating:
            risk_factors.append(f"PEG grafting requires specialized equipment; {design_inputs.peg_density_percent}% control critical")
            base_scale_risk += 12.0
        
        # Active loading scalability
        if design_inputs.encapsulation_method.lower() == "active_loading":
            risk_factors.append("pH-gradient active loading: tight parameter control required at scale")
            base_scale_risk += 15.0
        
        # Targeting ligand attachment at scale
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            risk_factors.append("Ligand coupling: reaction efficiency may vary with scale")
            base_scale_risk += 10.0
        
        scale_risk = min(100.0, base_scale_risk)
        
        return {
            "score": scale_risk,
            "risk_factors": risk_factors,
            "scale_up_strategy": "DOE (design of experiments) approach required; pilot batch (1kg) essential before commercial scale",
            "primary_driver": f"{len(risk_factors)} scale-up risk factors identified",
        }

    @staticmethod
    def _assess_cost_profile(design_inputs: TrialDesignInputs) -> Dict:
        """
        Estimate manufacturing cost per dose (rough order of magnitude).
        Based on 2023-2024 pharmaceutical manufacturing benchmarks.
        """
        # Base materials cost (PLGA core, typical API loading)
        base_material_cost = 15.0  # USD per dose equivalent
        
        # PEG increases materials cost
        if design_inputs.peg_surface_coating:
            peg_cost = 5.0 * (design_inputs.peg_density_percent / 50.0)  # Scales with density
            base_material_cost += peg_cost
        
        # Targeting ligand significantly increases cost
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            ligand_cost = 20.0  # Typical monoclonal antibody/ligand fragment cost
            base_material_cost += ligand_cost
        
        # Manufacturing processing labor and overhead
        labor_overhead = base_material_cost * 0.4  # 40% labor/overhead multiplier for small scale
        
        # Encapsulation complexity adds cost
        enc_method = design_inputs.encapsulation_method.lower()
        if enc_method == "active_loading":
            base_material_cost *= 1.3  # 30% complexity multiplier
        elif enc_method == "nanoprecipitation":
            base_material_cost *= 1.15
        
        # Quality control and testing ~15% of total
        qc_cost = (base_material_cost + labor_overhead) * 0.15
        
        total_cost = base_material_cost + labor_overhead + qc_cost
        
        # Note: At commercial scale (100kg batches), per-unit cost would be 30-50% lower
        scale_adjusted_cost = total_cost * 0.7  # Assume eventual commercial scale
        
        return {
            "cost_per_dose": round(scale_adjusted_cost, 2),
            "cost_breakdown": {
                "materials": round(base_material_cost, 2),
                "labor_overhead": round(labor_overhead, 2),
                "qc_testing": round(qc_cost, 2),
            },
            "scale_scenarios": {
                "lab_dose_cost": round(total_cost, 2),
                "pilot_dose_cost": round(total_cost * 0.85, 2),
                "commercial_dose_cost": round(scale_adjusted_cost, 2),
            },
        }

    @staticmethod
    def _estimate_cycle_time(design_inputs: TrialDesignInputs) -> float:
        """Estimate manufacturing batch cycle time in days"""
        # Base synthesis + encapsulation
        base_time = 2.0  # days
        
        # PEG grafting adds time
        if design_inputs.peg_surface_coating:
            base_time += 1.0
        
        # Targeting ligand conjugation
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            base_time += 1.5
        
        # Purification/formulation
        base_time += 1.0
        
        # QC testing (parallel, but add 1 day for batch-release)
        base_time += 1.0
        
        return base_time

    @staticmethod
    def _assess_gmp_readiness(design_inputs: TrialDesignInputs) -> str:
        """Assess process readiness for GMP manufacturing"""
        complexity_score = (
            ManufacturingEngine._assess_process_complexity(design_inputs)["score"] +
            ManufacturingEngine._assess_qc_requirements(design_inputs)["score"]
        ) / 2.0
        
        if complexity_score < 40:
            return "GMP-Ready: Process is well-established for regulatory manufacturing"
        elif complexity_score < 70:
            return "GMP-Feasible: Requires process development (6-12 months); moderate regulatory pathway"
        else:
            return "GMP-Challenging: Significant process development (12-24 months) required; complex regulatory strategy needed"

    @staticmethod
    def _identify_crit_params(design_inputs: TrialDesignInputs) -> List[str]:
        """Identify critical process parameters requiring tight control"""
        crit_params = [
            "Core particle size (±10nm target)",
            "Encapsulation efficiency (target 80%+)",
        ]
        
        if design_inputs.peg_surface_coating:
            crit_params.append(f"PEG density ({design_inputs.peg_density_percent}% ±5%)")
        
        if design_inputs.encapsulation_method.lower() == "active_loading":
            crit_params.append("Internal pH gradient (target pH 5.5-6.5)")
        
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            crit_params.append(f"Ligand coupling ratio (target {design_inputs.targeting_ligand} >90% efficient)")
        
        return crit_params

    @staticmethod
    def _generate_roadmap(design_inputs: TrialDesignInputs) -> str:
        """Generate manufacturing development roadmap"""
        lines = [
            "MANUFACTURING DEVELOPMENT ROADMAP:",
            "Phase 1 (Months 0-3): Process Characterization",
            "  • Optimize synthesis parameters for target size",
            "  • Develop encapsulation method; aim for 80%+ efficiency",
            "  • Establish quality control methods",
            "",
            "Phase 2 (Months 3-6): Scale-up to Pilot (1kg batches)",
            "  • Implement process controls; test batch reproducibility",
            "  • Validate QC analytical methods",
            "  • Stability testing (accelerated 3-month study)",
            "",
            "Phase 3 (Months 6-12): Manufacturing Process Development",
            "  • Design of Experiments (DOE) for critical parameters",
            "  • Equipment qualification; GMP facility readiness",
            "  • Regulatory interactions (IND-enabling toxicology)",
            "",
            "Phase 4 (Months 12+): Commercial Scale-up",
            "  • Full commercial manufacturing (100kg+ batches)",
            "  • GMP compliance; clean room operations",
            "  • Regulatory approval pathway (NDA or BLA)",
        ]
        
        if design_inputs.encapsulation_method.lower() == "active_loading":
            lines.insert(6, "  ⚠️ PRIORITY: Automate pH-gradient loading; critical for consistency at scale")
        
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            lines.insert(8, "  ⚠️ PRIORITY: Validate ligand coupling efficiency; QA critical for batch-to-batch variability")
        
        return "\n".join(lines)

    @staticmethod
    def _identify_bottlenecks(risk_dicts: List[Dict]) -> List[Tuple[str, float, str]]:
        """Identify top manufacturing bottlenecks from risk assessment"""
        bottlenecks = [
            ("Size Control", risk_dicts[0]["score"], risk_dicts[0]["primary_driver"]),
            ("Process Complexity", risk_dicts[1]["score"], risk_dicts[1]["primary_driver"]),
            ("QC Requirements", risk_dicts[2]["score"], risk_dicts[2]["primary_driver"]),
            ("Scale-up Risk", risk_dicts[3]["score"], risk_dicts[3]["primary_driver"]),
        ]
        
        # Sort by difficulty score and return top 2-3
        bottlenecks.sort(key=lambda x: x[1], reverse=True)
        return bottlenecks[:3]

    @staticmethod
    def _calculate_overall_manufacturability(risk_dicts: List[Dict]) -> float:
        """
        Calculate overall manufacturability score.
        Higher = easier to manufacture. Inverts difficulty scores.
        """
        scores = [item["score"] for item in risk_dicts]
        avg_difficulty = sum(scores) / len(scores)
        
        # Convert from difficulty (0-100, higher=worse) to manufacturability (0-100, higher=better)
        manufacturability = 100.0 - avg_difficulty
        return manufacturability

    @staticmethod
    def _generate_manufacturability_narrative(
        design_inputs: TrialDesignInputs,
        overall_score: float,
        size_control: Dict,
        process_complexity: Dict,
        qc_requirements: Dict,
        scale_up_risk: Dict,
        bottlenecks: List[Tuple],
    ) -> str:
        """Generate comprehensive manufacturability narrative"""
        
        lines = [
            "MANUFACTURABILITY ASSESSMENT",
            "=" * 60,
            "",
            f"Overall Manufacturability Score: {overall_score:.0f}/100",
            "",
        ]
        
        # Assessment interpretation
        if overall_score >= 75:
            lines.append("EXCELLENT: Formulation is highly manufacturable with standard techniques")
        elif overall_score >= 60:
            lines.append("GOOD: Formulation is manufacturableWith process development (6-12 months)")
        elif overall_score >= 45:
            lines.append("MODERATE: Formulation requires significant process development (12-24 months)")
        else:
            lines.append("CHALLENGING: Formulation requires extensive R&D; high commercial scale-up risk")
        
        lines.extend([
            "",
            "DETAILED ASSESSMENT:",
            f"• Size Control: {size_control['primary_driver']}",
            f"• Process Complexity: {len(process_complexity['process_steps'])} steps; {process_complexity['primary_driver']}",
            f"• QC Requirements: {len(qc_requirements['required_tests'])} test methods",
            f"• Scale-up Risk: {scale_up_risk['primary_driver']}",
            "",
            "TOP BOTTLENECKS:",
        ])
        
        for i, (aspect, score, driver) in enumerate(bottlenecks, 1):
            lines.append(f"  {i}. {aspect} ({score:.0f}/100 difficulty): {driver}")
        
        return "\n".join(lines)

    @staticmethod
    def _calculate_mfg_confidence() -> float:
        """Manufacturing assessment confidence"""
        # Manufacturing assessment based on well-established pharmaceutical processes
        # Confidence is high for standard techniques, lower for novel combinations
        return 0.75
