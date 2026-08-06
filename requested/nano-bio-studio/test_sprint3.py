#!/usr/bin/env python
"""Quick test of Sprint 3 components"""

from components.manufacturing_scalability_predictor import predict_manufacturing_scalability
from components.batch_quality_control_predictor import predict_batch_quality_control

# Test 1: Manufacturing scalability
print("Test 1: Manufacturing scalability predictor")
test_params_mfg = {
    'Material': 'Lipid NP',
    'Size': 100,
    'Charge': -5,
    'PEG_Density': 50,
    'Encapsulation': 'Passive Loading'
}

try:
    result = predict_manufacturing_scalability(test_params_mfg)
    print('✓ Manufacturing scalability predictor works')
    print(f'  Scalability Score: {result["scalability_score"]:.0f}/100')
    print(f'  Cost per dose: ${result["cost_per_dose_usd"]:.2f}')
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()

# Test 2: Batch QC with ligand
print("\nTest 2: Batch QC predictor with ligand")
test_params_qc = {
    'Material': 'Lipid NP',
    'Size': 100,
    'Charge': -5,
    'Ligand': 'GalNAc'
}

try:
    result2 = predict_batch_quality_control(test_params_qc)
    print('✓ Batch QC predictor works')
    print(f'  QC Score: {result2["total_qc_score"]:.0f}/100')
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
