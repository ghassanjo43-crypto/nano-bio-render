#!/usr/bin/env python3
"""
Quick test script for professional report generator
Run: python test_report_generator.py
"""

import sys
import os
from datetime import datetime
from io import BytesIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from professional_report_generator import (
    generate_professional_pdf_report,
    infer_missing_parameters,
    simulate_biological_environment,
    calculate_delivery_metrics,
    generate_executive_summary,
    generate_mechanistic_interpretation,
    generate_optimization_recommendations,
    DISEASE_CONTEXT,
    DRUG_PROPERTIES
)

def test_inference():
    """Test parameter inference"""
    print("\n" + "="*70)
    print("TEST 1: Parameter Inference")
    print("="*70)
    
    incomplete_trial = {
        'trial_id': 'TEST-001',
        'disease_subtype': 'HCC-S',
        'drug_name': 'Sorafenib',
        'np_size_nm': 115,
        'np_charge_mv': 18,
        'np_peg_percent': 28,
        # Missing: zeta_potential, PDI, encapsulation, circulation, treatment params
    }
    
    print(f"\nInput trial (incomplete):")
    for key, val in incomplete_trial.items():
        print(f"  {key}: {val}")
    
    complete_trial = infer_missing_parameters(incomplete_trial)
    
    print(f"\nInferred parameters:")
    inferred_keys = [k for k in complete_trial.keys() if k.endswith('_inferred')]
    for key in inferred_keys:
        param_name = key.replace('_inferred', '')
        value = complete_trial.get(param_name)
        print(f"  {param_name}: {value} [INFERRED]")
    
    return complete_trial

def test_biological_environment(trial):
    """Test biological environment simulation"""
    print("\n" + "="*70)
    print("TEST 2: Biological Environment Simulation")
    print("="*70)
    
    bio_env = simulate_biological_environment(trial, 'HCC-S')
    
    print("\nSimulated tumor microenvironment:")
    for param, value in bio_env.items():
        print(f"  {param}: {value}")
    
    return bio_env

def test_delivery_metrics(trial, bio_env):
    """Test delivery prediction metrics"""
    print("\n" + "="*70)
    print("TEST 3: AI Delivery Prediction Metrics")
    print("="*70)
    
    metrics = calculate_delivery_metrics(trial, bio_env)
    
    print("\nCalculated delivery metrics:")
    for metric, value in metrics.items():
        print(f"  {metric}: {value}")
    
    return metrics

def test_narrative_generation(trial, metrics, bio_env):
    """Test narrative generation"""
    print("\n" + "="*70)
    print("TEST 4: AI-Generated Narratives")
    print("="*70)
    
    # Executive summary
    exec_summary = generate_executive_summary(trial, metrics, 'HCC-S')
    print("\nExecutive Summary:")
    print(f"  {exec_summary[:200]}...")
    
    # Mechanistic interpretation
    mech = generate_mechanistic_interpretation(trial, metrics, bio_env)
    print("\nMechanistic Interpretation:")
    print(f"  {mech[:200]}...")
    
    # Recommendations
    recs = generate_optimization_recommendations(trial, metrics)
    print("\nOptimization Recommendations:")
    for i, rec in enumerate(recs[:3], 1):
        print(f"  {i}. {rec[:80]}...")
    
    return exec_summary, mech, recs

def test_pdf_generation(trial):
    """Test PDF generation"""
    print("\n" + "="*70)
    print("TEST 5: PDF Generation")
    print("="*70)
    
    pdf_buffer = generate_professional_pdf_report(trial)
    
    if pdf_buffer:
        size_kb = len(pdf_buffer.getvalue()) / 1024
        print(f"\n✓ PDF generated successfully")
        print(f"  Size: {size_kb:.1f} KB")
        print(f"  Pages: 3-4 (estimated)")
        
        # Save test file
        output_path = 'test_professional_report.pdf'
        with open(output_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        print(f"  Saved to: {output_path}")
        
        return True
    else:
        print("\n✗ PDF generation failed")
        return False

def test_disease_contexts():
    """Display available disease models"""
    print("\n" + "="*70)
    print("TEST 6: Available Disease Models")
    print("="*70)
    
    print(f"\nRegistered diseases ({len(DISEASE_CONTEXT)}):")
    for code, disease in DISEASE_CONTEXT.items():
        print(f"  {code}: {disease['full_name']}")
        print(f"      EPR baseline: {disease['epr_baseline']}")
        print(f"      Barriers: {len(disease['barriers'])}")

def test_drug_database():
    """Display available drugs"""
    print("\n" + "="*70)
    print("TEST 7: Drug Database")
    print("="*70)
    
    print(f"\nRegistered drugs ({len(DRUG_PROPERTIES)}):")
    for drug_name, props in DRUG_PROPERTIES.items():
        dose_range = props['typical_dose_range']
        print(f"  {drug_name}: {props['class']}")
        print(f"      Typical dose: {dose_range[0]}-{dose_range[1]} mg/kg")
        print(f"      Route: {props['route']} | Frequency: {props['frequency']}")

def run_all_tests():
    """Run complete test suite"""
    print("\n" + "#"*70)
    print("# NanoBio Studio - Professional Report Generator Test Suite")
    print("#"*70)
    
    # Create test trial
    test_trial = {
        'trial_id': 'TEST-HCC-20260316-001',
        'disease_name': 'Hepatocellular Carcinoma',
        'disease_subtype': 'HCC-S',
        'drug_name': 'Sorafenib',
        'np_size_nm': 115,
        'np_charge_mv': 18,
        'np_peg_percent': 28,
        'creation_timestamp': datetime.now().isoformat(),
        # Incomplete parameters will be inferred
    }
    
    try:
        # Run tests
        complete_trial = test_inference()
        bio_env = test_biological_environment(complete_trial)
        metrics = test_delivery_metrics(complete_trial, bio_env)
        narratives = test_narrative_generation(complete_trial, metrics, bio_env)
        pdf_ok = test_pdf_generation(complete_trial)
        test_disease_contexts()
        test_drug_database()
        
        # Summary
        print("\n" + "#"*70)
        print("# Test Summary")
        print("#"*70)
        print("\n✓ All tests completed successfully!")
        print("\nKey metrics generated:")
        print(f"  - Target Delivery: {metrics['target_delivery_efficiency']:.1f}%")
        print(f"  - Immune Capture Risk: {metrics['immune_capture_risk']:.1f}%")
        print(f"  - Tumor Penetration: {metrics['tumor_penetration_score']:.1f}%")
        print(f"  - Therapeutic Index: {metrics['therapeutic_index_estimate']:.1f}%")
        
        if pdf_ok:
            print("\n✓ PDF report generated and saved")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error:")
        print(f"  {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
