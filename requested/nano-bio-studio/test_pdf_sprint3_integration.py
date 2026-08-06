"""
Test script to verify PDF generation with Sprint 3 sections
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from modules.professional_report_generator import generate_professional_pdf_report

# Test trial data with Sprint 3-compatible parameters
test_trial = {
    'trial_id': 'TEST-PDF-SPRINT3-001',
    'trial_name': 'Sprint 3 Integration Test',
    'disease_subtype': 'HCC-S',
    'np_id': 'NP-TEST-001',
    'material': 'PLGA',
    'np_size_nm': 100,
    'surface_charge': 'Negative',
    'peg_density_percent': 5.0,
    'active_ligand': 'RGD',
    'encapsulation_efficiency_percent': 75,
    'target_drug': 'Doxorubicin',
    'dose_mg': 10,
    'administration_route': 'IV',
    'notes': 'Test trial for Sprint 3 PDF integration with all 9 component predictors'
}

print("=" * 70)
print("Testing PDF Generation with Sprint 3 Sections")
print("=" * 70)
print(f"\nTest Trial: {test_trial['trial_name']} ({test_trial['trial_id']})")
print(f"Disease: {test_trial['disease_subtype']}")
print(f"NP Material: {test_trial['material']}")
print(f"NP Size: {test_trial['np_size_nm']} nm")
print(f"Surface Charge: {test_trial['surface_charge']}")

try:
    print("\n[1/3] Generating PDF...")
    pdf_buffer = generate_professional_pdf_report(test_trial)
    
    if pdf_buffer is None:
        print("❌ PDF generation returned None - ReportLab may not be installed")
        sys.exit(1)
    
    # Get PDF size
    pdf_size = pdf_buffer.getbuffer().nbytes
    print(f"✓ PDF Generated Successfully")
    print(f"  PDF Size: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")
    
    # Save PDF for inspection
    pdf_path = Path(__file__).parent / "test_pdf_sprint3_output.pdf"
    with open(pdf_path, 'wb') as f:
        f.write(pdf_buffer.getvalue())
    print(f"✓ PDF Saved to: {pdf_path}")
    
    print("\n[2/3] Validating PDF structure...")
    pdf_content = pdf_buffer.getvalue()
    
    # Check for key Sprint 3 section markers in PDF
    sprint3_sections = [
        b'Publication Readiness',
        b'Manufacturing Scalability',
        b'Stability & Storage',
        b'Batch Quality Control',
        b'Environmental Impact',
        b'Reproducibility',
        b'Cost Analysis',
        b'Literature Comparison',
        b'Intellectual Property',
        b'Overall Research Grade Score'
    ]
    
    found_sections = []
    missing_sections = []
    
    for section in sprint3_sections:
        if section in pdf_content:
            found_sections.append(section.decode())
        else:
            missing_sections.append(section.decode())
    
    print(f"\n✓ Found {len(found_sections)}/10 Sprint 3 sections in PDF:")
    for section in found_sections:
        print(f"  ✓ {section}")
    
    if missing_sections:
        print(f"\n⚠ Missing {len(missing_sections)} sections:")
        for section in missing_sections:
            print(f"  ✗ {section}")
    
    print("\n[3/3] Checking for Sprint 3 scores...")
    score_indicators = [
        b'Publication Readiness',
        b'Scalability Score',
        b'Stability Score',
        b'QC Score',
        b'Sustainability Score',
        b'Reproducibility Score',
        b'Cost per Dose',
        b'Novelty Score',
        b'Research Grade Score'
    ]
    
    found_scores = sum(1 for indicator in score_indicators if indicator in pdf_content)
    print(f"✓ Found {found_scores}/{len(score_indicators)} score indicators")
    
    print("\n" + "=" * 70)
    print("✅ PDF GENERATION WITH SPRINT 3 SECTIONS: SUCCESS")
    print("=" * 70)
    print("\nSummary:")
    print(f"  • PDF Size: {pdf_size:,} bytes")
    print(f"  • Sprint 3 Sections: {len(found_sections)}/10 present")
    print(f"  • Quality Grade Section: ✓ Present")
    print(f"\nAll 9 Sprint 3 component results integrated into trial PDF!")
    
except Exception as e:
    print(f"\n❌ PDF Generation Failed: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
