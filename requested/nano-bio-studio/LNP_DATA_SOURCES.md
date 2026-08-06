# 🧬 LNP Dataset Sources & Integration Guide

## Quick Start: Where to Get LNP Data

### 1. **Pre-Built Comprehensive Dataset** ✅
You can use the `generate_lnp_dataset.py` script included in your project to create a dataset with **500+ realistic LNP samples**:

```bash
python generate_lnp_dataset.py
```

This generates `comprehensive_lnp_dataset.csv` with:
- 500 synthetic samples based on published literature
- 2 real formulations: Pfizer & Moderna COVID-19 LNP data
- 21 parameters per sample
- Known targets: Liver, Immune, Tumor, Neurons, Lung, Spleen

---

## 2. **Public Data Sources (Free)**

### A. Literature-Based Data
- **PubMed/PubChem**: Search "lipid nanoparticle" + "characterization"
- **COVID-19 Vaccine Data**:
  - Pfizer BioNTech LNP specs (published in Nature Biotech)
  - Moderna LNP platform data (public filings)
- **Zenodo.org**: Search for "LNP dataset" or "nanoparticle"
- **GitHub**: Search for "lnp-data" or "nanoparticle-database"

### B. Vendor Data (Often Free)
- **Evonik**: Neutral lipids & ionizable lipids spec sheets
- **Croda**: Lipid formulation guides
- **Merck KGaA**: NanoBio guidelines

### C. Open Research Databases
- **DrugBank.ca**: Search approved LNP therapeutics
- **ChemSpider**: Lipid component data
- **PDB (Protein Data Bank)**: Nanoparticle structures

---

## 3. **Commercial / Premium Sources**

| Source | Cost | Data Type | Quality |
|--------|------|-----------|---------|
| SciFinder | $$$ | Literature + proprietary | High |
| Reaxys | $$$ | Comprehensive chemical data | High |
| Clarivate (Web of Science) | $$ | Citation + experimental | High |
| Market Research Reports | $$ | Industry data | Medium |
| Company DataSheets | Free | Limited specs | Medium |

---

## 4. **How to Format Your Data for Training**

Your ML Training tab expects CSV with these key columns:

```
Batch_ID,Material,Size_nm,PDI,Charge_mV,Encapsulation_%,Stability_%,
Toxicity_%,Hydrodynamic_Size_nm,Surface_Area_nm2,Pore_Size_nm,
Degradation_Time_days,Target_Cells,Ligand,Receptor,Delivery_Efficiency_%,
Particle_Concentration_per_mL,Preparation_Method,pH,Osmolality_mOsm,
Sterility_Pass,Endotoxin_EU_mL
```

### Example Formats:
```csv
LNP-001,Lipid NP (LNP),95.0,0.15,-10.5,95.0,90.0,22.0,107.0,28274.0,2.5,30.0,Immune Cells,PEG,TLR,74.1,1.25e+14,Microfluidic,7.2,290.0,Yes,0.005
```

---

## 5. **Using Your ML Training Tab to Process Data**

### Step 1: Upload Dataset
1. Go to **12 🤖 ML Training** tab
2. Click **"Build Dataset"**
3. Upload your CSV file
4. System will validate and split: 80% train, 20% validation

### Step 2: Train Models
1. Select task type: `predict_particle_size`, `predict_toxicity`, etc.
2. Choose model types: Linear Regression, Random Forest, Gradient Boosting, SVM
3. Click **Train Models**
4. View metrics: R², RMSE, MAE

### Step 3: Save & Export
1. Models auto-save to `models_store/`
2. View trained models in **14 💾 Model Management**
3. Download predictions as CSV

---

## 6. **Quick Integration Steps**

### Option A: Use Generated Dataset (Recommended for Testing)
```bash
# 1. Generate synthetic dataset
python generate_lnp_dataset.py

# 2. Open app and go to ML Training tab
# 3. Upload comprehensive_lnp_dataset.csv

# 4. Train models (500 samples = good baseline)
```

### Option B: Use Real Data
```bash
# 1. Prepare your CSV following the format above
# 2. Ensure all columns are present
# 3. Upload via ML Training interface
# 4. System handles validation + splitting
```

---

## 7. **Recommended Data Collection Strategy**

### For Best Results:
1. **Minimum 100 samples** for initial training
2. **Mix materials**: Lipid NP, PLGA, Liposomes, DNA Origami
3. **Diverse targets**: Liver, Tumor, Immune cells
4. **Include extremes**: Both good and poor formulations (for contrast)
5. **Real experimental data** when possible (beats synthetic)

### Scaling Up:
- 100-500 samples: Good baseline model
- 500-2000 samples: Production-ready model
- 2000+ samples: Excellent model with strong generalization

---

## 8. **Example: Creating Your Own Dataset**

### From Literature Search:
1. Extract data from published papers (Table 1, Supplementary Data)
2. Parse: Size, charge, encapsulation, stability, target
3. Standardize units (all nm for size, all % for encapsulation)
4. Add metadata: Material, ligand, target
5. Save as CSV

### From Experimental Work:
1. Run LNP characterization (DLS, zeta, HPLC)
2. Record parameters for each batch
3. Add performance metrics (transfection, toxicity)
4. Build historical dataset
5. Upload to training system

---

## 9. **Files Included in Your Project**

| File | Purpose | Action |
|------|---------|--------|
| `generate_lnp_dataset.py` | Creates 500+ sample dataset | `python generate_lnp_dataset.py` |
| `sample_lnp_dataset.csv` | Small test dataset (15 samples) | Upload to test training |
| `pages/12_ML_Training.py` | Dataset building interface | Already active |
| `pages/13_ML_Ranking.py` | Compare trained models | View scores |
| `pages/14_Model_Management.py` | Manage saved models | Load/export |

---

## 10. **Next Steps**

### Immediate (Today):
```bash
# Generate test dataset
python generate_lnp_dataset.py

# Upload to ML Training and train models
```

### Short Term (This Week):
- Collect real LNP data from literature or experiments
- Prepare in CSV format
- Train with real data for better accuracy

### Long Term (Ongoing):
- Build internal LNP database
- Continuously improve with new experimental results
- Export trained models for production use

---

## 📞 Support Resources

**Need help finding data?**
- PubMed: pubmed.ncbi.nlm.nih.gov
- Google Scholar: scholar.google.com
- ResearchGate: researchgate.net (ask researchers directly)
- Zenodo: zenodo.org (open science data)

**Need help formatting?**
- Use the `generate_lnp_dataset.py` as a template
- Check existing CSV files in your project
- ML Training tab validates on upload
