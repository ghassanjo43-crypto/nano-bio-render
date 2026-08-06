"""
Test & Validation: Scientific Report Generation System
Demonstrates complete workflow from trial design to comprehensive scientific report
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from models.scientific_assessment import (
    TrialDesignInputs,
    ConfidenceLevel,
    EvidenceLevel,
)
from config.disease_profiles import list_supported_diseases
from reports.scientific_report_generator import ScientificReportGenerator


def test_complete_workflow():
    """
    Complete end-to-end test: Design inputs → Full Scientific Report
    """
    
    print("\n" + "="*80)
    print("SCIENTIFIC REPORT GENERATION - COMPLETE WORKFLOW TEST")
    print("="*80 + "\n")
    
    # Step 1: Create example trial design
    print("STEP 1: Creating trial design inputs...")
    trial_design = TrialDesignInputs(
        case_id="TEST-001",
        disease_code="HCC-S",
        trial_name="PEG-Targeted Doxorubicin Nanoparticles for HCC",
        trial_description="Passive + active targeting approach for improved hepatocellular carcinoma delivery",
        nanoparticle_size_nm=110.0,  # Optimal EPR window
        surface_charge_mv=-15.0,     # Slight negative charge
        peg_surface_coating=True,
        peg_density_percent=55.0,
        encapsulation_method="active_loading",
        targeting_ligand="Anti-ASGPR",
        payload_drug="Doxorubicin",
        payload_loading_percent=8.5,
        manufacturing_scale_target="kg",
        notes="Design targets improved HCC delivery via combined EPR + receptor targeting"
    )
    
    print(f"  ✓ Trial ID: {trial_design.case_id}")
    print(f"  ✓ Disease: {trial_design.disease_code}")
    print(f"  ✓ Formulation: {trial_design.nanoparticle_size_nm}nm, ", end="")
    print(f"PEG+{trial_design.peg_density_percent}%, ", end="")
    print(f"targeted with {trial_design.targeting_ligand}")
    print()
    
    # Step 2: Check supported diseases
    print("STEP 2: Checking supported disease profiles...")
    diseases = list_supported_diseases()
    disease_list = ", ".join(diseases)
    print(f"  ✓ {len(diseases)} disease profiles available: {disease_list}")
    print()
    
    # Step 3: Generate full scientific report
    print("STEP 3: Generating comprehensive scientific report...")
    print("  Running mechanistic engine...")
    print("  Running disease fit engine...")
    print("  Running safety engine...")
    print("  Running manufacturing engine...")
    print("  Running regulatory engine...")
    print("  Running confidence engine...")
    
    scientific_report = ScientificReportGenerator.generate_full_report(
        trial_design_inputs=trial_design,
        disease_code="HCC-S",
        trial_id="TEST-001-REPORT",
        include_appendix_mode=False,
    )
    
    print(f"  ✓ Report generated: {scientific_report.report_id}")
    print()
    
    # Step 4: Display report summary
    print("STEP 4: Scientific Report Overview")
    print("-" * 80)
    print(f"Report ID: {scientific_report.report_id}")
    print(f"Generated: {scientific_report.generated_at}")
    print(f"Mode: {scientific_report.report_mode}")
    print()
    
    # Mechanistic predictions
    print("MECHANISTIC PREDICTIONS:")
    print(f"  • Delivery Efficacy: {scientific_report.mechanistic_predictions.delivery_efficacy.value:.0f}/100")
    print(f"    Basis: {scientific_report.mechanistic_predictions.delivery_efficacy.basis}")
    print(f"  • Toxicity/Safety: {scientific_report.mechanistic_predictions.toxicity_safety.value:.0f}/100")
    print(f"  • Manufacturability: {scientific_report.mechanistic_predictions.manufacturability.value:.0f}/100")
    print(f"  • Stability: {scientific_report.mechanistic_predictions.storage_stability.value:.0f}/100")
    print(f"  • Targeting Efficacy: {scientific_report.mechanistic_predictions.targeting_efficacy.value:.0f}/100")
    print(f"  • Payload Release: {scientific_report.mechanistic_predictions.payload_release.value:.0f}/100")
    print()
    
    # Disease fit
    print("DISEASE-SPECIFIC FIT (HCC-S):")
    print(f"  • Overall Fit Score: {scientific_report.disease_biology_fit.overall_fit_score:.0f}/100")
    print(f"  • Size Appropriateness: {scientific_report.disease_biology_fit.size_appropriateness[:40]}...")
    print(f"  • Critical Mismatches: {len(scientific_report.disease_biology_fit.critical_mismatches)}")
    for i, mismatch in enumerate(scientific_report.disease_biology_fit.critical_mismatches[:2], 1):
        print(f"    {i}. {mismatch[:60]}...")
    print()
    
    # Safety decomposition
    print("SAFETY RISK PROFILE (6 Components):")
    safety = scientific_report.safety_risk_profile
    print(f"  • Overall Safety Score: {safety.overall_safety_score:.0f}/100")
    print(f"  • Systemic Toxicity: {safety.systemic_toxicity.risk_band} ({safety.systemic_toxicity.risk_score:.0f}/100)")
    print(f"  • Immunogenicity: {safety.immunogenicity.risk_band} ({safety.immunogenicity.risk_score:.0f}/100)")
    print(f"  • Off-Target Effects: {safety.off_target_effects.risk_band} ({safety.off_target_effects.risk_score:.0f}/100)")
    print(f"  • Aggregation Risk: {safety.aggregation_risk.risk_band} ({safety.aggregation_risk.risk_score:.0f}/100)")
    print(f"  • Premature Release: {safety.premature_payload_release.risk_band} ({safety.premature_payload_release.risk_score:.0f}/100)")
    print(f"  • Metabolic Burden: {safety.metabolic_burden.risk_band} ({safety.metabolic_burden.risk_score:.0f}/100)")
    print()
    
    # Manufacturing feasibility
    print("MANUFACTURABILITY ASSESSMENT:")
    mfg = scientific_report.manufacturability_assessment
    print(f"  • Overall Manufacturability: {mfg.overall_manufacturability_score:.0f}/100")
    print(f"  • Batch Consistency (CV%): {mfg.batch_consistency_prediction:.1f}%")
    print(f"  • Est. Cost/Dose: ${mfg.estimated_cost_per_dose_usd:.2f}")
    print(f"  • Cycle Time: {mfg.batch_cycle_time_days:.1f} days")
    print(f"  • GMP Pathway: {mfg.gmp_pathway_readiness[:40]}...")
    print()
    
    # Regulatory positioning
    print("REGULATORY ASSESSMENT:")
    reg = scientific_report.regulatory_assessment
    print(f"  • Current Stage: {reg.current_regulatory_stage.replace('_', ' ').title()}")
    print(f"  • Category: {reg.regulatory_category}")
    print(f"  • Strategy: {reg.primary_regulatory_strategy}")
    print(f"  • Critical Risks: {len(reg.critical_regulatory_risks)}")
    for i, risk in enumerate(reg.critical_regulatory_risks[:2], 1):
        print(f"    {i}. {risk[:60]}...")
    print()
    
    # Confidence & Evidence
    print("CONFIDENCE & EVIDENCE PROFILE:")
    conf = scientific_report.confidence_evidence_profile
    print(f"  • Overall Scientific Confidence: {conf.overall_scientific_confidence*100:.0f}%")
    print(f"  • Mechanistic Confidence: {conf.mechanistic_confidence*100:.0f}%")
    print(f"  • Safety Confidence: {conf.safety_confidence*100:.0f}%")
    print(f"  • Disease Fit Confidence: {conf.disease_fit_confidence*100:.0f}%")
    print(f"  • Manufacturing Confidence: {conf.manufacturing_confidence*100:.0f}%")
    print(f"  • High-Conf Predictions: {len(conf.predictions_with_high_confidence)}")
    print(f"  • Low-Conf Predictions: {len(conf.predictions_with_low_confidence)}")
    print()
    
    # Overall quality
    print("OVERALL REPORT QUALITY:")
    print(f"  • Scientific Quality Score: {scientific_report.overall_scientific_quality_score:.0f}/100")
    print(f"  • Report Completeness: {scientific_report.is_complete()}")
    print(f"  • Completeness %: {scientific_report.completeness_percentage():.0f}%")
    print()
    
    # Step 5: Generate investor summary
    print("STEP 5: Generating investor summary...")
    investor_summary = ScientificReportGenerator.generate_investor_summary(scientific_report)
    print()
    print(investor_summary)
    print()
    
    print("="*80)
    print("✓ COMPLETE WORKFLOW TEST SUCCESSFUL")
    print("="*80 + "\n")
    
    return scientific_report


def test_confidence_analysis():
    """
    Test confidence & evidence analysis
    """
    print("\n" + "="*80)
    print("CONFIDENCE & EVIDENCE ANALYSIS - DETAILED TEST")
    print("="*80 + "\n")
    
    trial_design = TrialDesignInputs(
        case_id="TEST-CONF-001",
        disease_code="PDAC-I",
        nanoparticle_size_nm=125.0,
        surface_charge_mv=0.0,
        peg_surface_coating=True,
        peg_density_percent=50.0,
        encapsulation_method="nanoprecipitation",
        targeting_ligand="None",
        payload_drug="Gemcitabine",
        payload_loading_percent=12.0,
    )
    
    report = ScientificReportGenerator.generate_full_report(
        trial_design_inputs=trial_design,
        disease_code="PDAC-I",
        trial_id="TEST-CONF-REPORT",
    )
    
    print("CONFIDENCE ANALYSIS FOR PDAC FORMULATION:")
    print("-"*80)
    print(report.confidence_evidence_profile.detailed_narrative)
    print()
    
    print("RECOMMENDATIONS FOR CONFIDENCE IMPROVEMENT:")
    for i, rec in enumerate(report.confidence_evidence_profile.recommended_confidence_improvements, 1):
        print(f"  {i}. {rec}")
    print()


def test_safety_decomposition():
    """
    Test 6-component safety decomposition
    """
    print("\n" + "="*80)
    print("SAFETY DECOMPOSITION - DETAILED TEST")
    print("="*80 + "\n")
    
    trial_design = TrialDesignInputs(
        case_id="TEST-SAFETY-001",
        disease_code="HCC-S",
        nanoparticle_size_nm=95.0,
        surface_charge_mv=8.0,
        peg_surface_coating=True,
        peg_density_percent=60.0,
        encapsulation_method="active_loading",
        targeting_ligand="Anti-ASGPR",
        payload_drug="Doxorubicin",
        payload_loading_percent=10.0,
    )
    
    report = ScientificReportGenerator.generate_full_report(
        trial_design_inputs=trial_design,
        disease_code="HCC-S",
        trial_id="TEST-SAFETY-REPORT",
    )
    
    print("6-COMPONENT SAFETY BREAKDOWN:")
    print("-"*80)
    print(report.safety_risk_profile.risk_summary_narrative)
    print()
    
    print(f"MITIGATION PRIORITIES (High/Critical Risk):")
    for component in report.safety_risk_profile.mitigation_priorities:
        print(f"  ⚠️ {component.component_name}:")
        print(f"     Risk Band: {component.risk_band}")
        print(f"     Score: {component.risk_score:.0f}/100")
        print(f"     Strategies: {component.mitigation_strategies[:2]}")
    print()


if __name__ == "__main__":
    # Run all tests
    test_complete_workflow()
    test_confidence_analysis()
    test_safety_decomposition()
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED SUCCESSFULLY")
    print("="*80)
