# Scoring Canonicalization

**Created:** 2026-07-30 (Phase 2, Step 1)
**Status:** PROPOSAL FOR REVIEW — no replacement Overall Score has been implemented.
**Required by:** DECISION 2 and DECISION 8.

> **Nothing in this document has been implemented as a production score.**
> Section 8 proposes a formula. It must be reviewed and separately authorised
> before any code is written. Sections 1–6 describe what exists today, verified by
> execution against the golden-vector baseline.

**Scientific positioning (applies to every score in this document).** All values
are computational research-planning results. None is experimentally validated,
clinically validated, a regulatory approval prediction, a diagnosis, a treatment
recommendation, or a substitute for wet-lab testing.

---

## 1. Inventory of every scoring system

Seven distinct scoring surfaces exist. Only two are canonical.

| # | System | Location | Status |
|---|---|---|---|
| 1 | **Principal Design Score** (`compute_impact`) | `core/scoring.py:8` | **ACTIVE — CANONICAL** (DECISION 3A) |
| 2 | Composite convenience score | `core/scoring.py::overall_score_from_impact` | ACTIVE, secondary |
| 3 | `DesignScorer` (6-weight) | `utils/design_scorer.py:8` | **LEGACY / SECONDARY** (DECISION 3C) |
| 4 | Assessment weights | `config/scoring_config.py` + 6 `engine/` modules | **ACTIVE — CANONICAL** for assessment (DECISION 3B) |
| 5 | Disease-fit score | `engine/disease_fit.py` | ACTIVE but **UNCALIBRATED verdict** (DECISION 6) |
| 6 | Confidence / evidence | `engine/confidence_engine.py`, `config/scoring_config.py` | ACTIVE (restored in Step 1) |
| 7 | Headline 92 / 89 / 82 | `pages/2_Run_Simulation.py:314-338` | **HARD-CODED DEFECT** (DECISION 2) |
| — | ML predictor outputs | `components/ml_predictor.py` | **DEFECTIVE** — heuristic, no model loads (DEFECT-D5) |
| — | AI Co-Designer scores | `pages/7_AI_Co_Designer.py` | **QUARANTINED** in Step 1 (DECISION 7) |

---

## 2. Exact formulas, inputs, weights, ranges, thresholds

### 2.1 System 1 — Principal Design Score (CANONICAL)

`core/scoring.py::compute_impact(design: dict, weights: dict | None) -> dict`

**Outputs:** `{"Delivery": 0–100, "Toxicity": 0–10, "Cost": 0–100}`

**Delivery** = weighted sum of 12 sub-scores, weights re-normalised to sum 1.0
(`core/scoring.py:167-170`, so doubling every weight changes nothing):

| Component | Weight | Rule |
|---|---:|---|
| size | 0.18 | 100 in 80–120 nm; below: `size/80*100`; above: `100-(size-120)/2`, floored at 0 |
| encapsulation | 0.18 | direct percentage |
| charge | 0.14 | 100 when \|ζ\| ≤ 10 mV; else `100-(\|ζ\|-10)*3`, floored at 0 |
| pdi | 0.10 | `100 - PDI*200`, floored at 0 |
| targeting | 0.08 | ligand present: `0.6*ligand_density_score + 0.4*binding_score`; absent: **60** |
| hydro | 0.06 | 100 when hydrodynamic/core ratio in 1.0–1.3; else `100-\|ratio-1.15\|*50` |
| hydrophobicity | 0.05 | 100 for LogP 0.5–2.5; else `100-\|LogP-1.5\|*20` |
| crystallinity | 0.05 | 100 for 70–90 %; else `100-\|x-80\|*2` |
| coating | 0.05 | `min(100, 50 + bonus)`; PEG +30, HA +20, chitosan +15, albumin +10 |
| stability | 0.04 | value passed through |
| release | 0.04 | value passed through |
| surface_area | 0.04 | 100 for 200–400 nm²; else `100-\|A-300\|/3` |

**Toxicity (0–10)**, clamped at 10:
`min(10, |charge|/10 + max(0,|size-100|)/50) + PDI*2 + max(0,(degradation-30)/30) + surface_toxicity + targeting_toxicity`
where `surface_toxicity` adds for LogP > 3.0 and crystallinity < 40, minus coating
protection (PEG −2, HA −1.5, albumin −1, floored at 0).

**Cost (0–100)**, clamped at 100:
`min(100, (100-encap)*0.8 + size/4) + surface_area/20 + (0.2-min(PDI,0.2))*100 + max(0,(degradation-60)/10) + ligand_cost + coating_cost + functional_cost + thickness_cost`
Ligand cost map: GalNAc 20, Folate 15, Transferrin 30, RGD 25, Anti-HER2 40, **default 20**.

**Input contract (corrected in Step 1, DEFECT-D9):**
* Required — `Size`, `Charge`, `Encapsulation`. Missing → `KeyError`. Never defaulted.
* Optional — absent key ≡ present-but-`None`; both fall back to the documented default.
* Verified: 21 optional keys × 3 functions = 63 consistency checks.

### 2.2 System 2 — composite convenience score

`overall_score_from_impact(impact)` = `clip(Delivery*0.6 + (10-Toxicity)*3 + (100-Cost)*0.1, 0, 100)`

Component weights sum to 0.6 + 30 + 10 on **different scales**, so the term
magnitudes are not comparable — see open question Q3.

### 2.3 System 3 — `DesignScorer` (LEGACY / SECONDARY)

Weights: size 0.25, material 0.20, ligand 0.20, charge 0.15, pdi 0.10, loading 0.10.
Inputs use **lowercase** keys (`size`, `charge`, `pdi`, `material`, `ligand`,
`payload`, `payload_amount`, `target`) — incompatible with System 1's CapitalCase.
Only `modules/design.py` calls it. **This is the system `docs/scoring_system.md`
documents**, which is why that document does not describe the running application.

### 2.4 System 4 — assessment weights (CANONICAL for assessment)

`config/scoring_config.py`: delivery 0.35, safety 0.25, manufacturability 0.20,
disease-fit 0.15, stability 0.05.
Confidence thresholds: high ≥ 0.75, medium ≥ 0.50.
Performance bands: Excellent ≥ 85, Good ≥ 75, Acceptable ≥ 65, else Requires Revision.

> **These weights are declared but not applied as a single composite anywhere.**
> The six engines consume the thresholds and labels; nothing multiplies the five
> weights into one number. See open question Q1.

### 2.5 System 5 — disease-fit

`_calculate_overall_fit()` = **unweighted mean** of barrier-mitigation scores
("All barriers equally important; average them"), 50.0 when no barriers.
Favourable threshold 70.0 — **uncalibrated and unreachable**: observed ceiling
**68.33** over a 1,792-combination sweep. Verdict withheld (DECISION 6).

### 2.6 System 7 — the hard-coded headline (DEFECT)

```
uptake > 85 → 92 "Excellent"   |   uptake > 75 → 89 "Good"   |   else → 82 "Satisfactory"
except:      → 89 "Good"
```
Three reachable values regardless of design; failure yields a favourable score.

---

## 3. Call sites and interface locations

| System | Call sites | Where the user sees it |
|---|---|---|
| 1 `compute_impact` | `pages/1_Design_Parameters.py`, `pages/2_Run_Simulation.py`, (dead `tabs/*`) | Delivery / Toxicity / Cost metrics |
| 2 `overall_score_from_impact` | same modules | composite figure |
| 3 `DesignScorer` | `modules/design.py` only | legacy module UI |
| 4 assessment weights | all six `engine/` modules | assessment sections, PDF report |
| 5 disease-fit | `engine/disease_fit.py` → regulatory + report | fit score, barrier table |
| 6 confidence | `engine/confidence_engine.py` → report | confidence narrative |
| 7 headline 92/89/82 | `pages/2_Run_Simulation.py` | **the most prominent number in the app** |
| ML predictor | `pages/2_Run_Simulation.py:33` | "ML PREDICTIONS" panel |

---

## 4. Status of each system

| System | Active | Legacy | Unused | Hard-coded | Defective | Uncalibrated |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| 1 `compute_impact` | ✔ | | | | | |
| 2 `overall_score_from_impact` | ✔ | | | | | see Q3 |
| 3 `DesignScorer` | | ✔ | | | | |
| 4 assessment weights | ✔ | | partly (see Q1) | | | |
| 5 disease-fit | ✔ | | | | | ✔ |
| 6 confidence | ✔ | | | | | see Q4 |
| 7 headline 92/89/82 | | | | ✔ | ✔ | |
| ML predictor | | | | | ✔ (D5) | |
| AI Co-Designer | | | | ✔ | ✔ (D6/D7) | |

---

## 5. Mapping between the systems

```
                    ┌──────────────── DESIGN INPUTS (23 fields) ────────────────┐
                    │                                                            │
        ┌───────────▼───────────┐                        ┌───────────────────────▼─────────┐
        │ PRINCIPAL DESIGN      │                        │ SCIENTIFIC ASSESSMENT           │
        │ core/scoring.py       │                        │ 6 engine/ modules               │
        │ compute_impact()      │                        │ config/scoring_config.py        │
        │ 12 weights            │                        │ 5 weights (declared)            │
        │ → Delivery/Tox/Cost   │                        │ → mechanistic, safety,          │
        └───────────┬───────────┘                        │   disease-fit, manufacturing,   │
                    │                                    │   regulatory, confidence        │
                    │ overall_score_from_impact()        └───────────┬─────────────────────┘
                    ▼                                                │
            composite figure                                         ▼
                    │                                    ScientificReport (PDF)
                    │                                                │
                    │        ┌───────────────────────────────────────┘
                    ▼        ▼
        ┌────────────────────────────┐        LEGACY / QUARANTINED (not canonical)
        │ pages/2_Run_Simulation.py  │        ├─ utils/design_scorer.py  (6 weights, lowercase keys)
        │ headline 92/89/82  ✗ DEFECT│        ├─ ML predictor            (heuristic; no model loads)
        └────────────────────────────┘        └─ AI Co-Designer          (quarantined Step 1)
```

**The two canonical systems are deliberately NOT combined.** Per DECISION 3B they
must not be averaged or merged without a reviewed formula that explicitly defines
the combination. No such formula exists today.

---

## 6. Distinguishing the concepts

These are routinely conflated in the legacy UI. The new API must keep them separate.

| Concept | Question it answers | Source | Range |
|---|---|---|---|
| **Design score** | How good is this formulation on intrinsic physicochemical criteria? | `compute_impact` | Delivery 0–100, Tox 0–10, Cost 0–100 |
| **Scientific assessment score** | What do the mechanistic engines predict? | 6 engines | per-module 0–100 |
| **Disease-fit score** | How well does it address *this disease's* barriers? | `disease_fit` | 0–100 (ceiling 68.33) |
| **Confidence** | How much do we trust this prediction? | `confidence_engine` | 0–1 |
| **Evidence level** | What kind of support exists? | `EvidenceLevel` enum | categorical |
| **Uncertainty** | What is the spread? | **NOT IMPLEMENTED** — see Q5 | — |
| **Prediction basis** | How was it derived (mechanistic / empirical / heuristic)? | `PredictionBasis.basis`; only 1 of 6 modules declares one | categorical |
| **Regulatory assessment** | What development stage and pathway? | `regulatory_engine` | categorical + verdict status |
| **Experimental validation status** | Has any of this been tested in a lab? | **NO** — universally absent | — |

**The last row is the most important.** No output in this platform has
experimental validation. Nothing should imply otherwise.

---

## 7. Proposed canonical API field names

```jsonc
{
  "design_impact_score": {                 // DECISION 3A
    "delivery": 87.52, "toxicity": 0.8, "cost": 80.75,
    "components": { "size": 100.0, "charge": 100.0, /* all 12 */ },
    "weights_used": { /* 12, post-normalisation */ },
    "weights_were_renormalised": false,
    "formula_version": "design-impact-1.0.0"
  },
  "scientific_assessment": {               // DECISION 3B — kept separate
    "mechanistic": {...}, "safety": {...}, "manufacturability": {...},
    "regulatory": { "calculation_version": "2.0.0",
                    "manufacturing_complexity": 2,
                    "manufacturing_complexity_basis": "Rule-based manufacturing complexity indicator",
                    "verdict_available": false,
                    "verdict_status": "calibration_required" }
  },
  "disease_fit": {
    "overall_fit_score": 68.33,            // valid, always returned
    "barrier_mitigation_scores": {...},
    "verdict_available": false,            // DECISION 6
    "verdict_status": "calibration_required",
    "favourable_verdict_threshold": 70.0,
    "observed_model_ceiling": 68.33
  },
  "confidence": { "overall": 0.65, "by_module": {...} },
  "evidence_level": "literature_derived",
  "prediction_basis": "mechanistic_physics_principles",
  "uncertainty": null,                     // not implemented — see Q5
  "experimental_validation_status": "none",
  "disease_profile_matched": true,         // DECISION 1
  "profile_used": "HCC-S",
  "legacy_overall_score": {                // DECISION 2 — audit only
    "value": 92, "status": "Excellent",
    "classification": "legacy_presentation_defect",
    "do_not_use_for": ["display", "ranking", "reporting", "comparison"]
  }
}
```

Naming rules: `*_score` = 0–100 computed; `*_status` = structured enum;
`*_available` = boolean gate; `*_version` on every calculated block;
`legacy_*` = audit-only, never displayed as a result.

---

## 8. Proposed Overall Score — FOR REVIEW, NOT IMPLEMENTED

### 8.1 What can be derived without inventing science

`overall_score_from_impact()` **already exists** in the canonical module and is
already used. It can be adopted as the replacement without inventing anything:

```
design_impact_overall = clip( Delivery*0.6 + (10 - Toxicity)*3 + (100 - Cost)*0.1 , 0, 100 )
```

Every input is a canonical System-1 output; every coefficient is pre-existing. It
is fully traceable, reproducible from stored inputs, and versionable.

**Proposal:** adopt this as `design_impact_overall`, version
`design-impact-overall-1.0.0`, with these binding conditions:

1. Available **only** when all three components computed successfully.
2. On any failure → `null` plus `status: "unavailable"` and a reason. **Never** a
   number, and never a favourable one (DECISION 2).
3. Always accompanied by component values, weights, formula version, confidence,
   evidence level and prediction basis.
4. Named `design_impact_overall`, **not** "Overall Score" — it scores the design,
   not the therapy's prospects.
5. It does **not** incorporate disease-fit, safety-engine or regulatory output.
   Combining those requires a separately reviewed formula (Q1).

### 8.2 Known weakness of the proposed formula (must be reviewed)

The three terms are **not on comparable scales**. Maximum contributions are
Delivery 60, Toxicity 30, Cost 10 — so the weighting is implicitly 60/30/10, but
that is an artefact of the multipliers rather than a stated intent. A design with
zero toxicity and maximum cost still scores 30 from the toxicity term alone.

**I am not proposing to change this.** Recording it as the primary review question
for the scientific team (Q3) — altering it would be inventing scientific meaning.

### 8.3 What must NOT happen

* No new coefficients invented.
* The legacy 92/89/82 must not be carried forward as production scoring.
* Failure must never produce a favourable number.
* Design score and assessment scores must not be averaged into one figure.

---

## 9. Unresolved scientific judgments

| # | Question | Blocking |
|---|---|---|
| **Q1** | `config/scoring_config.py` declares 5 assessment weights (0.35/0.25/0.20/0.15/0.05) that **nothing applies**. Were they intended as a composite assessment score? If so, over which normalised inputs? | Composite assessment score |
| **Q2** | Disease-fit uses an **unweighted mean** of barriers ("All barriers equally important"), yet `DiseaseFilModel` declares size 0.30 / charge 0.20 / targeting 0.25 / formulation 0.25 — also unused. Which is intended? | DECISION 6 calibration |
| **Q3** | Is the 60/30/10 implicit weighting in `overall_score_from_impact` intentional? | §8 adoption |
| **Q4** | Confidence values are **hard-coded per engine** (`_calculate_safety_confidence()` etc. return constants). Are these intended priors, or placeholders? | Confidence meaning |
| **Q5** | **No uncertainty quantification exists anywhere.** DECISION 2 requires the Overall Score be accompanied by uncertainty. What form should it take? | §8 requirement 3 |
| **Q6** | `compute_impact` defaults a missing `SurfaceCoating` to `["PEG (Stealth)"]` while `get_recommendations` defaults to `[]` — so a design with no coating is *scored* as PEGylated but *advised* to add PEG. Which default is scientifically correct? **Not silently unified** in Step 1. | Input contract |
| **Q7** | Absent ligand scores a fixed **60/100** "passive targeting baseline". Derivation unknown. | Targeting sub-score |
| **Q8** | Four of six engines declare **no prediction basis**. What basis should each declare? | Transparency section |
| **Q9** | `DesignScorer` (System 3) — retain, deprecate, or fold in? It is what the published `docs/scoring_system.md` documents. | DECISION 3C |
| **Q10** | The ligand cost map defaults unknown ligands to **20**, the same as GalNAc. Intended? | Cost sub-score |

---

## 10. Migration and versioning approach

Every calculated block carries a semantic version, incremented only on deliberate
scientific change:

| Block | Field | Current |
|---|---|---|
| Principal design score | `design_impact_score.formula_version` | `design-impact-1.0.0` (proposed) |
| Regulatory | `regulatory.calculation_version` | **`2.0.0`** (implemented in Step 1) |
| Disease-fit | `disease_fit.calculation_version` | to be assigned |
| Overall score | `design_impact_overall.formula_version` | not implemented |

Rules: PATCH = no numerical change; MINOR = additive fields; **MAJOR = any change
to a computed value**. A MAJOR bump requires golden-vector regeneration, a §6
retirement-log entry in `GOLDEN_VECTOR_BASELINE.md`, and scientific review.
Persist the version with every stored result so historical records remain
interpretable.

---

## 11. Keeping legacy scores auditable without presenting them as valid

Legacy values are retained for audit and never rendered as results:

1. **Immutable archive.** `tests/golden_vectors/baseline_step0_2026-07-30_legacy.json`
   preserves pre-correction behaviour verbatim; the harness never overwrites it.
2. **`legacy_` prefix.** `legacy_overall_score` carries
   `classification: "legacy_presentation_defect"` and an explicit
   `do_not_use_for` list.
3. **Excluded from the contract suite.** Legacy vectors are marked
   `known_defect` and deselected by `-m "not known_defect"`.
4. **Quarantined UI.** The AI Co-Designer's fabricated output is preserved outside
   `pages/`, banner-labelled synthetic demonstration data, unroutable by Streamlit
   (DECISION 7.6).
5. **Never mixed with real records.** Legacy and synthetic values must never be
   persisted in, compared against, or aggregated with real saved simulations.

---

## 12. Review questions for the molecular biology / scientific team

**Priority 1 — blocking the Overall Score**

1. Is the implicit 60/30/10 weighting of delivery / toxicity / cost defensible
   (Q3), or should the composite be re-derived on comparable scales?
2. What uncertainty measure should accompany the score (Q5)? Parameter
   sensitivity, confidence interval, or a qualitative band?
3. Should a design with **no coating** be scored as PEGylated (Q6)?

**Priority 2 — blocking disease-fit calibration (DECISION 6)**

4. Is the 68.33 ceiling appropriate conservatism, or is the barrier scoring
   under-calibrated? What evidence would settle it?
5. Should the favourable threshold remain 70, or is a different cut-off supported?
6. Should barriers be equally weighted, or use the declared 0.30/0.20/0.25/0.25 (Q2)?

**Priority 3 — assessment layer**

7. Were the five assessment weights meant to form a composite (Q1)?
8. Are the hard-coded per-engine confidence values priors or placeholders (Q4)?
9. What prediction basis should the four silent engines declare (Q8)?

**Priority 4 — sub-score derivations**

10. Where does the 60/100 passive-targeting baseline come from (Q7)?
11. Is 20 the right default cost for an unknown ligand (Q10)?
12. Should `DesignScorer` be retained, deprecated, or merged (Q9)?

**Priority 5 — corroboration of existing constants**

13. Optimal size is **80–120 nm** in `compute_impact` but **80–150 nm** in
    `mechanistic_engine`. Which is correct for which purpose?
14. Are the coating bonuses (PEG 30 / HA 20 / chitosan 15 / albumin 10) and ligand
    costs literature-derived or illustrative? `docs/scientific_references.md`
    cites ~18 DOIs but does not map them to these coefficients.

---

## Appendix — related documents

| Document | Purpose |
|---|---|
| `docs/CURRENT_APPLICATION_AUDIT.md` | Phase 1 baseline audit |
| `docs/GOLDEN_VECTOR_BASELINE.md` | Regression methodology, defect register, retirement log |
| `docs/SECURITY_CONTAINMENT_2026-07-30.md` | Security containment record |
| `docs/scoring_system.md` | **Describes System 3, not the running app.** Must be corrected once DECISION 3C resolves Q9. |
| `docs/scientific_references.md` | ~18 DOIs, not yet mapped to coefficients |
