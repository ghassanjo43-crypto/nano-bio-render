# 🧪 NanoBio Studio - Testing Guide

Comprehensive testing procedures to verify all features work correctly.

---

## Pre-Testing Checklist

- [ ] Python 3.8+ installed
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Application starts without errors (`streamlit run app.py`)
- [ ] Browser opens to `http://localhost:8501`

---

## Module Testing

### 1. Materials & Targets Library

**Test Steps:**

1. Navigate to "📚 Materials & Targets" page
2. Verify nanoparticle library displays (should show 10 types)
3. Test search functionality:
   - Search "lipid" → should show LNP
   - Search "gold" → should show AuNP
4. Expand "Lipid Nanoparticle (LNP)" → verify details display
5. Click "Switch to Targets" tab
6. Verify 12 targets display
7. Expand "Tumor Tissue" → verify details display

**Expected Results:**
- ✅ All 10 nanoparticle types visible
- ✅ All 12 targets visible
- ✅ Search works correctly
- ✅ Expand/collapse works
- ✅ Details show properties, ligands, payloads, etc.

**Pass/Fail:** ___________

---

### 2. Design Nanoparticle

**Test Steps:**

1. Navigate to "🎨 Design Nanoparticle" page
2. Enter name: "Test-Design-001"
3. Select material: "Lipid Nanoparticle (LNP)"
4. Adjust size slider to 100 nm
5. Adjust charge to -10 mV
6. Select ligand: "PEG2000"
7. Select payload: "mRNA"
8. Set payload loading: 40%
9. Select target: "Tumor Tissue (Solid)"
10. Set dose: 3 mg/kg
11. Adjust PDI: 0.15
12. Verify all parameters saved (refresh page and check)

**Expected Results:**
- ✅ All sliders respond smoothly
- ✅ Dropdowns populate correctly
- ✅ Current design summary displays
- ✅ Values persist in session
- ✅ PK parameters adjustable (kabs, kel, k12, k21)
- ✅ No error messages

**Pass/Fail:** ___________

---

### 3. Delivery Simulation

**Test Steps:**

1. Navigate to "📈 Delivery Simulation" page
2. Verify design summary shows current parameters
3. Click "▶️ Run Simulation" button
4. Wait for simulation to complete (~2-3 seconds)
5. Verify two plots appear:
   - Plasma vs Tissue concentration
   - Payload Release Profile
6. Check "Key Metrics" section displays 8 parameters:
   - Plasma AUC, Plasma Cmax, Plasma Tmax, Plasma T½
   - Tissue AUC, Tissue Cmax, Tissue Tmax, Tissue/Plasma Ratio
7. Verify interpretation text appears below metrics
8. Click "💾 Export Results (CSV)"
9. Verify CSV downloads
10. Click "💾 Save Plots (PNG)"
11. Verify PNG downloads

**Expected Results:**
- ✅ Simulation runs without errors
- ✅ Both plots display correctly
- ✅ Concentration curves show expected behavior (decay over time)
- ✅ Tissue accumulation > 0
- ✅ Metrics calculated correctly
- ✅ CSV contains time, plasma, tissue, released columns
- ✅ PNG image clear and readable

**Pass/Fail:** ___________

---

### 4. Toxicity & Safety Assessment

**Test Steps:**

1. Navigate to "⚠️ Toxicity & Safety" page
2. Click "🔬 Run Safety Assessment" button
3. Verify radar chart displays with 7 axes:
   - Size Risk, Charge Risk, Dose Risk, PDI Risk
   - Ligand Risk, Payload Risk, Material Risk
4. Check "Overall Safety Assessment" displays:
   - Overall Score (0-10)
   - Risk Level (LOW/MODERATE/HIGH/VERY HIGH)
   - Risk factors breakdown
5. Verify "Safety Recommendations" section appears
6. Check "Required Preclinical Studies" checklist displays
7. Click "📥 Download Safety Report (TXT)"
8. Verify TXT downloads
9. Click "💾 Save Radar Chart (PNG)"
10. Verify PNG downloads

**Expected Results:**
- ✅ Radar chart displays properly
- ✅ All 7 risk factors calculated
- ✅ Overall score reasonable (0-10 range)
- ✅ Risk level assigned correctly
- ✅ Recommendations specific to design
- ✅ Study checklist comprehensive
- ✅ TXT report contains all safety data
- ✅ PNG chart clear

**Pass/Fail:** ___________

---

### 5. Cost Estimator

**Test Steps:**

1. Navigate to "💰 Cost Estimator" page
2. Verify design summary displays
3. Check default cost parameters (material, ligand, payload)
4. Scroll to "Batch Size Analysis" section
5. Verify 1g, 10g, 100g batches shown
6. Expand "💡 Customize Cost Parameters"
7. Modify material cost (e.g., change to 150)
8. Verify costs recalculate
9. Scroll to "📊 Cost Breakdown Visualization"
10. Verify pie chart displays
11. Check "📈 Sensitivity Analysis" section
12. Verify table shows ±20% variations
13. Click "💾 Export Cost Analysis (CSV)"
14. Verify CSV downloads

**Expected Results:**
- ✅ All costs calculate correctly
- ✅ Material, ligand, payload costs separated
- ✅ Overhead and waste factors applied
- ✅ Batch sizes show economies of scale
- ✅ Per-patient cost calculated
- ✅ Pie chart displays proportions
- ✅ Sensitivity analysis shows variations
- ✅ CSV contains complete cost breakdown

**Pass/Fail:** ___________

---

### 6. AI Protocol Generator

**Test Steps:**

1. Navigate to "🤖 AI Protocol Generator" page
2. Verify design summary displays
3. Expand "⚙️ Protocol Configuration"
4. Adjust duration: 90 days
5. Select formulation method
6. Add notes: "Test protocol generation"
7. Toggle "Include AI Suggestions" ON
8. Click "✨ Generate Protocol" button
9. Wait for protocol generation (~2-3 seconds)
10. Verify protocol appears with 10 sections:
    - Formulation Overview
    - Materials & Reagents
    - Synthesis Procedure
    - Characterization
    - In Vitro Studies
    - In Vivo Studies
    - Safety & Disposal
    - Data Analysis
    - Expected Results
    - Troubleshooting
11. Click "📥 Download Protocol (TXT)"
12. Verify TXT downloads
13. Click "📥 Download Protocol (Markdown)"
14. Verify MD downloads

**Expected Results:**
- ✅ Protocol generates without errors
- ✅ All 10 sections present
- ✅ Material-specific synthesis methods (e.g., lipid microfluidic mixing)
- ✅ Payload-specific loading methods
- ✅ Target-appropriate cell lines
- ✅ Troubleshooting section relevant
- ✅ Safety warnings included
- ✅ TXT format clean and readable
- ✅ Markdown format properly formatted

**Pass/Fail:** ___________

---

### 7. Import/Export

**Test Steps:**

#### Export:
1. Navigate to "💾 Import / Export" page
2. Go to "📤 Export Data" tab
3. Verify current design preview shows
4. Click "📥 Download Design (JSON)"
5. Save file locally
6. Open JSON file, verify contents
7. Click "📥 Download Design (CSV)"
8. Save CSV file
9. Open CSV, verify contents
10. Click "📦 Create Complete Export Package"
11. Click "📥 Download Complete Package (JSON)"
12. Verify comprehensive export includes design + simulation + safety + cost

#### Import:
1. Go to "📥 Import Design" tab
2. Upload the JSON file from step 4
3. Verify design preview displays
4. Click "✅ Load This Design"
5. Navigate to "Design Nanoparticle" page
6. Verify all parameters match imported design

#### Template:
1. Return to "Import / Export" page
2. Go to "📥 Import Design" tab
3. Scroll to "Load from Template"
4. Select "mRNA-LNP for Tumor"
5. Click "📥 Load Template"
6. Navigate to "Design Nanoparticle"
7. Verify template parameters loaded

**Expected Results:**
- ✅ JSON export contains all design parameters
- ✅ CSV export readable in Excel/Sheets
- ✅ Complete package includes all results
- ✅ Import restores exact design
- ✅ Templates load pre-configured designs
- ✅ No data loss during export/import cycle

**Pass/Fail:** ___________

---

### 8. Tutorial

**Test Steps:**

1. Navigate to "📘 Tutorial & Learning Guide" page
2. Verify learning objectives display (6 objectives)
3. Select "Introduction to Nanomedicine"
4. Verify content displays with sections
5. Select "Exercise 1: Design a Cancer Nanotherapy"
6. Verify:
   - Objective stated
   - Background provided
   - Instructions clear
   - Discussion questions present
   - Expected results listed
7. Test other exercises:
   - Exercise 2: Blood-Brain Barrier
   - Exercise 3: Cost-Benefit Analysis
   - Exercise 4: Safety Assessment
   - Advanced: Multi-Parameter Optimization
8. Verify all exercises have complete content

**Expected Results:**
- ✅ All sections load properly
- ✅ Content well-formatted
- ✅ Instructions clear and actionable
- ✅ Discussion questions thought-provoking
- ✅ Examples relevant
- ✅ Links to other pages work

**Pass/Fail:** ___________

---

### 9. Instructor Notes

**Test Steps:**

1. Navigate to "🧑‍🏫 Instructor Notes" page
2. Verify password prompt displays
3. Enter wrong password → verify error message
4. Enter correct password: `instructor2024`
5. Verify access granted
6. Check "📝 Model Answers" tab:
   - Select Exercise 1
   - Verify model answers complete
   - Check Discussion Question Answers section
7. Check "📊 Grading Rubrics" tab:
   - Verify general rubric displays
   - Check exercise-specific rubrics
   - Verify point allocations clear
8. Check "💡 Teaching Tips" tab:
   - Verify lesson plans present
   - Check discussion prompts
   - Review troubleshooting section
9. Check "📚 Additional Resources" tab:
   - Verify resource lists
   - Check recommended readings
   - Review assessment templates
10. Click "🔒 Lock (Logout)"
11. Verify returned to password prompt

**Expected Results:**
- ✅ Password protection works
- ✅ Model answers comprehensive
- ✅ Grading rubrics clear and fair
- ✅ Teaching tips practical
- ✅ Resources valuable
- ✅ Logout works properly

**Pass/Fail:** ___________

---

## Integration Testing

### End-to-End Workflow

**Test Steps:**

1. **Start fresh** (clear browser cache or use incognito)
2. **Browse Materials** → Select Lipid Nanoparticle
3. **Design** → Configure all parameters
4. **Simulate** → Run PK/PD analysis
5. **Assess Safety** → Review risk factors
6. **Calculate Cost** → Estimate expenses
7. **Generate Protocol** → Create experimental plan
8. **Export Everything** → Save complete package
9. **Import** → Load saved design
10. **Verify** → All data preserved correctly

**Expected Results:**
- ✅ Smooth workflow without errors
- ✅ Session state persists across pages
- ✅ Export/import cycle preserves data
- ✅ No crashes or freezes
- ✅ Professional user experience

**Pass/Fail:** ___________

---

## Performance Testing

### Load Test

1. Run simulation 10 times consecutively
2. Generate protocol 5 times
3. Export/import cycle 3 times
4. Check for:
   - Memory leaks
   - Slowdown over time
   - Browser responsiveness

**Expected Results:**
- ✅ Consistent performance
- ✅ No significant slowdown
- ✅ Memory usage stable
- ✅ No browser crashes

**Pass/Fail:** ___________

---

## Browser Compatibility

Test on multiple browsers:

| Browser | Version | Status | Notes |
|---------|---------|--------|-------|
| Chrome | Latest | ☐ Pass / ☐ Fail | |
| Firefox | Latest | ☐ Pass / ☐ Fail | |
| Safari | Latest | ☐ Pass / ☐ Fail | |
| Edge | Latest | ☐ Pass / ☐ Fail | |

---

## Error Handling

### Test Error Scenarios

1. **Invalid input:**
   - Size: 0 nm → should show error or limit
   - Charge: 1000 mV → should show error or limit
   - Dose: -5 mg/kg → should show error or limit

2. **Missing data:**
   - Run simulation without design → should show warning
   - Generate protocol with incomplete design → should handle gracefully

3. **File operations:**
   - Upload invalid JSON → should show error message
   - Upload non-JSON file → should reject

**Expected Results:**
- ✅ Graceful error messages
- ✅ No application crashes
- ✅ Clear user guidance
- ✅ Recovery possible

**Pass/Fail:** ___________

---

## Accessibility Testing

1. **Keyboard navigation:** Tab through all controls
2. **Screen reader:** Test with NVDA/JAWS (optional)
3. **Color contrast:** Verify text readable
4. **Mobile responsiveness:** Test on phone/tablet

**Expected Results:**
- ✅ All interactive elements keyboard accessible
- ✅ Good color contrast
- ✅ Responsive design adapts to screen size

**Pass/Fail:** ___________

---

## Final Verification

### Complete Feature Checklist

- [ ] Materials & Targets Library (browse, search, details)
- [ ] Design Nanoparticle (all 15+ parameters)
- [ ] Delivery Simulation (PK/PD model, plots, export)
- [ ] Toxicity Assessment (7 factors, radar chart, report)
- [ ] Cost Estimator (breakdown, batch analysis, sensitivity)
- [ ] Protocol Generator (10 sections, download TXT/MD)
- [ ] Import/Export (JSON, CSV, templates)
- [ ] Tutorial (6 sections, exercises, instructions)
- [ ] Instructor Notes (password, answers, rubrics, tips)
- [ ] Session persistence (design saved across pages)
- [ ] Export/Import cycle (data preservation)
- [ ] Performance (responsive, no crashes)
- [ ] Documentation (README, SETUP, this guide)

### Sign-Off

**Tested by:** ___________________________

**Date:** ___________________________

**Version:** 1.0

**Overall Status:** ☐ PASS / ☐ FAIL

**Notes:**
```
_________________________________________________
_________________________________________________
_________________________________________________
```

---

## Bug Reporting Template

If you find issues, report using this template:

```
**Bug Title:** [Brief description]

**Page/Module:** [Which page/feature]

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Behavior:**


**Actual Behavior:**


**Screenshots:** [If applicable]

**Environment:**
- OS: [Windows/Mac/Linux]
- Browser: [Chrome/Firefox/etc.]
- Python Version: 
- Streamlit Version: 

**Error Messages:** [Copy any error messages]
```

---

## Automated Testing (Future)

For developers, consider adding:

```python
# tests/test_pk_model.py
import pytest
from utils.pk_model import two_compartment_model

def test_pk_model():
    dose = 100
    kabs = 0.5
    kel = 0.1
    k12 = 0.3
    k21 = 0.2
    t_max = 48
    
    t, C_plasma, C_tissue = two_compartment_model(dose, kabs, kel, k12, k21, t_max)
    
    assert len(t) > 0
    assert len(C_plasma) == len(t)
    assert len(C_tissue) == len(t)
    assert C_plasma[0] == 0  # Initial condition
    assert max(C_plasma) > 0  # Should have peak concentration
```

Run with: `pytest tests/`

---

**Testing Guide Complete**

For questions or issues, contact: info@expertsgroup.me
