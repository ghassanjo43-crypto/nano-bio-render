# 🎯 Nanoparticle Design Scoring System

## Overview

The NanoBio Studio scoring system evaluates nanoparticle design quality using a comprehensive multi-parameter approach based on scientific principles and clinical data from nanomedicine research.

---

## 📊 Main Scoring Function

The **Overall Suitability Score (0-100)** is calculated using a weighted average of six key parameters:

### Scoring Weights

| Parameter | Weight | Importance |
|-----------|--------|------------|
| **Size** | 25% | Most critical - affects biodistribution, clearance, EPR effect |
| **Material-Payload** | 20% | Carrier compatibility with therapeutic cargo |
| **Ligand-Target** | 20% | Targeting effectiveness for specific tissue |
| **Charge** | 15% | Influences stability, cell uptake, toxicity |
| **PDI** | 10% | Particle uniformity and quality |
| **Payload Loading** | 10% | Therapeutic efficiency |

### Formula

```
Overall Score = (Size × 0.25) + (Material-Payload × 0.20) + (Ligand-Target × 0.20) 
              + (Charge × 0.15) + (PDI × 0.10) + (Payload Loading × 0.10)
```

---

## 🔬 Individual Scoring Components

### 1. Size Score (0-100)

**Function:** `score_size(size, target)`

Evaluates if nanoparticle size is appropriate for the target tissue.

#### Target-Specific Optimal Ranges

| Target Tissue | Optimal Size (nm) | Rationale |
|---------------|-------------------|-----------|
| Tumor Tissue | 80-200 | EPR effect window for passive targeting |
| Brain (BBB) | 20-100 | Small particles cross blood-brain barrier |
| Kidney Glomeruli | 5-50 | Size-dependent filtration |
| Liver Hepatocytes | 50-150 | Fenestrated capillaries |
| Lymph Nodes | 10-100 | Lymphatic drainage uptake |
| Lung Endothelium | 50-200 | Pulmonary capillary bed |
| Spleen (RES) | 100-300 | Splenic sinus penetration |
| Cardiovascular | 30-150 | Endothelial targeting |
| Inflamed Tissue | 50-200 | Enhanced permeability |
| Bone Marrow | 50-200 | Bone marrow sinusoids |
| Skin (Dermal) | 50-300 | Dermal penetration |
| Ocular Tissue | 20-100 | Blood-retinal barrier |

#### Scoring Rules

- **Within optimal range:** 80-100 points
  - Closer to range center = higher score
  - Maximum 20-point penalty for deviation from center
  
- **Outside optimal range:** 20-80 points
  - Penalty increases with distance from range
  - Maximum 80-point penalty
  - Minimum score of 20

#### Example
- Size: 120nm for Tumor (optimal 80-200nm)
- Center: 140nm
- Deviation: 20nm from center
- **Score: 90/100** ✅

---

### 2. Charge Score (0-100)

**Function:** `score_charge(charge, target)`

Evaluates surface charge (zeta potential) appropriateness for target tissue.

#### Target-Specific Optimal Ranges

| Target Tissue | Optimal Charge (mV) | Rationale |
|---------------|---------------------|-----------|
| Tumor Tissue | -30 to +10 | Slightly negative to neutral avoids RES |
| Brain (BBB) | -15 to +5 | Near-neutral for BBB crossing |
| Kidney Glomeruli | -40 to -10 | Negative charge for filtration |
| Liver Hepatocytes | -20 to +20 | Broad tolerance |
| Lymph Nodes | -20 to +20 | Flexible for immune targeting |
| Spleen (RES) | -30 to +30 | RES uptake tolerance |
| Others | -20 to +10 | General physiological range |

#### Scoring Rules

- **Within optimal range:** 100 points
- **Outside optimal range:** 30-100 points
  - Normalized penalty based on deviation
  - Maximum 70-point penalty
  - Minimum score of 30

#### Example
- Charge: -10mV for Tumor (optimal -30 to +10)
- Within range ✅
- **Score: 100/100** ✅

---

### 3. PDI Score (0-100)

**Function:** `score_pdi(pdi)`

Evaluates particle size uniformity. Lower PDI indicates better quality and reproducibility.

#### Scoring Table

| PDI Range | Score | Quality Level |
|-----------|-------|---------------|
| ≤ 0.1 | 100 | Excellent - Highly uniform |
| ≤ 0.2 | 90 | Good - Acceptable uniformity |
| ≤ 0.3 | 70 | Fair - Moderate polydispersity |
| ≤ 0.4 | 50 | Poor - High polydispersity |
| > 0.4 | 30 | Very Poor - Unacceptable |

#### Scientific Basis
- PDI < 0.2: Considered monodisperse (ideal for clinical use)
- PDI 0.2-0.3: Acceptable for research
- PDI > 0.3: Quality concerns for reproducibility

---

### 4. Material-Payload Compatibility Score (0-100)

**Function:** `score_material_payload(material, payload)`

Evaluates how well the nanoparticle material suits the therapeutic payload.

#### Top Material-Payload Combinations (Score = 100)

| Material | Best Payloads | Score |
|----------|--------------|-------|
| **LNP** | mRNA, CRISPR-Cas9 | 100/90 |
| **Gold NP** | Imaging agents | 100 |
| **PLGA** | Small molecule drugs | 90 |
| **MSN** | Small molecule drugs | 90 |
| **Exosome** | mRNA, Proteins | 90 |
| **Liposome** | Small molecules, siRNA | 80 |

#### Scoring Scale
- **10/10 (100 pts):** Ideal combination, clinically proven
- **9/10 (90 pts):** Excellent compatibility
- **8/10 (80 pts):** Good compatibility
- **7/10 (70 pts):** Acceptable
- **≤6/10 (≤60 pts):** Suboptimal or poor fit

#### Example
- LNP + mRNA
- Clinical standard (Moderna/Pfizer vaccines)
- **Score: 100/100** ✅

---

### 5. Ligand-Target Compatibility Score (0-100)

**Function:** `score_ligand_target(ligand, target)`

Evaluates surface ligand effectiveness for specific tissue targeting.

#### Top Ligand-Target Combinations (Score = 100)

| Ligand | Best Targets | Mechanism |
|--------|--------------|-----------|
| **Antibody (mAb)** | Tumor, Brain, Lung | Receptor-mediated endocytosis |
| **Transferrin** | Brain (BBB) | Transferrin receptor targeting |
| **RGD Peptide** | Tumor | Integrin αvβ3 binding |
| **PEG** | Kidney, Cardiovascular | Stealth effect, prolonged circulation |
| **Hyaluronic Acid** | Inflamed tissue, Skin | CD44 receptor targeting |
| **Folate** | Tumor | Folate receptor overexpression |

#### Scoring Scale
- **10/10 (100 pts):** Highly specific, clinically validated
- **9/10 (90 pts):** Excellent targeting efficiency
- **8/10 (80 pts):** Good specificity
- **7/10 (70 pts):** Moderate effectiveness
- **≤6/10 (≤60 pts):** Low targeting efficiency

#### Example
- Antibody (mAb) + Tumor
- Receptor-mediated targeting
- **Score: 100/100** ✅

---

### 6. Payload Loading Score (0-100)

**Function:** `score_payload_loading(payload_amount, payload)`

Evaluates if payload loading percentage is optimal for the cargo type.

#### Optimal Loading Ranges

| Payload Type | Optimal Loading (% w/w) | Rationale |
|--------------|------------------------|-----------|
| **mRNA** | 1-5% | Sensitive to degradation |
| **siRNA** | 1-10% | Small molecule, efficient |
| **DNA (plasmid)** | 1-5% | Large molecule |
| **Small molecule drug** | 5-30% | Stable, high capacity |
| **Protein/Peptide** | 5-20% | Moderate stability |
| **Antibody** | 5-15% | Large protein |
| **CRISPR-Cas9 RNP** | 1-5% | Complex, fragile |
| **Imaging agent** | 1-20% | Variable by agent |
| **Combination** | 5-20% | Balanced loading |

#### Scoring Rules
- **Within optimal range:** 100 points
- **Below minimum:** 50-100 points (inefficient)
- **Above maximum:** 50-100 points (stability concerns)

---

## 📈 Score Interpretation

### Overall Score Ratings

| Score Range | Rating | Color | Meaning |
|-------------|--------|-------|---------|
| **85-100** | Excellent | 🟢 Green | Clinically viable design |
| **70-84** | Good | 🔵 Blue | Solid design, minor optimization |
| **55-69** | Fair | 🟡 Yellow | Needs improvement |
| **<55** | Needs Improvement | 🔴 Red | Major revisions required |

---

## 🔬 Scientific Basis

### Key Principles

1. **EPR Effect:** Enhanced Permeability and Retention in tumors (80-200nm window)
2. **Stealth Technology:** PEGylation for immune evasion
3. **Receptor-Mediated Targeting:** Ligand-receptor interactions
4. **Renal Clearance:** Size-dependent kidney filtration (<5nm cleared)
5. **RES Uptake:** Reticuloendothelial system clearance (charge-dependent)
6. **Blood-Brain Barrier:** Size and charge restrictions for BBB crossing

### References

- **Size optimization:** Peer et al. (2007), Maeda effect studies
- **Surface charge:** Alexis et al. (2008), Particle-cell interactions
- **Material selection:** Anselmo & Mitragotri (2019), Clinical nanomedicine
- **Ligand targeting:** Danhier (2016), Active targeting strategies
- **PDI standards:** ISO 22412:2017, Dynamic light scattering

---

## 💡 Recommendations System

The system automatically generates recommendations when scores fall below 70:

- **Size < 70:** Adjust to match target tissue size requirements
- **Charge < 70:** Optimize surface charge for target
- **PDI < 70:** Improve formulation uniformity
- **Material < 70:** Consider alternative nanoparticle platform
- **Ligand < 70:** Explore better targeting ligands
- **Loading < 70:** Adjust payload concentration

---

## 🎓 Example Calculation

### Design Parameters
- **Material:** Lipid Nanoparticle (LNP)
- **Size:** 120nm
- **Charge:** -10mV
- **PDI:** 0.15
- **Ligand:** PEG
- **Payload:** mRNA
- **Loading:** 3%
- **Target:** Tumor Tissue (Solid)

### Individual Scores
1. Size: 90/100 (within 80-200nm, near center)
2. Charge: 100/100 (within -30 to +10mV)
3. PDI: 90/100 (excellent uniformity)
4. Material-Payload: 100/100 (LNP + mRNA = clinical standard)
5. Ligand-Target: 80/100 (PEG + Tumor = good stealth)
6. Loading: 100/100 (3% optimal for mRNA)

### Overall Score Calculation

```
Overall = (90 × 0.25) + (100 × 0.15) + (90 × 0.10) + (100 × 0.20) + (80 × 0.20) + (100 × 0.10)
        = 22.5 + 15 + 9 + 20 + 16 + 10
        = 92.5/100
```

### Result: **92.5/100** - Excellent Design 🟢

---

---

## 📚 Scientific References

The NanoBio Studio scoring system is based on established scientific principles, peer-reviewed research, and clinical data from nanomedicine literature. Below are the primary references supporting each scoring component.

### 🎯 Size Optimization & EPR Effect

1. **Maeda, H., Wu, J., Sawa, T., Matsumura, Y., & Hori, K. (2000)**  
   *"Tumor vascular permeability and the EPR effect in macromolecular therapeutics: a review."*  
   Journal of Controlled Release, 65(1-2), 271-284.  
   DOI: 10.1016/S0168-3659(99)00248-5  
   **Key Finding:** Established the 80-200nm optimal size window for tumor targeting via Enhanced Permeability and Retention (EPR) effect.

2. **Peer, D., Karp, J. M., Hong, S., Farokhzad, O. C., Margalit, R., & Langer, R. (2007)**  
   *"Nanocarriers as an emerging platform for cancer therapy."*  
   Nature Nanotechnology, 2(12), 751-760.  
   DOI: 10.1038/nnano.2007.387  
   **Key Finding:** Comprehensive review of size-dependent biodistribution and targeting efficiency.

3. **Choi, H. S., Liu, W., Misra, P., Tanaka, E., Zimmer, J. P., Ipe, B. I., ... & Frangioni, J. V. (2007)**  
   *"Renal clearance of quantum dots."*  
   Nature Biotechnology, 25(10), 1165-1170.  
   DOI: 10.1038/nbt1340  
   **Key Finding:** Particles <5.5nm undergo rapid renal clearance; optimal size for different organs.

4. **Cabral, H., Matsumoto, Y., Mizuno, K., Chen, Q., Murakami, M., Kimura, M., ... & Kataoka, K. (2011)**  
   *"Accumulation of sub-100 nm polymeric micelles in poorly permeable tumours depends on size."*  
   Nature Nanotechnology, 6(12), 815-823.  
   DOI: 10.1038/nnano.2011.166  
   **Key Finding:** Size-dependent tumor penetration; smaller particles (30-50nm) show better penetration.

5. **Kreuter, J. (2014)**  
   *"Drug delivery to the central nervous system by polymeric nanoparticles: What do we know?"*  
   Advanced Drug Delivery Reviews, 71, 2-14.  
   DOI: 10.1016/j.addr.2013.08.008  
   **Key Finding:** Optimal size for BBB crossing: 20-100nm with appropriate surface modifications.

6. **Saraiva, C., Praça, C., Ferreira, R., Santos, T., Ferreira, L., & Bernardino, L. (2016)**  
   *"Nanoparticle-mediated brain drug delivery: Overcoming blood–brain barrier to treat neurodegenerative diseases."*  
   Journal of Controlled Release, 235, 34-47.  
   DOI: 10.1016/j.jconrel.2016.05.044  
   **Key Finding:** Size and charge requirements for CNS drug delivery.

### ⚡ Surface Charge Effects

7. **Alexis, F., Pridgen, E., Molnar, L. K., & Farokhzad, O. C. (2008)**  
   *"Factors affecting the clearance and biodistribution of polymeric nanoparticles."*  
   Molecular Pharmaceutics, 5(4), 505-515.  
   DOI: 10.1021/mp800051m  
   **Key Finding:** Charge-dependent protein adsorption, RES clearance, and cellular uptake mechanisms.

8. **Fröhlich, E. (2012)**  
   *"The role of surface charge in cellular uptake and cytotoxicity of medical nanoparticles."*  
   International Journal of Nanomedicine, 7, 5577-5591.  
   DOI: 10.2147/IJN.S36111  
   **Key Finding:** Optimal charge ranges for different cell types; cytotoxicity correlations.

9. **Xiao, K., Li, Y., Luo, J., Lee, J. S., Xiao, W., Gonik, A. M., ... & Lam, K. S. (2011)**  
   *"The effect of surface charge on in vivo biodistribution of PEG-oligocholic acid based micellar nanoparticles."*  
   Biomaterials, 32(13), 3435-3446.  
   DOI: 10.1016/j.biomaterials.2011.01.021  
   **Key Finding:** Near-neutral charge (-10 to +10 mV) shows optimal tumor accumulation.

### 📊 Polydispersity Index (PDI) Standards

10. **ISO 22412:2017**  
    *"Particle size analysis - Dynamic light scattering (DLS)"*  
    International Organization for Standardization  
    **Key Standard:** PDI < 0.2 considered monodisperse; PDI > 0.3 indicates high polydispersity.

11. **Danaei, M., Dehghankhold, M., Ataei, S., Hasanzadeh Davarani, F., Javanmard, R., Dokhani, A., ... & Mozafari, M. R. (2018)**  
    *"Impact of particle size and polydispersity index on the clinical applications of lipidic nanocarrier systems."*  
    Pharmaceutics, 10(2), 57.  
    DOI: 10.3390/pharmaceutics10020057  
    **Key Finding:** PDI impact on reproducibility, stability, and clinical translation.

### 🧬 Material-Payload Compatibility

**Lipid Nanoparticles (LNPs) & mRNA**

12. **Pardi, N., Hogan, M. J., Porter, F. W., & Weissman, D. (2018)**  
    *"mRNA vaccines—a new era in vaccinology."*  
    Nature Reviews Drug Discovery, 17(4), 261-279.  
    DOI: 10.1038/nrd.2017.243  
    **Key Finding:** LNPs as optimal carriers for mRNA; clinical validation (Moderna/Pfizer COVID-19 vaccines).

13. **Cullis, P. R., & Hope, M. J. (2017)**  
    *"Lipid nanoparticle systems for enabling gene therapies."*  
    Molecular Therapy, 25(7), 1467-1475.  
    DOI: 10.1016/j.ymthe.2017.03.013  
    **Key Finding:** LNP formulation principles for nucleic acid delivery.

**PLGA & Small Molecules**

14. **Danhier, F., Ansorena, E., Silva, J. M., Coco, R., Le Breton, A., & Préat, V. (2012)**  
    *"PLGA-based nanoparticles: an overview of biomedical applications."*  
    Journal of Controlled Release, 161(2), 505-522.  
    DOI: 10.1016/j.jconrel.2012.01.043  
    **Key Finding:** PLGA optimal for sustained release of small molecule drugs and proteins.

**Gold Nanoparticles & Imaging**

15. **Boisselier, E., & Astruc, D. (2009)**  
    *"Gold nanoparticles in nanomedicine: preparations, imaging, diagnostics, therapies and toxicity."*  
    Chemical Society Reviews, 38(6), 1759-1782.  
    DOI: 10.1039/B806051G  
    **Key Finding:** Gold nanoparticles excel in imaging applications; surface plasmon resonance properties.

**Exosomes & Biologics**

16. **Vader, P., Mol, E. A., Pasterkamp, G., & Schiffelers, R. M. (2016)**  
    *"Extracellular vesicles for drug delivery."*  
    Advanced Drug Delivery Reviews, 106, 148-156.  
    DOI: 10.1016/j.addr.2016.02.006  
    **Key Finding:** Exosomes as natural carriers for proteins, nucleic acids; low immunogenicity.

### 🎯 Ligand-Mediated Targeting

17. **Danhier, F. (2016)**  
    *"To exploit the tumor microenvironment: Since the EPR effect fails in the clinic, what is the future of nanomedicine?"*  
    Journal of Controlled Release, 244, 108-121.  
    DOI: 10.1016/j.jconrel.2016.11.015  
    **Key Finding:** Active targeting improves upon passive EPR; ligand selection strategies.

18. **Johnsen, K. B., Burkhart, A., Thomsen, L. B., Andresen, T. L., & Moos, T. (2019)**  
    *"Targeting the transferrin receptor for brain drug delivery."*  
    Progress in Neurobiology, 181, 101665.  
    DOI: 10.1016/j.pneurobio.2019.101665  
    **Key Finding:** Transferrin-conjugated nanoparticles for effective BBB crossing.

19. **Danhier, F., Le Breton, A., & Préat, V. (2012)**  
    *"RGD-based strategies to target alpha(v) beta(3) integrin in cancer therapy and diagnosis."*  
    Molecular Pharmaceutics, 9(11), 2961-2973.  
    DOI: 10.1021/mp3002733  
    **Key Finding:** RGD peptides bind αvβ3 integrins overexpressed on tumor endothelium.

20. **Prabhakar, U., Maeda, H., Jain, R. K., Sevick-Muraca, E. M., Zamboni, W., Farokhzad, O. C., ... & Blakey, D. C. (2013)**  
    *"Challenges and key considerations of the enhanced permeability and retention effect for nanomedicine drug delivery in oncology."*  
    Cancer Research, 73(8), 2412-2417.  
    DOI: 10.1158/0008-5472.CAN-12-4561  
    **Key Finding:** Antibody-mediated active targeting enhances specificity 5-10 fold.

### 💊 Payload Loading Optimization

21. **Kauffman, K. J., Webber, M. J., & Anderson, D. G. (2016)**  
    *"Materials for non-viral intracellular delivery of messenger RNA therapeutics."*  
    Journal of Controlled Release, 240, 227-234.  
    DOI: 10.1016/j.jconrel.2015.12.032  
    **Key Finding:** Optimal mRNA loading: 1-5% w/w for stability and transfection efficiency.

22. **Sharma, A., Garg, T., Aman, A., Panchal, K., Sharma, R., Kumar, S., & Markandeywar, T. (2016)**  
    *"Nanogel—an advanced drug delivery tool: Current and future."*  
    Artificial Cells, Nanomedicine, and Biotechnology, 44(1), 165-177.  
    DOI: 10.3109/21691401.2014.930745  
    **Key Finding:** Small molecule drugs: 5-30% loading typical; depends on hydrophobicity.

### 🔬 Clinical Translation & Nanomedicine Reviews

23. **Anselmo, A. C., & Mitragotri, S. (2019)**  
    *"Nanoparticles in the clinic: An update."*  
    Bioengineering & Translational Medicine, 4(3), e10143.  
    DOI: 10.1002/btm2.10143  
    **Key Finding:** Analysis of FDA-approved nanomedicines; design principles for clinical success.

24. **Mitchell, M. J., Billingsley, M. M., Haley, R. M., Wechsler, M. E., Peppas, N. A., & Langer, R. (2021)**  
    *"Engineering precision nanoparticles for drug delivery."*  
    Nature Reviews Drug Discovery, 20(2), 101-124.  
    DOI: 10.1038/s41573-020-0090-8  
    **Key Finding:** Modern design principles; optimization strategies from recent clinical data.

25. **Shi, J., Kantoff, P. W., Wooster, R., & Farokhzad, O. C. (2017)**  
    *"Cancer nanomedicine: progress, challenges and opportunities."*  
    Nature Reviews Cancer, 17(1), 20-37.  
    DOI: 10.1038/nrc.2016.108  
    **Key Finding:** Comprehensive analysis of nanomedicine in oncology; clinical success factors.

### 🧪 Safety & Toxicity

26. **Monopoli, M. P., Åberg, C., Salvati, A., & Dawson, K. A. (2012)**  
    *"Biomolecular coronas provide the biological identity of nanosized materials."*  
    Nature Nanotechnology, 7(12), 779-786.  
    DOI: 10.1038/nnano.2012.207  
    **Key Finding:** Protein corona formation affects biocompatibility; size and charge dependencies.

27. **Soenen, S. J., Parak, W. J., Rejman, J., & Manshian, B. (2015)**  
    *"(Intra)cellular stability of inorganic nanoparticles: effects on cytotoxicity, particle functionality, and biomedical applications."*  
    Chemical Reviews, 115(5), 2109-2135.  
    DOI: 10.1021/cr400714j  
    **Key Finding:** Nanomaterial safety profiles; design parameters affecting toxicity.

### 📋 Regulatory & Quality Standards

28. **U.S. FDA (2022)**  
    *"Liposome Drug Products - Chemistry, Manufacturing, and Controls; Human Pharmacokinetics and Bioavailability; and Labeling Documentation"*  
    Guidance for Industry  
    **Key Standard:** FDA quality requirements for nanoparticle-based drug products.

29. **EMA (2013)**  
    *"Reflection paper on surface coatings: general issues for consideration regarding parenteral administration of coated nanomedicine products"*  
    European Medicines Agency  
    **Key Standard:** European regulatory considerations for nanomedicine design.

### 📚 Foundational Nanomedicine Textbooks

30. **Torchilin, V. P. (Ed.). (2014)**  
    *"Handbook of Nanobiomedical Research: Fundamentals, Applications and Recent Developments"*  
    World Scientific Publishing, Volumes 1-4.  
    ISBN: 978-981-4520-64-5

31. **Bawa, R., Audette, G. F., & Rubinstein, I. (Eds.). (2016)**  
    *"Handbook of Clinical Nanomedicine: Nanoparticles, Imaging, Therapy, and Clinical Applications"*  
    Pan Stanford Publishing.  
    ISBN: 978-981-4669-22-1

### 💡 Clinical Validation Examples

**FDA-Approved Nanomedicines Referenced:**

- **Doxil® (1995):** PEGylated liposomal doxorubicin - validates size/PEG principles
- **Abraxane® (2005):** Albumin-bound paclitaxel - validates protein carrier concept
- **Onpattro® (2018):** LNP-siRNA - validates LNP for nucleic acids
- **Comirnaty® (2021):** Pfizer BioNTech COVID-19 vaccine - LNP-mRNA validation
- **Spikevax® (2021):** Moderna COVID-19 vaccine - LNP-mRNA validation

---

## 🔍 How to Cite This System

**Suggested Citation:**

Muammar, G., & Experts Group FZE. (2026). *NanoBio Studio: Evidence-Based Nanoparticle Design Scoring System.* Retrieved from https://www.expertsgroup.me

---

## 📞 Support

For questions about the scoring system or to report issues:

**Experts Group FZE**  
📧 info@expertsgroup.me  
🌐 www.expertsgroup.me

© 2026 Experts Group FZE | IP Rights: Ghassan Muammar
