#!/usr/bin/env python3
"""Test database insertion and retrieval"""

import sys
sys.path.insert(0, '/d/nbs_18_march_2026')

from modules.trial_registry import create_trial_entry, get_all_trials
from datetime import datetime

print("=" * 60)
print("DATABASE INSERTION TEST")
print("=" * 60)
print()

# Test data
test_trial_id = f"TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
print(f"📝 Creating test trial: {test_trial_id}")
print()

try:
    success = create_trial_entry(
        trial_id=test_trial_id,
        disease_subtype="hcc_l",
        disease_name="Hepatocellular Carcinoma",
        drug_name="Test Drug",
        np_size_nm=100,
        np_charge_mv=-5,
        np_peg_percent=85.0,
        np_zeta_potential=-30.0,
        np_pdi=1.2,
        treatment_dose_mgkg=10.0,
        treatment_route="IV",
        treatment_frequency="Once",
        treatment_duration_days=1,
        trial_outcomes="Test successful",
        notes="Material: Test LNP"
    )
    
    if success:
        print("✅ Trial inserted successfully!")
    else:
        print("❌ Trial insertion returned False!")
    
    print()
    print("=" * 60)
    print("RETRIEVING ALL TRIALS")
    print("=" * 60)
    print()
    
    # Get all trials
    all_trials = get_all_trials()
    print(f"📊 Total trials in database: {len(all_trials)}")
    print()
    
    # Show latest 3
    print("Latest 3 trials:")
    print("-" * 80)
    for i, trial in enumerate(all_trials[:3], 1):
        trial_id = trial.get('trial_id', 'N/A')
        timestamp = trial.get('creation_timestamp', 'N/A')[:19]  # Get date+time
        print(f"{i}. {trial_id:30s} | {timestamp}")
    print("-" * 80)
    print()
    
    # Check if test trial is there
    test_found = any(trial.get('trial_id') == test_trial_id for trial in all_trials)
    if test_found:
        print(f"✅ Test trial '{test_trial_id}' FOUND in database!")
        test_trial = next(trial for trial in all_trials if trial.get('trial_id') == test_trial_id)
        print(f"   Created at: {test_trial.get('creation_timestamp')}")
    else:
        print(f"❌ Test trial '{test_trial_id}' NOT found in database!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
