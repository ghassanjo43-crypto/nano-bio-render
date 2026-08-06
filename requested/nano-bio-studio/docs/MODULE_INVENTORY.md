# NanoBio Studio — Module Inventory

**Audit date:** 2026-07-31
**Method:** Repository inspection plus execution of the golden-vector suite. Findings
marked **[VERIFIED]** were confirmed by running code; **[STATIC]** are from reading only.
**Predecessor:** `docs/CURRENT_APPLICATION_AUDIT.md` (2026-07-30). This document
supersedes its module-status table and adds per-module migration accounting.

> **Rule applied throughout.** A page existing in the interface is *not* evidence that a
> module is operational. Status below reflects whether a **genuine legacy implementation is
> connected and tested**, nothing else.

---

## 0. Status vocabulary

| Status | Meaning | May display calculated output? |
|---|---|---|
| **Operational** | Connected to its genuine implementation and tested | Yes |
| **Limited prototype** | Genuine but limited calculation | Yes |
| **Calibration required** | Implemented but not scientifically calibrated | **No** |
| **Migration in progress** | Genuine legacy implementation exists, not connected | **No** |
| **Not yet operational** | No usable genuine implementation exists | **No** |

---

## 1. Headline finding — the disease-coverage ceiling

**`config/disease_profiles.py` defines exactly two disease profiles: `HCC-S` and `PDAC-I`.**
`get_disease_profile()` returns `DISEASE_PROFILES.get(code, DISEASE_PROFILES["HCC-S"])` —
i.e. **any unrecognised disease silently receives hepatocellular-carcinoma biology**. This is
recorded in the golden-vector baseline as **DEFECT-D1**. **[VERIFIED]**

The React workflow offers **5 indications and 19 subtypes** from `diseaseData.ts`.

| Indication (React) | Genuine engine profile? |
|---|---|
| Liver Cancer (HCC) | **Yes** — `HCC-S` |
| Pancreatic Cancer | **Yes** — `PDAC-I` |
| Breast Cancer | **No** |
| Lung Cancer | **No** |
| Colorectal Cancer | **No** |

**Consequence for this work.** The six `engine/` assessment modules can only be run honestly
for HCC and pancreatic designs. For the other three indications the correct behaviour is an
explicit *unsupported disease model* response — **not** a silently-substituted HCC assessment.
Any implementation that returns numbers for a lung-cancer design is fabricating them.

This ceiling is the single largest limiter on how much of the application can become
operational, and it is a **scientific** blocker (new disease profiles must be authored and
reviewed), not an engineering one.

---

## 2. Module inventory

### 2.1 Disease & Therapeutic Selection

| Field | Value |
|---|---|
| **Legacy source** | `pages/0_Disease_Selection.py`, `data/disease_drug_mapping.py` |
| **Purpose** | Record indication → subtype → therapeutic agent for the session |
| **Inputs** | User selection from a fixed mapping |
| **Outputs** | `{disease, subtype, drug}` |
| **Dependencies** | None |
| **Validation level** | Curated mapping; no scientific calculation to validate |
| **Real calculation?** | N/A — data selection only |
| **Migration status** | **Operational** |
| **Connected to** | `frontend/src/workflow/diseaseData.ts` (generated from the legacy mapping: 5 indications, 19 subtypes, verbatim) |
| **Work required** | None. Note that the selection feeds **no** currently-connected engine (§1) |

### 2.2 Nanoparticle Design Parameters

| Field | Value |
|---|---|
| **Legacy source** | `pages/1_Design_Parameters.py` (23 fields, 78 widgets) |
| **Purpose** | Primary formulation input surface |
| **Inputs** | 23 legacy fields; the migrated API accepts 17 |
| **Outputs** | Design dict consumed by the scorer |
| **Dependencies** | `core/scoring.py` |
| **Validation level** | Bounds mirror the legacy widgets exactly |
| **Real calculation?** | N/A — input collection |
| **Migration status** | **Operational** |
| **Connected to** | `POST /api/v1/design/score` request schema |
| **Work required** | 6 legacy fields (`Material`, `Target`, `EncapsulationMethod`, `PorosityLevel`, `PoreSize`, `Receptor`, `ReleaseProfile`) are **not collected**, because they feed only unmigrated engines. Collecting-and-discarding was rejected as dishonest |

### 2.3 Design Impact Score

| Field | Value |
|---|---|
| **Legacy source** | `core/scoring.py::compute_impact()` — System 1, the production scorer |
| **Purpose** | Delivery / Toxicity / Cost from 12 weighted physicochemical sub-scores |
| **Inputs** | `Size`, `Charge`, `Encapsulation` (required) + 14 optional, documented defaults |
| **Outputs** | `{Delivery 0–100, Toxicity 0–10, Cost 0–100}` |
| **Dependencies** | None |
| **Validation level** | `literature_informed_unvalidated`; rule-based heuristic, no calibration data |
| **Real calculation?** | **Yes** |
| **Migration status** | **Operational** |
| **Connected to** | `POST /api/v1/design/score` → `services/design_scoring.py` (canonical function called verbatim, bit-exact equivalence tested over 20 golden vectors) |
| **Work required** | None for this slice. Open: no composite "Overall Score" is produced (DECISION 2); 12 internal sub-scores are not exposed (Q-VS2) |

> **Superseded defect.** `pages/2_Run_Simulation.py:314-323` set the *displayed* headline score
> to one of three constants (92/89/82) by bucketing uptake, and returned a favourable **89
> "Good"** on any exception. This is **DEFECT-D5/D7** and is deliberately **not** migrated. **[VERIFIED]**

### 2.4 PK Simulation

| Field | Value |
|---|---|
| **Legacy source** | `utils/pk_model.py` — `two_compartment_model()`, `calculate_pk_parameters()` |
| **Purpose** | Depot → central → peripheral two-compartment PK, explicit forward Euler |
| **Inputs** | `dose`, `kabs`, `kel`, `k12`, `k21` (required); `duration`, `dt` (legacy defaults 48 h / 0.1 h) |
| **Outputs** | Concentration–time arrays; C_max, T_max, AUC, terminal t½ (nullable), tissue accumulation ratio, peak ratio |
| **Dependencies** | NumPy only (matplotlib decoupled 2026-07-31) |
| **Validation level** | `not_experimentally_validated`; structural model, user-supplied rate constants |
| **Real calculation?** | **Yes** |
| **Migration status** | **Operational** |
| **Connected to** | `POST /api/v1/pk/simulate` → `services/pk_simulation.py` (bit-exact over all 7 golden vectors including every curve point) |
| **Work required** | None for this slice. **Produces no clearance** (no volume term) — declared explicitly, never derived |

### 2.5 Results

| Field | Value |
|---|---|
| **Legacy source** | `pages/2_Run_Simulation.py` display sections, `modules/simulation.py` |
| **Purpose** | Present calculated outputs with provenance |
| **Migration status** | **Operational** |
| **Connected to** | Renders only values returned by the two endpoints above |
| **Work required** | None. Legacy clinical-interpretation prose deliberately not reproduced |

### 2.6 Compare Designs

| Field | Value |
|---|---|
| **Legacy source** | **None.** No legacy comparison implementation exists |
| **Purpose** | Side-by-side comparison of completed runs |
| **Inputs** | Two or more stored runs |
| **Outputs** | Aligned inputs and genuinely calculated outputs |
| **Dependencies** | Run persistence (§3) |
| **Real calculation?** | Comparison is presentation of already-calculated values; no new science |
| **Migration status before this work** | **Not yet operational** (placeholder page) |
| **Work required** | Run persistence, then aligned presentation. **Must not** produce a combined ranking — no approved formula exists |

### 2.7 Scientific Assessments

| Field | Value |
|---|---|
| **Legacy source** | `engine/{mechanistic,safety,disease_fit,manufacturing,regulatory,confidence}_engine.py` (6 modules, 121 KB) + `models/scientific_assessment.py` + `config/{scoring_config,disease_profiles}.py` |
| **Purpose** | Mechanistic prediction, safety risk profile, disease fit, manufacturability, regulatory position, confidence |
| **Inputs** | `TrialDesignInputs` dataclass + `DiseaseProfile` |
| **Outputs** | Structured dataclasses with evidence level, prediction basis, limitations already encoded |
| **Dependencies** | **`config/disease_profiles.py` — only 2 profiles exist (§1)** |
| **Validation level** | Mixed. Mechanistic/safety/disease-fit/manufacturing: rule-based, literature-informed, uncalibrated. **Regulatory: `verdict_available = False` pending calibration (DECISION 6)** — the favourable disease-fit verdict threshold is unreachable (ceiling 68.33) |
| **Real calculation?** | **Yes** — Streamlit-free static methods over dataclasses; the highest-quality code in the repository |
| **Migration status before this work** | **Migration in progress** — genuine, golden-vector covered, not connected |
| **Work required** | Endpoint + disease-support gate. **Blocked for 3 of 5 indications** by §1 |

### 2.8 Projects

| Field | Value |
|---|---|
| **Legacy source** | `design_persistence.py`, `models.py` (SQLite, `nano_bio.db`) |
| **Purpose** | Group designs and runs into research projects |
| **Dependencies** | Server-side persistence |
| **Real calculation?** | N/A — organisational |
| **Known defect** | `design_persistence.py` calls `init_design_db()` **at import time** (line 568), creating `nano_bio.db` in the CWD on a bare import — **DEFECT-D11**. Cannot be imported safely by tests |
| **Migration status before this work** | **Not yet operational** (placeholder page) |
| **Work required** | New backend persistence; the legacy module is not safely reusable as-is |

### 2.9 Simulation History

| Field | Value |
|---|---|
| **Legacy source** | `modules/trial_registry.py` (`trial_registry.db`), `design_history.py`, `pages/6_Trial_History.py` |
| **Purpose** | Reproducible record of past runs |
| **Real calculation?** | N/A — storage. Trial-ID generation is genuine and golden-vector covered |
| **Migration status before this work** | **Not yet operational** (placeholder page) |
| **Work required** | Run persistence with inputs, versions and results |

### 2.10 Reports

| Field | Value |
|---|---|
| **Legacy source** | `reports/scientific_report_generator.py` (Streamlit-free), `modules/professional_report_generator.py` (59 KB, Streamlit-coupled), `utils/pdf_generator.py`, `export.py` |
| **Purpose** | Scientific report generation and export |
| **Inputs** | `TrialDesignInputs` + disease code; chains all 5 assessment engines |
| **Outputs** | `ScientificReport` dataclass → PDF/JSON/CSV |
| **Dependencies** | **The assessment engines** — therefore inherits the §1 disease ceiling |
| **Real calculation?** | **Yes**, but entirely derived from the engines |
| **Migration status before this work** | **Not yet operational** (placeholder page) |
| **Work required** | Report assembly from *stored runs* rather than from the unmigrated engine chain |

### 2.11 Protocol Generator

| Field | Value |
|---|---|
| **Legacy source** | `modules/protocol.py` (40 KB, ~25 pure functions + Streamlit shell) |
| **Purpose** | 10-section wet-lab synthesis/characterisation protocol |
| **Inputs** | Design dict (`Material`, `Size`, `Charge`, `Ligand`, payload, loading, `Target`) |
| **Outputs** | Deterministic protocol text |
| **Dependencies** | Streamlit at module scope only; the generators themselves are pure |
| **Validation level** | Template text derived from method literature. **Not a validated laboratory procedure** |
| **Real calculation?** | Deterministic template selection — genuine, but not a scientific *calculation* |
| **Migration status** | **Migration in progress** |
| **Work required** | Decouple the module-level Streamlit import, golden-vector the text output, expose an endpoint. Requires `Material`/`Target`/payload fields the React form does not yet collect (§2.2) |

### 2.12 Molecular Visualization

| Field | Value |
|---|---|
| **Legacy source** | `components/nanoparticle_3d_viewer.py` |
| **Purpose** | 3-D representation of core, coating, ligands |
| **Real calculation?** | Partially — `generate_core_sphere()`, `generate_peg_coating_layer()`, `generate_targeting_ligands()` are genuine geometry from design parameters. The rest is Plotly rendering |
| **Migration status** | **Not yet operational** |
| **Work required** | Geometry generators are portable; the React side needs a 3-D renderer (three.js/react-three-fiber), which is a substantial new frontend dependency. Out of scope here |

### 2.13 ML Training

| Field | Value |
|---|---|
| **Legacy source** | `pages/10_ML_Training.py`, `components/ml_predictor.py`, `nanobio_studio_backend/app/ml/{trainer,features,encoders,exporters}.py`, `models_store/` |
| **Purpose** | Train and evaluate property-prediction models |
| **Inputs** | `comprehensive_lnp_dataset.csv` (31 KB) |
| **Outputs** | Pickled models + metadata with genuine metrics |
| **Real calculation?** | **Yes, partially.** `models_store/` holds **31 genuine trained toxicity models** with real train/validation MAE/RMSE/R² (e.g. linear regression validation R² 0.984). **[VERIFIED]** |
| **Critical gap** | **Only `toxicity_prediction` models exist.** `predict_uptake()` and `predict_particle_size()` silently fall back to `_estimate_*_heuristic()` when no model is loaded (`ml_predictor.py:200,246`). The legacy headline score was bucketed from **uptake** — i.e. from a heuristic presented as an ML prediction. **[VERIFIED]** |
| **Migration status** | **Limited prototype** (toxicity only) / **Not yet operational** (uptake, size) |
| **Work required** | Training-run history is genuine and exposable. Serving predictions requires deciding what to do about the silent heuristic fallback — a scientific decision, not an engineering one |

### 2.14 AI Co-Designer

| Field | Value |
|---|---|
| **Legacy source** | `ai_engine/` (Optuna optimiser, Pareto front, sensitivity, seeding, audit), `pages/7_AI_Co_Designer.py` |
| **Purpose** | Multi-objective formulation optimisation |
| **Real calculation?** | **Mixed, and this is the problem.** `ai_engine/optimizer.py` (Optuna), `pareto.py`, `explainability.py` and `seed_everything` are genuine and reproducible. But **`ai_engine/simulator_adapter.py::simulate_design_placeholder()` is explicitly a placeholder** with toy proxies (`auc = dose*10/(1+|zeta|/25)`), so the optimiser currently optimises against a fake objective. **[VERIFIED]** |
| **Known defect** | `pages/7_AI_Co_Designer.py:364-373` displayed a **hard-coded candidate table** (`Score: [94.2, 91.5, 89.8, 87.3, 84.9]`) independent of every design parameter, plus a fabricated audit trail — **DEFECT-D6**, already quarantined out of `pages/` |
| **Migration status** | **Not yet operational** |
| **Work required** | Wire `simulator_adapter` to the genuine connected engines (scoring + PK) instead of the placeholder. Until then it cannot meet the stated bar ("calculates every displayed score"), so it stays visibly unavailable |

### 2.15 Administration

| Field | Value |
|---|---|
| **Legacy source** | `auth.py` (49 KB, 40+ functions), `rbac.py`, `pages/4_Admin_Panel.py` |
| **Purpose** | Accounts, roles, activity audit |
| **Real calculation?** | N/A |
| **Migration status** | **Migration in progress** — auth itself is **Operational** (bcrypt, HttpOnly cookie, roles enforced backend-side); the *admin UI* is not built |
| **Known defect** | `auth.py` calls `init_db()` at import (line 88) — **DEFECT-D11**; cannot be imported by tests |
| **Work required** | Admin CRUD endpoints + UI. The backend already has `auth_models`, `auth_service`, role enforcement |

### 2.16 Settings

| Field | Value |
|---|---|
| **Legacy source** | Scattered (`config/`, per-user `custom_weights` in session state) |
| **Real calculation?** | N/A |
| **Migration status** | **Not yet operational** |
| **Work required** | Decide what is genuinely user-configurable. Scoring-weight overrides are a **scientific** decision (they change results), not a preference |

### 2.17 Help & Tutorial

| Field | Value |
|---|---|
| **Legacy source** | `modules/tutorial.py` (21 KB, 6 guided exercises), `pages/98_Tutorial.py` |
| **Purpose** | Guided onboarding |
| **Real calculation?** | No — instructional text, plus exercises that invoke the real engines |
| **Migration status** | **Not yet operational** |
| **Work required** | Content port. The **Demo Workspace** delivered in this work covers the same need functionally |

---

## 3. Legacy predictors and engines — full sweep

### 3.1 The 19 `components/` predictors

Each exposes `predict_*()` (computation) + `display_*_widget()` (Streamlit). The computation
halves are separable.

| Predictor | Real calculation? | Validation level | Status |
|---|---|---|---|
| `charge_predictors` | Yes — pH-dependent zeta heuristics | Literature-informed, uncalibrated | Migration in progress |
| `cellular_uptake_predictor` | Yes — size/charge/ligand rules | Uncalibrated | Migration in progress |
| `immune_response_predictor` | Yes — PEG/complement rules | Uncalibrated | Migration in progress |
| `intracellular_trafficking_predictor` | Yes | Uncalibrated | Migration in progress |
| `payload_release_predictor` | Yes | Uncalibrated | Migration in progress |
| `stability_storage_predictor` | Yes | Uncalibrated | Migration in progress |
| `tumor_microenvironment_predictor` | Yes | Uncalibrated | Migration in progress |
| `blood_safety_assessor` | Yes — hemolysis rules | Uncalibrated | Migration in progress |
| `osmolarity_calculator` | **Yes — genuine physical chemistry** | Standard formula | Migration in progress |
| `batch_quality_control_predictor` | Yes | Uncalibrated | Migration in progress |
| `manufacturing_scalability_predictor` | Yes | Uncalibrated | Migration in progress |
| `cost_analysis_predictor` | Yes — cost model | Indicative only | Migration in progress |
| `environmental_impact_predictor` | Yes | Uncalibrated | Migration in progress |
| `reproducibility_assessment_predictor` | Yes | Uncalibrated | Migration in progress |
| `literature_comparison_predictor` | Partly — compares against embedded reference values | Provenance of reference values unverified | **Calibration required** |
| `intellectual_property_predictor` | **Questionable** — emits a "patent likelihood %" from heuristics | **No basis for a patentability probability** | **Not yet operational** |
| `publication_readiness_predictor` | Questionable — scores "publication readiness" | No basis | **Not yet operational** |
| `nanoparticle_3d_viewer` | Geometry yes, rest rendering | N/A | Not yet operational |
| `ml_predictor` | Mixed — see §2.13 | Toxicity model genuine; uptake/size heuristic | Limited prototype |

**None of the 19 is connected to the React application**, and none is connected by this work.
They are individually small; the blocker is that migrating ~19 uncalibrated heuristic
predictors would multiply the number of uncalibrated numbers on screen without improving
scientific standing. Recommend prioritising by scientific defensibility, starting with
`osmolarity_calculator` (a standard physical-chemistry formula).

### 3.2 Toxicity model

`utils/toxicity_model.py` — 7 independent risk factors, each returning `(score, rationale)`,
combined by `calculate_overall_safety_score()`. Streamlit-free, golden-vector covered.
**Migration in progress.** Note it uses a **mixed key convention** (documented in its own
docstring and in `tests/golden_vectors/inputs.py`), which any adapter must reproduce exactly.

### 3.3 Design scorer (System 2)

`utils/design_scorer.py` — a **second, non-equivalent** 6-weight scoring system, imported only
by the legacy `modules/design.py`. **Must not be migrated** alongside System 1 without a
scientific decision about which is canonical; DECISION 3A already designates
`core/scoring.py` as the Principal Design Score.

### 3.4 Release profile model

`utils/pk_model.py::simulate_release_profile()` — 4 genuine release modes (burst, sustained,
controlled, default). Golden-vector covered, **not migrated** (it is a release model, not PK).

---

## 4. Summary table

Status **as audited on 2026-07-31**, before the integration slice. The delivered
state is in `docs/INTEGRATION_SLICE.md` §7 and is shown in the right-hand column.

| # | Module | Audited status | Delivered status | Genuine legacy source | Endpoint |
|---|---|---|---|---|---|
| 1 | Disease & Therapeutic Selection | Operational | **Operational** | `data/disease_drug_mapping.py` | client data |
| 2 | Nanoparticle Design Parameters | Operational | **Operational** | `pages/1_Design_Parameters.py` | request schema |
| 3 | Design Impact Score | Operational | **Operational** | `core/scoring.py` | `POST /api/v1/design/score` |
| 4 | PK Simulation | Operational | **Operational** | `utils/pk_model.py` | `POST /api/v1/pk/simulate` |
| 5 | Results | Operational | **Operational** | display layer | — |
| 6 | Demo Workspace | did not exist | **Operational** | new (typed fixtures) | `/api/v1/demo/*` |
| 7 | Compare Designs | Not yet operational | **Operational** | new | `/api/v1/runs/compare/select` |
| 8 | Simulation History | Not yet operational | **Operational** | replaces `modules/trial_registry.py` | `/api/v1/runs` |
| 9 | Projects | Not yet operational | **Operational** | replaces `design_persistence.py` (D11) | `/api/v1/projects` |
| 10 | Reports | Not yet operational | **Limited prototype** | replaces `reports/scientific_report_generator.py` | client-side, from a stored run |
| 11 | Scientific Assessments | Migration in progress | Migration in progress — **blocked B1, B2** | `engine/` ×6 | — |
| 12 | Protocol Generator | Migration in progress | Migration in progress | `modules/protocol.py` | — |
| 13 | Molecular Visualization | Not yet operational | Not yet operational | `components/nanoparticle_3d_viewer.py` | — |
| 14 | ML Training | Limited prototype | Limited prototype (not surfaced) — **blocked B3** | `models_store/` + `app/ml/` | — |
| 15 | AI Co-Designer | Not yet operational | Not yet operational — **blocked B4** | `ai_engine/` (placeholder objective) | — |
| 16 | Administration | Migration in progress (auth Operational) | unchanged | `auth.py`, `rbac.py` | `/api/v1/auth/*` |
| 17 | Settings | Not yet operational | unchanged | scattered | — |
| 18 | Help & Tutorial | Not yet operational | unchanged (Demo Workspace covers the need) | `modules/tutorial.py` | — |

---

## 5. Scientific blockers — decisions required, not code

These cannot be resolved by engineering and are **not** being decided automatically:

| # | Blocker | Blocks |
|---|---|---|
| **B1** | Only 2 disease profiles exist (HCC-S, PDAC-I). New profiles must be authored and reviewed | Assessments, Reports for Breast / Lung / Colorectal |
| **B2** | `RegulatoryEngine.verdict_available = False`; the favourable disease-fit threshold is uncalibrated and unreachable (ceiling 68.33) | Regulatory verdict |
| **B3** | No uptake or particle-size ML model exists; the code silently substitutes heuristics | ML-backed uptake/size predictions |
| **B4** | `ai_engine` optimises against `simulate_design_placeholder()`, a toy objective | AI Co-Designer |
| **B5** | Two non-equivalent scoring systems (System 1 vs System 2) and no approved composite formula | Any combined ranking, incl. Compare |
| **B6** | 16 of 19 predictors are uncalibrated heuristics; 2 (`intellectual_property`, `publication_readiness`) have no defensible basis at all | Bulk predictor migration |
| **B7** | No uncertainty quantification exists anywhere in the codebase | Confidence intervals on any output |

---

## 6. Known defects carried forward (not reintroduced)

| ID | Defect | Handling |
|---|---|---|
| D1 | Unsupported disease silently scored as HCC-S | Must return an explicit unsupported status |
| D5/D7 | Hard-coded 92/89/82 headline score; favourable 89 on exception | Not migrated |
| D6 | Hard-coded AI candidate table | Quarantined; not migrated |
| D8 | Regulatory engine chain crash | Fixed in Step 1 |
| D9 | Null-vs-absent input contract | Fixed in Step 1; the API contract depends on it |
| D11 | Import-time DB creation in `auth.py` / `design_persistence.py` | Those modules are never imported by the backend or tests |
