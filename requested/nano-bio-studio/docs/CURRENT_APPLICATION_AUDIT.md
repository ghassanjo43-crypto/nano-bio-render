# NanoBio Studio — Current Application Audit (Phase 1)

**Audit date:** 2026-07-30
**Auditor:** Automated repository assessment (Claude Opus 5)
**Scope:** `D:\Nano_bio_Studio_30-7-2026` — full repository, read-only assessment
**Purpose:** Establish a verified baseline before any migration to React + FastAPI + PostgreSQL on Render.

> **Status of this document.** Phase 1 deliverable. No application code was modified to produce it.
> Findings marked **[VERIFIED]** were confirmed by executing code in this repository.
> Findings marked **[STATIC]** come from reading code only and have not been executed.

### Audit-time side effects (full disclosure)

Two changes to the working tree occurred around this audit. Both are disclosed rather than hidden:

1. **`users.db` was created/initialised** — this happened *before* the audit, while fixing the
   `UnicodeEncodeError` that prevented the app from starting. The pre-existing `db_init` bug meant
   the database had never been successfully committed. It now contains 1 admin user + 1 activity row.
2. **`trial_registry.db` was created and then removed.** Probing the trial-ID generator
   auto-created this database (it did not exist in the pre-audit file inventory) and consumed
   3 sequence numbers. It contained **zero** trial records. It was deleted to restore the pre-audit
   state, so the user's first real trial today still receives sequence `00001`.
3. **`Login.py` lines 11–19** — a UTF-8 stdout guard added during the pre-audit startup fix.
   This is the only source file changed, and it is not a scientific change.

---

## 1. Current project structure and architecture

### 1.1 Runtime shape

A **Streamlit multipage application**. There is no API layer, no service boundary, and no
separation between presentation and computation in the page modules.

- **Entry point:** `Login.py` (repo root). Declares itself the Streamlit Cloud entry point.
- **Navigation:** Streamlit's `pages/` convention, plus `st.switch_page()` calls.
- **Process model:** single Python process; all state in `st.session_state` (per-browser-session,
  in-memory) plus several on-disk SQLite files.
- **Python:** running under system Python 3.14 with Streamlit 1.58.0.
  (`nanobio_studio_backend/pyproject.toml` targets `>=3.11`.)

### 1.2 Directory map (root = authoritative application)

| Directory | Files | Size | Streamlit-coupled? | Role |
|---|---:|---:|---|---|
| `pages/` | 17 | 441 KB | **Yes** | Live UI pages + workflow |
| `modules/` | 17 | 341 KB | **Mostly** | Legacy monolith feature modules |
| `components/` | 25 | 212 KB | **Mostly** | 19 domain "predictor" widgets |
| `engine/` | 7 | 121 KB | **No** | Newest scientific assessment engines |
| `nanobio_studio_backend/` | 50 | 138 KB | **No** | Pre-existing FastAPI/SQLAlchemy scaffold |
| `data/` | 6 | 84 KB | **No** | Scientific mapping tables |
| `ai_engine/` | 14 | 52 KB | **No** | Optuna optimiser + Pareto + explainability |
| `utils/` | 4 | 46 KB | **No** | PK model, toxicity model, scorer, PDF |
| `tabs/` | 11 | 60 KB | Yes | **Dead code** — see §11 |
| `ui/` | 11 | 17 KB | Yes | Styling/nav helpers |
| `core/` | 3 | 16 KB | Marginal | **Production scoring function** |
| `config/` | 3 | 9 KB | **No** | Scoring weights + disease profiles |
| `models/` | 2 | 12 KB | **No** | Scientific report dataclasses |
| `reports/` | 2 | 14 KB | **No** | Scientific report generator |
| `tests/` | 2 | 11 KB | No | 1 real test module |
| `biotech-lab-main/` | 154 | 1,238 KB | Yes | **Older duplicate snapshot** |

### 1.3 The `biotech-lab-main` duplication — important

`biotech-lab-main/` is an **older, near-complete copy** of the application, not a subcomponent.

- 148 `.py` files exist in both root and `biotech-lab-main/`. **139 are byte-identical.**
- 9 have diverged: `modules/cost.py`, `modules/design.py`, `modules/simulation.py`,
  `modules/trial_registry.py`, `modules/professional_report_generator.py` (59.3 KB root vs 37.2 KB),
  `components/sidebar_navigation.py`, `pages/About_AI_Co_Designer.py`, `audit_dashboard.py`,
  `streamlit_auth.py`.
- **The root is authoritative.** All newer work exists only at root: the entire live `pages/` set,
  `engine/`, `config/`, `models/`, `reports/`, the 19 predictor components, and `data/` mappings.
- `biotech-lab-main/app.py` (147 KB) is the **older monolithic app** — no root equivalent.
- **`Login.py:17` puts `biotech-lab-main` on `sys.path`.** Root paths are inserted first, so root
  wins, but this makes shadowing possible and import resolution ambiguous. **[STATIC]**
- `biotech-lab-main/` has its own `users.db` (16 KB) and its own `.venv_new`.

**Migration consequence:** exactly one lineage must be designated the scientific reference.
Recommendation: **root**. `biotech-lab-main/` should move to `legacy_streamlit/` untouched.

### 1.4 Existing FastAPI backend (significant asset)

`nanobio_studio_backend/` is **already** a FastAPI + SQLAlchemy + Alembic + Pydantic project with
its own `pyproject.toml`, `alembic.ini`, `.env.example`, and `tests/`. It is **not wired to the
Streamlit app** and addresses a different problem: **LNP experimental-record ingestion and ML
dataset construction**, not the design/simulation workflow.

Present: `app/main.py`, `api/routes/{health,ingestion,ml,query}.py`, `core/{config,constants,logging}.py`,
`db/{base,models,session}.py`, `ingestion/{csv,json}_importer.py`, `ml/{trainer,features,encoders,exporters,dataframe_builder}.py`,
`qc/validators.py`, and 9 Pydantic schema modules (`lnp_record`, `lipids`, `payloads`,
`formulations`, `process_conditions`, `characterization`, `assays`, `biological_models`, `experiments`).

**Notably it already uses `pydantic-settings` for env-var config** — the only part of the repo that does.
It should be adopted as the Phase 2/3 foundation rather than rebuilt.

---

## 2. Complete feature inventory

### 2.1 Live user workflow (3 declared steps)

`Login.py` → `pages/0_Disease_Selection.py` → `pages/1_Design_Parameters.py` → `pages/2_Run_Simulation.py`

| Page | Widgets | Function |
|---|---:|---|
| `Login.py` | 5 | Sign in / self-register, session bootstrap, DB init |
| `0_Disease_Selection.py` | 3 | Disease + subtype + therapeutic drug selection, epidemiology |
| `1_Design_Parameters.py` | 78 | **Primary input surface** — 23-field design + weight tuning + 19 predictors |
| `2_Run_Simulation.py` | 6 | PK simulation, ML predictions, scoring, PDF/CSV export |
| `4_Admin_Panel.py` | 15 | User management, roles, activity log |
| `6_Trial_History.py` | 4 | Saved trials, re-open, delete, report export |
| `7_AI_Co_Designer.py` | 9 | Optuna-driven design optimisation |
| `8_Protocol_Generator.py` | 12 | 10-section wet-lab protocol generation |
| `9_AI_Architecture.py` | 0 | Static explainer |
| `10_ML_Training.py` | 23 | Dataset stats, model training, evaluation |
| `98_Tutorial.py` | 5 | 6 guided exercises |
| `99_Features.py` | 0 | Static feature list |
| `13_ML Training/` (5 pages) | — | AI architecture, training process, feature engineering, validation, dataset stats |
| `About_AI_Co_Designer.py` | 0 | **"Coming Soon" placeholder** |

### 2.2 The 19 predictor components

Each exposes `predict_*()` (computation) + `display_*_widget()` (Streamlit rendering) — a
consistent pattern that makes extraction to backend services tractable.

`batch_quality_control`, `cellular_uptake`, `charge_predictors`, `cost_analysis`,
`environmental_impact`, `immune_response`, `intellectual_property`, `intracellular_trafficking`,
`literature_comparison`, `manufacturing_scalability`, `payload_release`, `publication_readiness`,
`reproducibility_assessment`, `stability_storage`, `tumor_microenvironment`,
`blood_safety_assessor` (hemolysis), `osmolarity_calculator`, `nanoparticle_3d_viewer`, `ml_predictor`.

### 2.3 Supporting subsystems

- **Auth/RBAC** — `auth.py` (45 KB, 40+ functions), `rbac.py`, `streamlit_auth.py`
- **Persistence** — `design_persistence.py`, `design_history.py`, `persistence.py`, `models.py`, `modules/trial_registry.py`
- **Export** — `export.py`, `utils/pdf_generator.py`, `modules/professional_report_generator.py`, `reports/scientific_report_generator.py`
- **External data** — `modules/data_integrations.py`, `hybrid_toxcast_connector.py`, `live_data_orchestrator.py`, `data_downloader.py`
- **Optimisation** — `ai_engine/` (Optuna, Pareto front, sensitivity, audit records)
- **Audit** — `audit_dashboard.py`, `ai_engine/audit.py`, `auth.py` activity log

---

## 3. Scientific calculations and simulation models

### 3.1 CRITICAL: four parallel, non-equivalent scoring systems

This is the single most important finding for scientific migration. **Four different overall-score
formulas coexist**, with different weights and different parameter sets. **[VERIFIED]**

#### System 1 — `core/scoring.py::compute_impact()` — **the production scorer**

Used by the live pages (`1_Design_Parameters.py`, `2_Run_Simulation.py`). Returns
`{Delivery 0–100, Toxicity 0–10, Cost 0–100}` from **12 weighted sub-scores**:

| Component | Weight | Component | Weight |
|---|---:|---|---:|
| size | 0.18 | targeting | 0.08 |
| encapsulation | 0.18 | hydrodynamic | 0.06 |
| charge | 0.14 | hydrophobicity | 0.05 |
| pdi | 0.10 | crystallinity | 0.05 |
| stability | 0.04 | coating | 0.05 |
| release | 0.04 | surface_area | 0.04 |

Weights are user-overridable in the UI and re-normalised to sum to 1.0 (`core/scoring.py:167-170`).
Sub-score rules include: size optimum 80–120 nm; charge optimum ±10 mV; PDI score `100 - pdi*200`;
hydrodynamic/core ratio optimum 1.0–1.3; coating bonuses (PEG +30, HA +20, chitosan +15, albumin +10);
ligand cost map (GalNAc 20, Folate 15, Transferrin 30, RGD 25, Anti-HER2 40).

A **fifth** formula also lives here — `overall_score_from_impact()`:
`clip(Delivery*0.6 + (10-Toxicity)*3 + (100-Cost)*0.1, 0, 100)`.

#### System 2 — `utils/design_scorer.py::DesignScorer` — 6 weights

Size 0.25, Material 0.20, Ligand 0.20, Charge 0.15, PDI 0.10, Loading 0.10.
**Only imported by `modules/design.py`** (legacy module, not the live pages).

#### System 3 — `config/scoring_config.py` — 5 weights

Delivery 0.35, Safety 0.25, Manufacturability 0.20, Disease-fit 0.15, Stability 0.05.
Used by **all six `engine/` modules**. Includes confidence thresholds (high ≥0.75, medium ≥0.50)
and performance bands (Excellent ≥85, Good ≥75, Acceptable ≥65).

#### System 4 — hard-coded constants — **what the user actually sees**

`pages/2_Run_Simulation.py:314-323` sets the headline "Overall Score" by bucketing uptake efficiency:

```
uptake > 85  → overall_score = 92 ("Excellent")
uptake > 75  → overall_score = 89 ("Good")
else         → overall_score = 82 ("Satisfactory")
```

and `:337-338` — on **any** exception — `overall_score = 89 ("Good")`.

**This is not a calculation.** The prominent score is one of three constants, and prediction
failure silently yields a favourable "89 / Good". This must be flagged in the migration and
must not be reproduced as if it were a scientific result. **[VERIFIED by code inspection at those lines]**

#### Documentation drift

`docs/scoring_system.md` (21 KB, with ~18 DOI citations) documents **System 2** — a 6-parameter
formula with a worked example yielding 92.5/100. The live application uses **System 1** for
components and **System 4** for the headline. The published scientific documentation therefore
does **not** describe the running code.

### 3.2 Pharmacokinetic model — `utils/pk_model.py` (clean, portable)

`two_compartment_model(dose, kabs, kel, k12, k21, duration=48.0, dt=0.1)` — depot → central →
peripheral, solved by **explicit forward Euler** at fixed `dt=0.1 h`:

```
dC_depot  = -kabs*C_depot
dC_plasma =  kabs*C_depot - kel*C_plasma - k12*C_plasma + k21*C_tissue
dC_tissue =  k12*C_plasma - k21*C_tissue
```

> **Migration constraint.** The Euler scheme with `dt=0.1` **is** the model's numerical identity.
> Replacing it with `scipy.integrate.solve_ivp` or any adaptive solver **will change results**.
> Port the loop verbatim; do not "improve" the integrator.

`calculate_pk_parameters()` derives C_max, T_max, AUC (trapezoid), terminal half-life, tissue
accumulation ratio, Vss ratio. Half-life uses a **bare `except:`** returning `None`
(`pk_model.py:134-135`) — must be preserved as an explicit nullable, not silently defaulted.

`simulate_release_profile()` — 4 modes: `burst` (`1-exp(-3kt)`), `sustained` (`1-exp(-kt)`),
`controlled` (zero-order, `min(1, kt/10)`), default sustained.

NumPy 1.x/2.x compatibility shim for `trapezoid`/`trapz` at `pk_model.py:11-14`.

### 3.3 Toxicity model — `utils/toxicity_model.py` (clean, portable)

7 independent risk factors, each returning `(score, rationale)`: size, charge, dose, PDI, ligand,
payload, material → `calculate_overall_safety_score()`. This drives the safety radar chart.

### 3.4 The `engine/` assessment layer (best-quality code in the repo)

Six Streamlit-free engines, all static methods over dataclasses — **directly portable to FastAPI services**:

| Engine | Produces |
|---|---|
| `mechanistic_engine.py` | delivery efficacy, toxicity, manufacturability, storage stability, targeting efficacy, payload release. Named constants (`OPTIMAL_SIZE_MIN=80`, `MAX=150`, `SUBOPTIMAL_PENALTY=15`, `OVERSIZED_PENALTY=20`, `PEG_COATING_BENEFIT=8`, `PEG_DENSITY_BENEFIT=5`, `LIGAND_BENEFIT=12`) |
| `safety_engine.py` | 6 risk components: systemic toxicity, immunogenicity, off-target, aggregation, premature release, metabolic burden + risk bands |
| `disease_fit.py` | barrier-mitigation scoring, size/charge/targeting/formulation fit, mismatch identification |
| `manufacturing_engine.py` | size control, process complexity, QC, scale-up, cost, cycle time, GMP readiness, roadmap |
| `regulatory_engine.py` | regulatory stage/category/strategy, pathway, risks, evidence gaps, recommended studies |
| `confidence_engine.py` | evidence distribution, per-component confidence, bottlenecks, reliability, narrative |

`models/scientific_assessment.py` supplies the dataclass contracts and — importantly — already
encodes **`EvidenceLevel`, `ConfidenceLevel`, `RegulatoryStage`, `PredictionBasis`,
`AIModelTransparency`, `ReportLimitations`**. Safety rule 9's classification vocabulary
**already exists in the codebase** and should be carried forward, not reinvented.

### 3.5 Optimisation — `ai_engine/`

Optuna-based (`run_optimization`), scalarised multi-objective with `ObjectiveWeights`,
Pareto front (`pareto.py`), one-at-a-time sensitivity (`explain_design`), seedable
(`seed_everything`) — **reproducibility hook already present**.

`ai_engine/simulator_adapter.py::simulate_design_placeholder()` — **explicitly a placeholder**.

---

## 4. Application inputs and outputs

### 4.1 Canonical design schema — 23 fields (`pages/1_Design_Parameters.py:157-182`)

| Field | Default | Field | Default |
|---|---|---|---|
| `Material` | "Lipid NP" | `PorosityLevel` | "Mesoporous (2-50nm)" |
| `Target` | "Liver Cells" | `PoreSize` | 5.0 |
| `Size` | 100 | `SurfaceCoating` | `["PEG (Stealth)"]` |
| `PDI` | 0.15 | `CoatingThickness` | 2.5 |
| `HydrodynamicSize` | 120 | `FunctionalGroups` | `["-COOH (Carboxyl)"]` |
| `Encapsulation` | 85 | `Hydrophobicity` | 1.5 |
| `EncapsulationMethod` | "Passive Loading" | `Ligand` | "GalNAc" |
| `Charge` | -5 | `LigandDensity` | 60 |
| `SurfaceArea` | 250 | `Receptor` | "ASGPR" |
| `Stability` | 85 | `ReceptorBinding` | 10.0 |
| `DegradationTime` | 30 | `ReleaseProfile` | "Sustained (1 week)" |
| `CrystallinityIndex` | 65 | `ReleasePredictability` | 85 |

Consumed by `core/scoring.py` via `d["…"]` / `d.get("…", default)`. **Note:** `Size`, `Charge`,
`Encapsulation` are accessed with **bare subscripts** — a missing key raises `KeyError`.
All others have inline defaults. There is **no schema validation layer**; Pydantic models in
Phase 3 must reproduce these defaults exactly.

Also in session state but outside this dict: disease selection (`selected_disease`, `hcc_subtype`),
drug selection, dose, and per-user weight overrides (`custom_weights`).

### 4.2 Widget inventory (app-wide)

69 `number_input`, 43 `selectbox`, 32 `checkbox`, 23 `slider`, 22 `text_input`,
19 `download_button`, 5 `multiselect`, 3 `text_area`, 3 `form_submit_button`,
2 `file_uploader`, 1 `radio`.

### 4.3 Outputs

**Numeric:** Delivery (0–100), Toxicity (0–10), Cost (0–100), overall score, 7-factor safety
profile, PK parameters (C_max, T_max, AUC, t½, accumulation ratio, Vss), 19 predictor result sets,
confidence scores, regulatory stage, manufacturability.

**Files** (via 19 `download_button` calls):

| Format | Examples |
|---|---|
| PDF | `{trial_id}_report.pdf`, `{Material}_simulation_report.pdf` |
| CSV | `{Material}_pk_data.csv`, `{Material}_pk_params.csv`, `_cost_data.csv`, `_design.csv` |
| JSON | `{name}_complete_export.json`, `{name}_design.json`, `{trial_id}_report.json` |
| PNG | `{Material}_pk_plot.png`, `{name}_risk_chart.png` |
| TXT/MD | `{name}_protocol.txt`, `_protocol.md`, `_safety_report.txt`, `_cost_analysis.txt` |

**Charts:** matplotlib (PK profiles, safety radar) and Plotly (28 files) — Plotly's JSON spec
is the easier bridge to a React frontend.

---

## 5. Authentication and user management

### 5.1 Implemented in `auth.py` (40+ functions)

Login, self-registration, role update, password change/reset, activate/deactivate, delete,
user listing/detail, admin bootstrap, admin counting, plus an extensive audit subsystem
(activity log, per-user trail, date filters, stats, search, export, design/optimisation/admin
action logging, report generation) and an `AuthManager` class.

- **Hashing:** bcrypt (`bcrypt.hashpw` / `checkpw`) — acceptable; Argon2 would be an upgrade.
- **Password policy:** `MIN_PASSWORD_LENGTH = 6`, regex requires ≥1 letter and ≥1 digit. **Weak.**
- **Session timeout:** 30 minutes inactivity.
- **Self-registration:** **enabled** (`Login.py` "Create a New Account" tab), assigns role `student`.
  → Phase 4 should preserve registration, since the current app permits it.

### 5.2 Roles (`rbac.py`)

`Role` enum: `admin`, `student`, `viewer` (+ a `Permission` enum, decorators
`require_permission` / `require_role`, and `can_access_tab` / `get_available_tabs`).

> There is **no `researcher` role** in the current application. Introducing one in Phase 4 would be
> a new feature, not a migration. Flagging per the "do not silently change" rule.

Role-default inconsistency: `auth.py` defaults new users to `student`; `db_init.py` creates the
users table with `role TEXT DEFAULT 'viewer'`. The **live database uses `'viewer'`** (§6.2).

### 5.3 Session tokens — CRITICAL VULNERABILITY **[VERIFIED]**

`streamlit_auth.py:73`:

```python
token = f"token_{user_id}_{int(datetime.now(timezone.utc).timestamp())}"
```

and `Login.py:153-158` passes `user_id=username`. So a real token is literally `token_admin_1785…`.

Three compounding defects:

1. **Predictable / forgeable.** Not cryptographic. Knowing a username reduces forgery to guessing
   a Unix *second*. Contrast `secrets.token_urlsafe()`. (`secrets` is even imported in `auth.py`
   but not used for this.)
2. **Plaintext at rest.** Stored in `sessions.json` — **21 live sessions** with `username`,
   `user_id`, `email`, `roles`, timestamps. **This file is not git-ignored** (§10.2).
3. **Transported in the URL.** `st.query_params["session_token"] = token` (`Login.py:170`,
   `components/sidebar_navigation.py:19,61`, and every page). Bearer tokens in query strings leak
   via browser history, server logs, and `Referer` headers.

**All three must be fixed in Phase 4** — httpOnly cookies or `Authorization: Bearer` with signed,
random tokens (or JWT; `PyJWT` is already a declared dependency, currently unused).

### 5.4 Other auth issues

- **`auth.py:171` calls `_reset_admin_session()` at import time.** Its own docstring says
  *"Remove in production."* Every import rewrites the admin's `session_start`/`last_activity`. **[STATIC]**
- **`auth.py:88` calls `init_db()` at import time** — import has DB side effects, which breaks
  testability and clean startup.
- **No rate limiting / lockout** on `authenticate()`. Unlimited password attempts.
- **Login page displays the credentials** `admin` / `admin` on screen (`Login.py:128-129`).
- **Hard-coded passwords in source:** `create_admin.py:31` and `set_admin_password.py:7` both
  contain `"<redacted — see ARCHIVE_NOTES.md>"`; `db_init.py` seeds `admin`/`admin`.
- **`reset_password()` takes no token** — it sets a new password directly, so there is no
  email-verified reset flow to migrate. Phase 4's token-based reset is **new functionality**.
- **`authenticate()` swallows all bcrypt errors** (`except Exception: ok = False`) — a type
  mismatch becomes a silent "wrong password" (see §6.2).

---

## 6. Database schema and `users.db` usage

### 6.1 Seven separate SQLite databases

Referenced in code: `users.db`, `trial_registry.db`, `nano_bio.db`, `ml_module.db`, `app.db`,
`nanobio_studio.db`, `nanoparticles_disease_tagged.db`. Most are created lazily on first use.
Currently on disk: `users.db` (28 KB) and `biotech-lab-main/users.db` (16 KB).

| DB | Owner module | Tables |
|---|---|---|
| `users.db` | `auth.py`, `db_init.py` | `users`, `activity_log` |
| `trial_registry.db` | `modules/trial_registry.py` | `trials`, `trial_sequences` |
| `nano_bio.db` | `design_persistence.py` | `user_designs`, `design_versions` |
| `nanobio_studio.db` | `models.py` (SQLAlchemy) | `users`, `projects`, `designs`, `optimizations`, `simulations` |
| `ml_module.db` | ML training pages | training records |

**Consolidation into one PostgreSQL schema is the single biggest Phase 4 task.**

### 6.2 `users.db` — live schema and a schema conflict **[VERIFIED]**

Actual live schema (queried read-only):

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT,                      -- NOT UNIQUE
    password_hash BLOB NOT NULL,     -- BLOB
    role TEXT DEFAULT 'viewer',      -- 'viewer'
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
  , last_activity TIMESTAMP, session_start TIMESTAMP);  -- added by ALTER

CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL, action TEXT NOT NULL,
    details TEXT, ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (username) REFERENCES users(username));
```

Indexes: `idx_activity_username`, `idx_activity_timestamp`. Contents: 1 user (`admin`/`admin`/active), 1 activity row.

**Two modules define `users` incompatibly:**

| | `db_init.py` | `auth.py` |
|---|---|---|
| `password_hash` | `BLOB` | `TEXT` |
| `role` default | `'viewer'` | `'student'` |
| `email` | not unique | `UNIQUE` |
| `last_activity`/`session_start` | absent | present |

Whichever runs first wins; **`db_init.py` won** (both use `CREATE TABLE IF NOT EXISTS`-style guards,
and `auth.py` then patched columns in via `ALTER TABLE`). Latent bug: if `auth.py`'s `TEXT` variant
ever wins, `bcrypt.checkpw` receives a `str`, raises `TypeError`, is swallowed by
`except Exception: ok = False`, and **all logins silently fail**. PostgreSQL migration must fix the
type to a single explicit choice (`BYTEA` or `TEXT`, consistently).

Also note `activity_log.username` is a **string FK** to `users.username` rather than `users.id`
— renaming a user orphans the audit trail. Phase 4 should key on `user_id`.

### 6.3 A good ORM already exists but is unused

`models.py` defines SQLAlchemy models `User`, `Project`, `Design`, `Optimization`, `Simulation`,
plus repository classes — with `parameters = Column(JSON)`, denormalised score columns,
`version`, and timestamps. It is **imported by no page** (grep found zero importers outside
`persistence.py`).

**This is the best available starting point for the PostgreSQL schema** — change
`DB_URL = "sqlite:///nanobio_studio.db"` (`models.py:14`) to an env-var-driven PostgreSQL URL,
add the reproducibility columns from §12, and generate the initial Alembic migration.

### 6.4 Trials and designs

`trials` (19 columns: disease, drug, `np_size_nm`, `np_charge_mv`, `np_peg_percent`,
`np_zeta_potential`, `np_pdi`, dose/route/frequency/duration, outcomes, notes, status, export path)
plus `trial_sequences` for per-day-per-disease sequence allocation.

Trial IDs: `TRIAL-{DISEASE}-NP{SIZE}-{YYYYMMDD}-{SEQUENCE:05d}`. Sequence allocation is a
read-modify-write with no locking — **a race under concurrent web users**. PostgreSQL should use a
sequence or `ON CONFLICT` upsert.

`user_designs` + `design_versions` (`design_persistence.py`) provide versioning with
`UNIQUE(username, design_name)` and `ON DELETE CASCADE`.

---

## 7. Reports, charts, files and exports

- **`modules/professional_report_generator.py`** (59 KB) — the richest report path:
  `infer_missing_parameters()` → `simulate_biological_environment()` → `calculate_delivery_metrics()`
  → narrative generators (executive summary, mechanistic interpretation, optimisation
  recommendations) → `generate_professional_pdf_report()` (ReportLab → `BytesIO`).
  **`infer_missing_parameters()` silently fabricates absent inputs** — must be surfaced as
  explicit assumptions in the new API response, not hidden.
- **`reports/scientific_report_generator.py`** — assembles the `engine/` outputs into the
  `ScientificReport` dataclass (with evidence/confidence/limitations).
- **`utils/pdf_generator.py`** — per-trial PDF.
- **`export.py`** — JSON / CSV / PDF design export.
- Nine `generate_*.py` root scripts produce DOCX/PDF documentation artefacts (sitemaps, dataset
  reports, scientific features). These are **build-time authoring tools, not app features** —
  they belong in `tools/`, not the backend.
- 13 `.docx` and 3 `.pdf` generated artefacts are committed at root, plus two Word lock files
  (`~$…docx`).

**Render consequence:** every export currently streams from memory or writes locally. On Render's
ephemeral filesystem, generated reports must be streamed to the client or stored in object
storage — never written to local disk for later retrieval (§10.4).

---

## 8. External databases, APIs, AI models, libraries

### 8.1 External sources

| Source | Type | Status |
|---|---|---|
| PubChem (`pubchem.ncbi.nlm.nih.gov/rest/pug`) | **Live HTTP** | `hybrid_toxcast_connector.py:47`, 10 s timeout |
| EPA ToxCast / CompTox | Live + local fallback | `live_data_orchestrator.py:50` |
| FDA FAERS (`api.fda.gov`) | Converter | `modules/data_integrations.py` |
| ClinicalTrials.gov | Converter + curated data | `modules/clinical_trials_data.py` |
| NCBI GEO | Converter | `modules/data_integrations.py` |
| ChemSpider | Converter | `modules/data_integrations.py` |
| RCSB PDB (`data.rcsb.org`) | Converter | `modules/data_integrations.py` |

Only **3 files** make real network calls; the rest are converters over local/sample data.
`HybridToxCastConnector` tries live then **silently falls back to a local template**, exposing
`self.source` ("LIVE PubChem API" vs "LOCAL TEMPLATE") — provenance is tracked and must be
surfaced in the new API.

**No API keys are required** by any current integration.

### 8.2 ML models — loading is broken **[VERIFIED]**

`components/ml_predictor.py` looks for `models/{toxicity,uptake,particle_size}_model.pkl`.
`models/` contains **only Python source**. The 57 `.pkl` bundles live in `models_store/` under a
different naming convention (`toxicity_prediction_<timestamp>.pkl` + `_preprocessor.pkl` + `_metadata.json`).

Executed result:

```
load_models()      -> {'toxicity': False, 'uptake': False, 'particle_size': False}
predict_toxicity() -> (1.75, 'Very Low')
predict_uptake()   -> (92.0, 'Excellent')
```

**No model loads, yet confident-looking values are still returned** — from
`_estimate_toxicity_heuristic()` / `_estimate_uptake_heuristic()`. `pages/2_Run_Simulation.py:33`
instantiates with `model_dir="models"`, so this is the live production path.

Disclosure exists — `"⚠️ Using Heuristic"` — but inside an expander with `expanded=False`
(`2_Run_Simulation.py:199`), so it is **hidden by default**, while the results section presents the
numbers under an "ML PREDICTIONS" heading. Combined with §3.1 System 4, the headline result is a
hard-coded constant driven by a heuristic. **Directly implicates safety rules 9 and 10.**

Model metadata that *does* exist is good: `model_types` (linear_regression, random_forest),
`target_variable`, train/validation MAE/RMSE/R², `created_at` — a real provenance record
(e.g. linear regression validation R² ≈ 0.984, which is suspiciously high and suggests possible
leakage or a synthetic dataset — worth investigating before relying on it).

### 8.3 Datasets

`comprehensive_lnp_dataset.csv` (31 KB, plus two `- Copy` duplicates), `sample_lnp_dataset.csv`,
24 CSVs total, `nanobio_studio_backend/data/sample_lnp_records.{csv,json}`.

### 8.4 Libraries

Declared: streamlit, numpy, pandas, matplotlib, scikit-learn, plotly, optuna, sqlalchemy, bcrypt,
pydantic, pydantic-settings, PyJWT, reportlab.

---

## 9. Hard-coded values and scientific assumptions

### 9.1 Configuration that must become environment variables

**`os.environ`, `os.getenv`, and `st.secrets` appear ZERO times in the root application.** **[VERIFIED]**
The only env-var handling anywhere is in `nanobio_studio_backend` (`pydantic-settings`).

Hard-coded and needing externalisation: all 7 DB paths; `SESSION_TIMEOUT_MINUTES = 30`;
`MIN_PASSWORD_LENGTH = 6`; admin credentials; `localhost:8501` / `localhost:3000`;
external API URLs and timeouts; `models_store` / `models` paths.

### 9.2 Scientific assumptions (preserve verbatim; document, don't "fix")

| Assumption | Value | Location |
|---|---|---|
| Optimal size | 80–120 nm (scoring) / 80–150 nm (engine) — **the two disagree** | `core/scoring.py:24`, `engine/mechanistic_engine.py:30` |
| Optimal charge | \|ζ\| ≤ 10 mV, then −3/mV | `core/scoring.py:32-35` |
| PDI score | `100 − PDI×200` | `core/scoring.py:69` |
| Hydrodynamic ratio | optimum 1.0–1.3, ideal 1.15 | `core/scoring.py:73-76` |
| Ligand density | optimum 50–80 % | `core/scoring.py:81` |
| Receptor binding | Kd < 50 nM = ideal | `core/scoring.py:87` |
| Surface area | optimum 200–400 nm² | `core/scoring.py:101` |
| Hydrophobicity | LogP 0.5–2.5 | `core/scoring.py:107` |
| Crystallinity | optimum 70–90 % | `core/scoring.py:113` |
| Coating thickness | optimum 2–5 nm | `core/scoring.py:135` |
| Coating bonuses | PEG 30, HA 20, chitosan 15, albumin 10 | `core/scoring.py:121-128` |
| Ligand costs | GalNAc 20, Folate 15, Transferrin 30, RGD 25, Anti-HER2 40 | `core/scoring.py:264-270` |
| Regulatory checklist | 8 binary gates; "approved material" = **only** Lipid NP or PLGA | `core/scoring.py:358-366` |
| Kupffer uptake | "80 % RES uptake without PEG" | `config/disease_profiles.py:37` |
| Sinusoidal fenestrae | 50–200 nm | `config/disease_profiles.py:35` |
| PDAC stroma | ">80 % of tumour mass" | `config/disease_profiles.py:62` |
| Tumour pH | 6.5–6.8 | `config/disease_profiles.py:38` |
| PK defaults | `duration=48 h`, `dt=0.1 h`, burst fraction 0.2, k_release 0.1 | `utils/pk_model.py:22-23,158-159` |

### 9.3 AMBIGUITY: disease taxonomy is fragmented across four modules **[VERIFIED]**

The UI offers **5 diseases × 3–4 subtypes (19 combinations)** via `data/disease_drug_mapping.py`:
Liver (HCC) — AFP-high / Immune-active / Immune-excluded / Immune-desert; Pancreatic;
Breast; Lung; Colorectal.

But the scientific engines read `config/disease_profiles.py`, which contains **only `HCC-S` and
`PDAC-I`** and **silently returns HCC-S for anything unrecognised** (`disease_profiles.py:91`):

```
requested 'HCC-MS'          -> returned HCC-S
requested 'Breast Cancer'   -> returned HCC-S
requested 'Triple-Negative' -> returned HCC-S
requested ''                -> returned HCC-S
```

Meanwhile `modules/disease_database.py` uses a **third**, differentiation-based vocabulary
(`hcc_s`/`hcc_ms`/`hcc_l`/`cholangio_intra`/`cholangio_extra`/`hepatoblastoma`) that does not
match the UI's immune-phenotype labels, and `modules/trial_registry.py` maps only
`hcc_s`/`hcc_ms`/`hcc_l`, yielding `UNKNOWN` for real UI selections:

```
'AFP-high HCC'                      -> TRIAL-UNKNOWN-NP100-…
'Triple-Negative (ER-, PR-, HER2-)' -> TRIAL-UNKNOWN-NP100-…
```

**Consequence:** selecting *Breast Cancer → Triple-Negative* produces an assessment computed
against **hepatocellular-carcinoma** biological barriers, labelled with the breast-cancer
selection, and filed under trial ID `UNKNOWN`.

**Per instruction, existing behaviour is preserved and documented rather than replaced.**
The new backend must (a) reproduce the fallback exactly for regression parity, **and**
(b) return an explicit `disease_profile_matched: bool` + `profile_used` field so the substitution
is visible instead of silent. This is a **blocking question for Phase 2** — see §14.

### 9.4 Other ambiguities

- **Size optimum disagreement** (80–120 vs 80–150 nm) between the two live scoring layers.
- `DiseaseFilModel` / `DiseaseFilEngine` — apparent typo for "Fit"; preserve the name to avoid
  breaking imports, alias if desired.
- `sessions.json` timeout uses timezone-aware UTC while `auth.py` uses naive `datetime.now()` —
  mixed timezone handling across the two session systems.

---

## 10. Security, reliability and deployment risks

### 10.1 Critical

| # | Risk | Evidence |
|---|---|---|
| C1 | **Forgeable session tokens** — `token_{username}_{unix_seconds}` | `streamlit_auth.py:73` |
| C2 | **Tokens in URL query strings** | `Login.py:170` + all pages |
| C3 | **21 plaintext session tokens on disk, not git-ignored** | `sessions.json` |
| C4 | **Default `admin`/`admin`, shown on the login page** | `db_init.py:49`, `Login.py:128` |
| C5 | **Hard-coded `<redacted — see ARCHIVE_NOTES.md>` in source** | `create_admin.py:31`, `set_admin_password.py:7` |
| C6 | **No rate limiting or lockout on login** | `auth.py:95` |
| C7 | **Headline score is a hard-coded constant; failure defaults to "89 / Good"** | `2_Run_Simulation.py:314-338` |
| C8 | **ML models never load; heuristics presented as ML output, disclosure collapsed** | §8.2 |

### 10.2 Repository hygiene

- **`sessions.json` and `users.json` are not git-ignored** — live tokens and user data.
  Add both to `.gitignore` **and** rotate the tokens.
- **`.venv_new/` is not ignored** (only `.venv/`, `venv/`, `env/`, `ENV/` are). Two such
  directories exist (root and `biotech-lab-main/`).
- `*.db` **is** ignored — good; `users.db` should stay out of git (safety rule 7).
- **`package-lock.json` is git-ignored (`.gitignore:73`)** — actively harmful for the new React
  frontend; lockfiles must be committed for reproducible Render builds. **Remove this line in Phase 5.**
- Stray files: `%F` (312 B), `git` (0 B), `~$…docx` × 2, `comprehensive_lnp_dataset - Copy.csv`,
  `- Copy (2).csv`.
- `README.md` is 20 bytes (`# nano_bio_studio_2`).

### 10.3 Reliability

- **`.streamlit/` is git-ignored**, so no theme/server config is version-controlled.
- Import-time side effects: `auth.py:88` (`init_db()`), `auth.py:171` (`_reset_admin_session()`).
- SQLite + `check_same_thread=False` across 40+ ad-hoc connections; no pooling, no transactions
  spanning operations, no retry. Will not survive concurrent web traffic.
- Broad `except Exception: pass` swallowing in `auth.py`, `db_init.py`, `pk_model.py:134`.
- The `UnicodeEncodeError` class of bug (fixed pre-audit) shows emoji `print()` under a cp1252
  pipe can kill a page; the backend must configure UTF-8 logging explicitly.
- Trial-sequence read-modify-write race (§6.4).

### 10.4 Render-specific risks

- **Ephemeral filesystem.** Every SQLite DB, `sessions.json`, `users.json`, generated PDFs, and
  `models_store/*.pkl` written at runtime **will be lost on redeploy/restart**. All persistent
  state must move to PostgreSQL or object storage.
- **No `$PORT` binding today** — Streamlit is launched on a fixed 8501.
- **Memory.** Optuna optimisation, scikit-learn training, matplotlib, and ReportLab in one process
  will exceed Render's free 512 MB tier. Long optimisation runs also risk request timeouts and
  belong in a background worker.
- **No health endpoint** other than Streamlit's own `/healthz`.
- **CORS** — not applicable today (single origin); required for a split frontend/backend.

---

## 11. Missing or incomplete functionality

- **`tabs/` (11 files, 60 KB) is dead code with a broken import.** `tabs/home.py:10` does
  `from viz.dial import show_circular_dial` — **no `viz/` package exists in the repository**.
  Nothing imports `tabs/` (grep: zero importers). Five files are 0 bytes
  (`cost.py`, `delivery.py`, `protocol.py`, `quiz.py`, `toxicity.py`). **[VERIFIED]**
  → Do not migrate. Move to `legacy_streamlit/`.
- **Empty stubs:** `ui/components/inputs.py`, `ui/components/tables.py`, `ui/__init__.py` (0 bytes).
- **`pages/About_AI_Co_Designer.py`** — "Feature Coming Soon".
- **`pages/10_ML_Training.py:320`** — "Comparison view coming soon...".
- **`ai_engine/simulator_adapter.py`** — `simulate_design_placeholder()`, explicitly a placeholder.
- **`models.py` / `persistence.py`** — complete SQLAlchemy layer, wired to nothing.
- **`nanobio_studio_backend/`** — `repositories/` and `services/` are empty; `alembic/versions/`
  contains **no migrations**.
- **No password-reset token flow** (§5.4).
- **No `researcher` role** (§5.2).
- **Launch scripts are all broken:**
  - `start.bat` → `streamlit run app.py`; **no `app.py` exists at root**. Creates `venv/`.
  - `start_streamlit.ps1` → activates `.\.venv\`; **does not exist** (actual: `.venv_new/`), then
    runs `biotech-lab-main/App.py` (the legacy monolith).
  - `LAUNCH.md` → references `d:\nano_bio-26_1` and a root `app.py`; both wrong.
  - Neither `.venv_new` has Streamlit installed; the app runs on **system** Python 3.14.
- **`docs/scoring_system.md` documents a formula the live app does not use** (§3.1).

### 11.1 Test coverage — effectively none

| File | pytest asserts | Style | Mutating |
|---|---:|---|---|
| `tests/test_scientific_report_generation.py` | 3 | pytest | no |
| `test_database.py` | 1 | `__main__` script | **yes (4)** |
| `test_db_insertion.py` | 0 | script | **yes (3)** |
| `test_delete_trial.py` | 0 | script | **yes (6)** |
| `test_encapsulation_fix.py` | 0 | script | no |
| `test_phase3_integration.py` | 0 | script | no |
| `test_sprint3.py` | 0 | script | no |
| `test_pdf_sprint3_integration.py` | 0 | script | no |
| `test_live_toxcast_api.py` | 1 | script (network) | no |

No `pytest.ini` / `conftest.py` / `pyproject.toml` at root. Most "tests" are print-based scripts;
several mutate real databases and would be unsafe to run in CI as-is.
**There is no regression baseline for any scientific calculation** — Phase 6 must create it from scratch.

---

## 12. Python dependencies missing from `requirements.txt` **[VERIFIED]**

AST scan of all root-application imports (excluding `biotech-lab-main`), resolved against
`requirements.txt`:

### Genuinely missing — used by the running application

| Package | pip name | Used by |
|---|---|---|
| `requests` | `requests` | `hybrid_toxcast_connector.py`, `live_data_orchestrator.py`, `test_live_toxcast_api.py` (4 files) |
| `joblib` | `joblib` | `components/ml_predictor.py` (model loading) |
| `docx` | `python-docx` | 6 report-generation scripts |

### Missing — needed by the existing backend / tooling

| Package | pip name | Used by |
|---|---|---|
| `fastapi` | `fastapi` | `nanobio_studio_backend` (6 files) |
| `uvicorn` | `uvicorn[standard]` | `nanobio_studio_backend/app/main.py` |
| `loguru` | `loguru` | `nanobio_studio_backend` (13 files) |
| `pytest` | `pytest` | test suites |

### Declared but unused

- **`PyJWT`** — `requirements.txt:12`; zero `import jwt` in the root app. (Will become genuinely
  needed if Phase 4 uses JWTs.)

### Notes

- `pydantic-settings` **is** correctly declared (`requirements.txt:11`).
- `scipy` is **not** used anywhere — the PK model is hand-rolled NumPy (§3.2). Do not add it as a
  convenience; adding a solver would change results.
- `requirements.txt` has no upper bounds and no lockfile. Given the NumPy 1.x/2.x shim in
  `pk_model.py:11`, **numerical reproducibility depends on pinned versions.** Phase 3 must pin exactly.
- No `runtime.txt` / `.python-version`; Render needs an explicit Python version.

---

## 13. Features that must be preserved

### 13.1 Tier 1 — scientific core (must be numerically identical)

1. **`core/scoring.py::compute_impact()`** — all 12 sub-scores, the re-normalisation at
   lines 167-170, and user weight overrides. **This is the production scorer.**
2. **`core/scoring.py::overall_score_from_impact()`**, `get_recommendations()`,
   `validate_parameter()`, `regulatory_checklist()`.
3. **`utils/pk_model.py`** — the **forward-Euler loop at `dt=0.1`** verbatim, all 4 release modes,
   all 9 PK parameters, and the nullable half-life.
4. **`utils/toxicity_model.py`** — all 7 risk factors with rationale strings.
5. **All six `engine/` modules** + `config/scoring_config.py` + `config/disease_profiles.py`
   (including the documented fallback).
6. **`models/scientific_assessment.py`** — evidence/confidence/limitation vocabulary.
7. **`ai_engine/`** — Optuna optimisation, Pareto front, sensitivity, seeding, audit records.
8. **The 19 predictor `predict_*()` functions** — extracted from their `display_*_widget()` twins.
9. **`data/` mapping tables** (6 modules) and `modules/disease_database.py`.
10. **`utils/design_scorer.py`** — even though only `modules/design.py` uses it, it is what the
    published documentation describes; preserve and reconcile.

### 13.2 Tier 2 — workflow and application features

Disease → design → simulation workflow; 23-field design schema with exact defaults; trial registry
and ID format; design save/version/history; all 5 export formats; protocol generator; tutorial
(6 exercises); admin panel; activity log/audit trail; ML training pages; 3D viewer; safety radar;
PK plots.

### 13.3 Tier 3 — must be preserved but *corrected and disclosed*

- **The heuristic fallback** (§8.2) — keep the fallback, but make disclosure prominent and
  machine-readable (`prediction_basis: "heuristic" | "trained_model"`).
- **Hard-coded 92/89/82 headline score** (§3.1 System 4) — must **not** be reproduced as a
  scientific output. Recommendation: compute it from `overall_score_from_impact()` and record the
  legacy constant separately for regression comparison. **Requires your decision** (§14).
- **`infer_missing_parameters()`** (§7) — keep the inference, return it as explicit assumptions.
- **Silent disease fallback** (§9.3) — preserve the value, add a visibility flag.

### 13.4 Do not migrate

`tabs/` (dead, broken import); empty `ui/components/*` stubs; `biotech-lab-main/` (legacy copy);
the 9 root `generate_*.py` documentation scripts (move to `tools/`); duplicate CSVs; stray files.

---

## 14. Recommended migration plan

### Guiding principle

Extract the Streamlit-free scientific code **first and unchanged**; it is already the
best-structured part of the repository. `engine/`, `config/`, `data/`, `models/`, `reports/`,
`ai_engine/`, `utils/pk_model.py`, and `utils/toxicity_model.py` import no Streamlit and can move
essentially verbatim. Only `core/scoring.py` (1 vestigial `import streamlit`), `utils/design_scorer.py`
(0 uses), and the 19 predictors need decoupling. **No `@st.cache*` decorators exist anywhere**, so
there are no caching semantics to preserve. (Two bare `st.cache_data.clear()` calls exist —
`pages/6_Trial_History.py:376` and `TRAINING_HISTORY_TAB_CORRECTED.py:13` — but with nothing cached
they are no-ops and become plain refresh actions in the new frontend.)

### Step 0 — Freeze the baseline (before any code moves)

1. Copy the current app to `legacy_streamlit/` (**copy, never move** — safety rule 8).
2. Add `sessions.json`, `users.json`, `.venv_new/` to `.gitignore`; **remove the
   `package-lock.json` line**. Rotate all 21 session tokens.
3. Pin every dependency exactly and add the 3 missing runtime packages (§12).
4. **Build the golden-vector harness now.** Sweep representative designs through
   `compute_impact`, `two_compartment_model`, `calculate_overall_safety_score`, and all six
   engines; serialise inputs → outputs to JSON. This is the only defence against silent numerical
   drift, and it must exist *before* refactoring.

### Step 1 — Backend skeleton

Adopt `nanobio_studio_backend/` as the base (it already has FastAPI, Alembic, `pydantic-settings`,
`loguru`, tests). Restructure to the Phase 2 layout, keeping its existing LNP ingestion/ML routes.

### Step 2 — Port the scientific core into `backend/app/scientific/`

Move the Streamlit-free modules verbatim. Run the golden vectors after each move; **zero tolerance
for numerical change** (exact equality for deterministic paths, documented tolerance only where
floating-point summation order genuinely differs).

### Step 3 — Decouple the coupled modules

Split each predictor into a pure `predict_*()` service and drop the `display_*_widget()`. Extract
the calculation paths out of `modules/{simulation,cost,toxicity,design}.py` (~90–99 `st.*` calls each —
these are the labour-intensive ones).

### Step 4 — Consolidate 7 SQLite DBs into one PostgreSQL schema

Base it on `models.py`'s existing ORM (§6.3). Resolve the `BLOB`/`TEXT` conflict explicitly.
Re-key `activity_log` on `user_id`. Replace the trial-sequence read-modify-write with a real
sequence. **Add reproducibility columns**: engine version, model version, input snapshot (JSONB),
weight overrides, `prediction_basis`, `disease_profile_matched`, `profile_used`, assumptions,
random seed, timestamps. Ship as the first Alembic migration.

### Step 5 — Auth rebuild (§5.3)

`secrets.token_urlsafe()` or signed JWT; httpOnly cookie or `Authorization` header — **never** the
URL; Argon2 (or keep bcrypt) with a raised minimum length; rate limiting on login/reset;
token-based password reset; preserve self-registration → `student`; preserve `admin`/`student`/`viewer`
(adding `researcher` is a **new feature — confirm before adding**). Remove the import-time
`_reset_admin_session()`. Never seed a default password.

### Step 6 — `users.db` → PostgreSQL migration utility

A standalone, **manually invoked** script (safety rule: not automatic, never committed with the DB).
1 user currently exists, so this is low-risk — but bcrypt hashes must transfer as-is so existing
passwords keep working.

### Step 7 — React + TypeScript frontend

Plotly specs bridge most cleanly (28 files already use Plotly). matplotlib figures (PK plot, safety
radar) must either be re-implemented client-side or served as backend-rendered PNGs — **recommend
re-implementing in Plotly** so the frontend stays interactive, while keeping the matplotlib path for
PDF export.

### Step 8 — Verification (Phase 6), then Render (Phase 7)

Golden-vector regression must be green before any feature is declared migrated.
Then `render.yaml`, `$PORT` binding, health checks, and the ephemeral-filesystem constraints (§10.4).

### Sequencing note

Steps 1–2 are low-risk and high-value; Step 3 is the bulk of the effort; Step 4 is the highest-risk
single change. **Step 0.4 (golden vectors) gates everything** — without it, no claim of scientific
equivalence in Phase 6 can be substantiated.

---

## Blocking questions for Phase 2

These change the work materially and are yours to decide:

1. **Disease taxonomy (§9.3).** The UI offers 19 disease/subtype combinations; the scientific
   engines support 2 and silently substitute HCC-S. Should the new backend (a) reproduce the
   fallback but expose it explicitly, (b) reject unmapped diseases, or (c) restrict the UI to
   HCC-S and PDAC-I? Preserving current behaviour = option (a) — my default absent direction.
2. **Headline score (§3.1 System 4).** The user-visible "Overall Score" is one of three hard-coded
   constants, and errors default to "89 / Good". Preserve as-is for parity, or replace with the
   real computed score? I recommend computing it and retaining the constant only as a regression
   reference.
3. **Which scoring system is canonical?** Live code uses System 1; published documentation
   describes System 2; the newest engines use System 3. I recommend System 1 as the migration
   baseline (it is what the app actually runs) with System 3 for the assessment layer — and
   correcting `docs/scoring_system.md`.
4. **`researcher` role** — genuinely new, or map to existing `student`/`viewer`?

---

## Appendix A — Files created or materially changed in Phase 1

| File | Change |
|---|---|
| `docs/CURRENT_APPLICATION_AUDIT.md` | **Created** — this document |
| `Login.py` (lines 11–19) | UTF-8 stdout guard, added during the pre-audit startup fix |
| `users.db` | Initialised (1 admin row) by the pre-audit `db_init` fix |
| `trial_registry.db` | Created by an audit probe, then **removed** to restore prior state |

No other application file was read-modified. No git operations were performed
(the directory is not a git repository).

## Appendix B — Verification commands used

```powershell
# Live schema (read-only)
python -c "import sqlite3; c=sqlite3.connect('file:users.db?mode=ro',uri=True); print([r for r in c.execute(\"SELECT sql FROM sqlite_master WHERE type='table'\")])"

# Disease fallback
python -c "import sys; sys.path.insert(0,'.'); from config.disease_profiles import get_disease_profile as g; print(g('Breast Cancer').disease_code)"

# ML model loading
python -c "import sys; sys.path.insert(0,'.'); from components.ml_predictor import MLPredictor; p=MLPredictor(); print(p.load_models())"

# Root vs biotech-lab-main divergence
Get-FileHash <root>\<file> -Algorithm MD5; Get-FileHash <bl>\<file> -Algorithm MD5
```
