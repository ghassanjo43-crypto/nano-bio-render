"""
Safety Risk Decomposition Engine for NanoBio Studio
Breaks down nanoparticle safety into 6 independent risk components
"""

from dataclasses import dataclass
from typing import List, Tuple
from models.scientific_assessment import (
    SafetyRiskProfile,
    SafetyRiskComponent,
    TrialDesignInputs,
)
from config.scoring_config import get_confidence_label


@dataclass
class RiskBand:
    """Classification of risk severity"""
    name: str
    threshold_min: float
    threshold_max: float
    color: str  # For UI visualization
    mitigation_priority: int  # 1=critical, 5=low


class SafetyEngine:
    """
    Decomposes nanoparticle safety into 6 independent risk dimensions.
    Each assessed separately with transparent rationale for regulatory positioning.
    """

    # Risk band definitions (0-100 scale, where 100 = maximum risk)
    RISK_BANDS = [
        RiskBand("Critical", 80.0, 100.0, "#ff0000", 1),
        RiskBand("High", 60.0, 79.9, "#ff6600", 2),
        RiskBand("Moderate", 40.0, 59.9, "#ffcc00", 3),
        RiskBand("Low", 20.0, 39.9, "#99cc00", 4),
        RiskBand("Minimal", 0.0, 19.9, "#00cc00", 5),
    ]

    @staticmethod
    def assess_safety_profile(design_inputs: TrialDesignInputs) -> SafetyRiskProfile:
        """
        Comprehensive 6-component safety decomposition.
        
        Returns:
            SafetyRiskProfile with component breakdown
        """
        
        components = {
            "systemic_toxicity": SafetyEngine._assess_systemic_toxicity(design_inputs),
            "immunogenicity": SafetyEngine._assess_immunogenicity(design_inputs),
            "off_target_effects": SafetyEngine._assess_off_target_effects(design_inputs),
            "aggregation_risk": SafetyEngine._assess_aggregation_risk(design_inputs),
            "premature_release": SafetyEngine._assess_premature_payload_release(design_inputs),
            "metabolic_burden": SafetyEngine._assess_metabolic_burden(design_inputs),
        }
        
        # Calculate overall safety risk (inverse of safety: lower = better)
        component_risks = [c.risk_score for c in components.values()]
        overall_risk = sum(component_risks) / len(component_risks) if component_risks else 50.0
        
        # Convert risk to safety score (100 - risk = safety, where 100 = very safe)
        overall_safety = 100.0 - overall_risk
        
        confidence_score = SafetyEngine._calculate_safety_confidence()
        
        assumptions = [
            "Assumes standard pharmaceutical excipients without toxic additives",
            "Risk assessment based on in vitro and published in vivo nanoparticle safety data",
            "Does not account for drug-specific toxicity (safety of encapsulated payload assessed separately)",
            "Assumes systemic IV administration (route affects all risk components)",
            "Risk projections based on rodent models; human translation requires clinical data",
        ]
        
        # Generate narrative summary
        narrative = SafetyEngine._generate_safety_narrative(components)
        
        return SafetyRiskProfile(
            overall_safety_score=overall_safety,
            systemic_toxicity=components["systemic_toxicity"],
            immunogenicity=components["immunogenicity"],
            off_target_effects=components["off_target_effects"],
            aggregation_risk=components["aggregation_risk"],
            premature_payload_release=components["premature_release"],
            metabolic_burden=components["metabolic_burden"],
            risk_summary_narrative=narrative,
            highest_risk_component=max(components.items(), key=lambda x: x[1].risk_score)[0],
            mitigation_priorities=[
                c for c in components.values() if c.risk_band == "Critical" or c.risk_band == "High"
            ],
            assumptions=assumptions,
            confidence_level=get_confidence_label(confidence_score),
            numeric_confidence=confidence_score,
        )

    @staticmethod
    def _assess_systemic_toxicity(design_inputs: TrialDesignInputs) -> SafetyRiskComponent:
        """
        Direct nanoparticle cytotoxicity and organ damage.
        
        Factors:
        - Particle size (affects cell uptake kinetics)
        - Surface composition (material toxicity)
        - Clearance rate (determines exposure)
        """
        base_risk = 30.0
        adjustments = []
        
        # Size-dependent cellular uptake
        size = design_inputs.nanoparticle_size_nm
        if size < 50:
            # Very small particles more efficiently internalized
            adjustments.append(("Very small size (<50nm) enhances cellular uptake", 15.0))
        elif 80 <= size <= 150:
            # Optimal size for EPR; lower cellular uptake
            adjustments.append(("Optimal size range (80-150nm) limits unwanted cellular uptake", -10.0))
        elif size > 200:
            # Large particles may accumulate
            adjustments.append(("Large particles (>200nm) may accumulate in organs", 8.0))
        
        # PEG coating reduces cellular interaction
        if design_inputs.peg_surface_coating:
            adjustments.append(("PEG coating reduces direct cell-nanoparticle contact", -12.0))
        
        # Material concern: assume standard biocompatible materials
        # (specific material toxicity would be assessed separately)
        
        risk_score = max(0.0, min(100.0, base_risk + sum(adj[1] for adj in adjustments)))
        rationale = "Systemic toxicity risk reflects potential for direct cytotoxic effects. "
        rationale += "Minimized by: (1) optimal particle size in EPR window, (2) PEG stealth coating. "
        rationale += "Assumes biocompatible material composition (e.g., FDA-approved polymers)."
        
        risk_band = SafetyEngine._classify_risk(risk_score)
        
        return SafetyRiskComponent(
            component_name="systemic_toxicity",
            risk_score=risk_score,
            risk_band=risk_band,
            primary_drivers=dict((name, val) for name, val in adjustments),
            rationale=rationale,
            mitigation_strategies=[
                "Use FDA-approved materials (PLGA, PEG, liposomes)",
                "Maintain size 80-150nm for optimal clearance kinetics",
                "Include PEG surface coating for RES evasion",
                "Perform acute toxicity studies (LD50) in rodent models",
            ],
        )

    @staticmethod
    def _assess_immunogenicity(design_inputs: TrialDesignInputs) -> SafetyRiskComponent:
        """
        Innate immune activation and inflammation.
        
        Factors:
        - PEG coating (primary immunoevader)
        - Surface charge (affects complement activation)
        - Particulate size (activates pattern recognition)
        """
        base_risk = 60.0  # Nanoparticles inherently immunogenic
        adjustments = []
        
        # PEG coating dramatically reduces immune activation
        if design_inputs.peg_surface_coating:
            peg_benefit = -35.0  # Strong immune-suppressing effect
            adjustments.append((f"PEG {design_inputs.peg_density_percent}% coating provides immune evasion", peg_benefit))
        else:
            adjustments.append(("No PEG coating; bare nanoparticles highly immunogenic", 25.0))
        
        # Surface charge affects complement cascade
        charge = design_inputs.surface_charge_mv
        if abs(charge) < 10:
            adjustments.append(("Neutral charge minimizes complement activation", -8.0))
        elif abs(charge) > 30:
            adjustments.append((f"High charge {charge}mV promotes complement cascade", 10.0))
        
        # Targeting ligand may add immunogenicity if protein-derived
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            adjustments.append(("Protein ligand may have immunogenic epitopes", 5.0))
        
        risk_score = max(0.0, min(100.0, base_risk + sum(adj[1] for adj in adjustments)))
        
        rationale = "Immunogenicity reflects innate immune system recognition and activation. "
        rationale += "Primary driver is PEG surface coating; secondary factors include surface charge. "
        rationale += "Risk assessed for first-administration and repeated-dose scenarios."
        
        risk_band = SafetyEngine._classify_risk(risk_score)
        
        return SafetyRiskComponent(
            component_name="immunogenicity",
            risk_score=risk_score,
            risk_band=risk_band,
            primary_drivers=dict((name, val) for name, val in adjustments),
            rationale=rationale,
            mitigation_strategies=[
                "Maximize PEG density on surface (>50% target)",
                "Maintain neutral or near-neutral surface charge",
                "Use humanized or synthetic targeting ligands to avoid epitopes",
                "Consider alternative immune-evasion technologies (CD47 mimicry, complement inhibitors)",
                "Perform immunogenicity assays (cytokine release, complement activation)",
            ],
        )

    @staticmethod
    def _assess_off_target_effects(design_inputs: TrialDesignInputs) -> SafetyRiskComponent:
        """
        Unintended biodistribution and off-target organ damage.
        
        Factors:
        - Size (determines RES tropism)
        - Targeting ligand specificity (if present)
        - Disease-specific vascularization
        """
        base_risk = 45.0
        adjustments = []
        
        # Size determines default biodistribution
        size = design_inputs.nanoparticle_size_nm
        if 80 <= size <= 150:
            adjustments.append(
                ("Optimal size for EPR targeting; minimal RES sequestration", -12.0)
            )
        elif size < 80:
            adjustments.append(
                ("Small size: high renal filtration and potential glomerular injury", 10.0)
            )
        elif size > 180:
            adjustments.append(
                ("Large size: high hepatic and splenic accumulation", 15.0)
            )
        
        # Targeting ligand improves specificity
        if design_inputs.targeting_ligand and design_inputs.targeting_ligand.lower() != "none":
            adjustments.append(
                (f"Targeting ligand ({design_inputs.targeting_ligand}) improves specificity", -15.0)
            )
        else:
            adjustments.append(
                ("No targeting: relies on passive EPR; broad biodistribution", 5.0)
            )
        
        # Surface charge affects organ uptake
        charge = design_inputs.surface_charge_mv
        if charge > 20:
            adjustments.append(("Positive charge: liver uptake, potential hepatotoxicity", 8.0))
        elif charge < -20:
            adjustments.append(("Negative charge: spleen uptake, less hepatic", -3.0))
        
        risk_score = max(0.0, min(100.0, base_risk + sum(adj[1] for adj in adjustments)))
        
        rationale = "Off-target effects risk reflects potential for unwanted biodistribution. "
        rationale += "Minimized by: (1) active targeting ligand, (2) optimal size for EPR + disease vasculature. "
        rationale += "Remaining risk primarily in liver/kidney chronic exposure."
        
        risk_band = SafetyEngine._classify_risk(risk_score)
        
        return SafetyRiskComponent(
            component_name="off_target_effects",
            risk_score=risk_score,
            risk_band=risk_band,
            primary_drivers=dict((name, val) for name, val in adjustments),
            rationale=rationale,
            mitigation_strategies=[
                "Implement active targeting strategy to improve selectivity",
                "Optimize size within EPR window (80-150nm)",
                "Perform biodistribution studies (radiolabel tracking) across organs",
                "Assess organ-specific toxicity biomarkers (liver enzymes, creatinine)",
                "Consider modified surface chemistry to reduce liver accumulation",
            ],
        )

    @staticmethod
    def _assess_aggregation_risk(design_inputs: TrialDesignInputs) -> SafetyRiskComponent:
        """
        In vivo aggregation and vascular occlusion risk.
        
        Factors:
        - PEG coating (prevents aggregation)
        - Surface charge (affects colloidal stability)
        - Protein corona formation
        """
        base_risk = 50.0
        adjustments = []
        
        # PEG coating is primary aggregation prevention
        if design_inputs.peg_surface_coating:
            peg_benefit = -25.0
            adjustments.append(
                (f"PEG {design_inputs.peg_density_percent}% provides steric stabilization", peg_benefit)
            )
        else:
            adjustments.append(
                ("No PEG; bare nanoparticles highly susceptible to aggregation", 20.0)
            )
        
        # Charge affects electrostatic stabilization
        charge = design_inputs.surface_charge_mv
        if abs(charge) > 25:
            adjustments.append(
                (f"High charge {charge}mV provides electrostatic stabilization", -8.0)
            )
        elif abs(charge) < 10 and not design_inputs.peg_surface_coating:
            adjustments.append(
                ("Neutral, non-PEGylated: highly aggregation-prone", 15.0)
            )
        
        # Protein corona promotes aggregation
        adjustments.append(
            ("Protein corona formation inevitable in blood; PEG mitigates", -3.0)
        )
        
        risk_score = max(0.0, min(100.0, base_risk + sum(adj[1] for adj in adjustments)))
        
        rationale = "Aggregation risk reflects potential for in vivo particle-particle interactions. "
        rationale += "Primary mitigation: PEG coating (steric barrier) + electrostatic stabilization. "
        rationale += "High aggregation risk leads to vascular occlusion, thrombosis, microinfarction."
        
        risk_band = SafetyEngine._classify_risk(risk_score)
        
        return SafetyRiskComponent(
            component_name="aggregation_risk",
            risk_score=risk_score,
            risk_band=risk_band,
            primary_drivers=dict((name, val) for name, val in adjustments),
            rationale=rationale,
            mitigation_strategies=[
                "Maximize PEG surface density (>50% target)",
                "Use combined electrostatic + steric stabilization",
                "Perform stability testing in simulated biological fluids (PBS, blood plasma)",
                "Monitor thrombosis markers (PT/INR, platelet count) in toxicity studies",
                "Include microscopy analysis of aggregation in circulation",
            ],
        )

    @staticmethod
    def _assess_premature_payload_release(design_inputs: TrialDesignInputs) -> SafetyRiskComponent:
        """
        Risk of uncontrolled payload release in circulation.
        
        Factors:
        - Encapsulation method (passive = high release risk)
        - pH buffering in blood
        - Plasma protein interactions
        """
        base_risk = 40.0
        adjustments = []
        
        # Encapsulation method is primary determinant
        enc_method = design_inputs.encapsulation_method.lower()
        if enc_method == "passive_loading":
            adjustments.append(
                ("Passive loading: weak payload retention; rapid in-circulation release", 25.0)
            )
            base_risk = 65.0
        elif enc_method == "active_loading":
            adjustments.append(
                ("Active loading: pH-gradient retained; sustained payload retention", -20.0)
            )
        elif enc_method == "nanoprecipitation":
            adjustments.append(
                ("Nanoprecipitation: polymer encapsulation; moderate release control", -8.0)
            )
        
        # PEG may slow release
        if design_inputs.peg_surface_coating:
            adjustments.append(
                ("PEG coating creates diffusion barrier; slows payload release", -5.0)
            )
        
        # Protein corona promotes leaching
        adjustments.append(
            ("Protein corona binding may disrupt encapsulation", 3.0)
        )
        
        risk_score = max(0.0, min(100.0, base_risk + sum(adj[1] for adj in adjustments)))
        
        rationale = "Premature release risk reflects loss of payload before reaching target. "
        rationale += "Active loading dramatically reduces this risk vs passive loading. "
        rationale += "Premature release causes systemic drug exposure + off-target toxicity."
        
        risk_band = SafetyEngine._classify_risk(risk_score)
        
        return SafetyRiskComponent(
            component_name="premature_payload_release",
            risk_score=risk_score,
            risk_band=risk_band,
            primary_drivers=dict((name, val) for name, val in adjustments),
            rationale=rationale,
            mitigation_strategies=[
                "Use active loading / pH-gradient approach for sustained retention",
                "Incorporate membrane stabilizers (cholesterol, DSPE)",
                "Perform in vitro release kinetics in simulated circulation (37°C, pH 7.4)",
                "Monitor systemic drug concentrations to quantify release",
                "Assess off-target toxicity attributable to released payload",
            ],
        )

    @staticmethod
    def _assess_metabolic_burden(design_inputs: TrialDesignInputs) -> SafetyRiskComponent:
        """
        Cumulative metabolic/clearance burden on liver and immune system.
        
        Factors:
        - Particle dose (mg/kg)
        - Size (affects clearance kinetics)
        - Repeated dosing frequency
        """
        # Assume typical single dose; scale with size
        base_risk = 35.0
        adjustments = []
        
        # Size affects clearance rate and burden
        size = design_inputs.nanoparticle_size_nm
        if 80 <= size <= 150:
            adjustments.append(
                ("Optimal size for rapid hepatic clearance (24-48hrs)", -10.0)
            )
        elif size < 80:
            adjustments.append(
                ("Small particles: renal filtration burden on kidneys", 5.0)
            )
        elif size > 150:
            adjustments.append(
                ("Large particles: prolonged hepatic burden, slower clearance", 10.0)
            )
        
        # PEG affects clearance
        if design_inputs.peg_surface_coating:
            adjustments.append(
                (f"PEG {design_inputs.peg_density_percent}% slows clearance; increases metabolic burden", 5.0)
            )
        else:
            adjustments.append(
                ("Bare nanoparticles cleared rapidly; low chronic burden", -5.0)
            )
        
        risk_score = max(0.0, min(100.0, base_risk + sum(adj[1] for adj in adjustments)))
        
        rationale = "Metabolic burden reflects cumulative organ stress from nanoparticle processing. "
        rationale += "Optimal size achieves balance: rapid clearance (low burden) vs sufficient circulation time (delivery). "
        rationale += "Repeated dosing or high dose exacerbates burden; assess liver/kidney function post-treatment."
        
        risk_band = SafetyEngine._classify_risk(risk_score)
        
        return SafetyRiskComponent(
            component_name="metabolic_burden",
            risk_score=risk_score,
            risk_band=risk_band,
            primary_drivers=dict((name, val) for name, val in adjustments),
            rationale=rationale,
            mitigation_strategies=[
                "Optimize size for rapid clearance (80-150nm target)",
                "Monitor hepatic and renal function markers (ALT, AST, creatinine)",
                "Establish clearance kinetics via biodistribution studies (PET/SPECT imaging)",
                "Space repeated doses to allow organ recovery between administrations",
                "Consider bioaccumulation potential in repeated dosing studies",
            ],
        )

    @staticmethod
    def _classify_risk(risk_score: float) -> str:
        """Convert numeric risk score to categorical band"""
        for band in SafetyEngine.RISK_BANDS:
            if band.threshold_min <= risk_score <= band.threshold_max:
                return band.name
        return "Unknown"

    @staticmethod
    def _generate_safety_narrative(components: dict) -> str:
        """Generate comprehensive narrative safety summary"""
        lines = [
            "SAFETY RISK PROFILE SUMMARY",
            "=" * 60,
            "",
        ]
        
        for name, component in components.items():
            lines.append(f"{name.upper().replace('_', ' ')}: {component.risk_band} ({component.risk_score:.0f}/100)")
            lines.append(f"  {component.rationale[:100]}...")
            lines.append("")
        
        # Identify highest risks
        sorted_components = sorted(components.items(), key=lambda x: x[1].risk_score, reverse=True)
        if sorted_components:
            lines.append("HIGHEST RISKS (priority for mitigation):")
            for name, component in sorted_components[:2]:
                lines.append(f"  • {name}: {component.risk_band} - {component.primary_drivers}")
        
        return "\n".join(lines)

    @staticmethod
    def _calculate_safety_confidence() -> float:
        """
        Safety assessment confidence inherently lower than mechanistic
        because in vivo toxicology is context-dependent
        """
        return 0.68  # 68% confidence in safety predictions
