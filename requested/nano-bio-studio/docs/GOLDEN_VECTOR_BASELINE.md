# Golden-Vector Scientific Baseline — Phase 2, Steps 0 and 1

**Created:** 2026-07-30 (Step 0) · **Updated:** 2026-07-30 (Step 1)
**Current baseline version:** `step1-2026-07-30`
**Archived Step 0 baseline:** `step0-2026-07-30` (immutable, never overwritten)
**Status:** Step 1 corrections applied. No architectural implementation has begun.

| Artefact | Path |
|---|---|
| Representative inputs | `tests/golden_vectors/inputs.py` |
| Capture harness | `tests/golden_vectors/capture.py` |
| Machine-readable baseline (current) | `tests/golden_vectors/baseline.json` |
| **Machine-readable baseline (Step 0, immutable)** | `tests/golden_vectors/baseline_step0_2026-07-30_legacy.json` |
| Regression tests | `tests/golden_vectors/test_golden_vectors.py` |
| **Step 1 correction tests** | `tests/test_step1_corrections.py` |
| Isolation fixtures | `tests/conftest.py` |
| Pytest config | `pytest.ini` |

> **Historical evidence is never overwritten.** The Step 0 baseline — capturing the
> legacy application's behaviour before any correction — is archived verbatim at
> `baseline_step0_2026-07-30_legacy.json`. Every reclassification between the two
> is explained in §6.

---

## 1. Results

### Step 1 (current)

```
420 vectors captured    366 intended    54 known_defect    5 raised
504 tests               504 passed      0 failed           ~3.0 s
```

| Run | Command | Result |
|---|---|---|
| Complete suite | `python -m pytest tests -q` | **504 passed** |
| Must-hold contract | `python -m pytest tests -q -m "not known_defect"` | **445 passed**, 59 deselected |
| Known-defect suite | `python -m pytest tests -q -m "known_defect"` | **59 passed**, 445 deselected |
| Leak-detector self-tests | `python -m pytest tests -q -k "Isolation or leak or snapshot"` | **4 passed** |
| Step 1 corrections | `python -m pytest tests/test_step1_corrections.py -q` | **61 passed** |

**Zero numerical drift.** A field-level diff of every Step 0 vector against Step 1
found **45 leaf fields added, 0 removed, and 0 values changed** — including 0
numeric changes. Every difference is either an additive provenance field or a
`raised → ok` status transition where a defect was corrected.

### Step 0 (archived, for comparison)

```
375 vectors captured    304 intended    71 known_defect    14 raised
397 tests               397 passed      0 failed
```

Coverage by section (all captured cleanly, zero capture errors):

| Section | Vectors | Notes |
|---|---:|---|
| `core_scoring` | 171 | `compute_impact` × 40 designs, 5 weight sets, 4 error paths, `overall_score_from_impact`, `get_recommendations`, `regulatory_checklist`, `validate_parameter` |
| `toxicity_model` | 44 | 7 risk functions × boundary cases + `calculate_overall_safety_score` × 5 designs |
| `engines` | 72 | 6 designs × mechanistic (7 methods), safety, disease-fit, manufacturing, regulatory, confidence |
| `pk_model` | 19 | 7 parameter sets × (`two_compartment_model`, `calculate_pk_parameters`) + 5 release modes |
| `disease_profiles` | 17 | 2 supported + 14 unsupported (defect) + `list_supported_diseases` |
| `ml_predictor` | 17 | heuristic fallback, all defect-classified |
| `legacy_headline_score` | 10 | the 92/89/82 buckets + the exception path |
| `trial_registry` | 8 | isolated temp DB; 3 mapped + 5 unmapped subtypes |
| `design_scorer` | 4 | secondary/legacy scorer (DECISION 3C) |
| `import_side_effects` | 3 | 2 defects + 1 resolved by containment |
| `engines_unsupported_disease` | 6 | the DECISION-1 blocking case |
| `report_generator` | 2 | blocked by DEFECT-D8 |
| `mock_ai_codesigner` | 1 | hard-coded "optimisation" output |
| `unreachable_modules` | 1 | `ai_engine` import failure |

---

## 2. What "intended" and "known_defect" mean here

This is the core of the deliverable, per Phase 2 item 4/5.

**`intended` (304 vectors) — the migration contract.**
These are the scientific results the new FastAPI backend **must** reproduce. Strict
equality, no tolerance. A failure means numerical behaviour changed and must be
explained before any feature is called migrated.

**`known_defect` (71 vectors) — recorded, never endorsed.**
These pin current *wrong* behaviour so its removal is **detectable**. They are
explicitly **not** target behaviour. They live in `TestKnownDefects`, marked
`known_defect`, and are excluded from the contract run.

> **A failure in `TestKnownDefects` is the expected and desired outcome** of
> implementing DECISION 1 or DECISION 2. When one fails because the defect was
> fixed, retire the vector deliberately and record the retirement in §6 below.

This already happened once during Step 0 — see §6.

### Numerical precision and determinism

* Floats are serialised via `json`, which uses `repr()` and round-trips exactly.
  Comparison is **exact equality**, not approximate.
* NumPy arrays are stored as `{shape, dtype, length, sha256, samples}`. The SHA-256
  covers every element at full `repr` precision, so a single changed value in a
  481-point PK curve is detected; the samples exist for human readability.
* Determinism was verified, not assumed: `compute_impact` and
  `two_compartment_model` are asserted identical across repeated runs.
* **Exactly two wall-clock reads exist** in the captured surface and both are
  normalised to a sentinel:
  `datetime.now()` at `reports/scientific_report_generator.py:148` and
  `pd.Timestamp.now()` at `components/ml_predictor.py:412`. The second is easy to
  miss — a grep for `datetime.now` does not find it.
* No `random`, `uuid`, or seeded stochastic code exists in the captured surface.
  (`ai_engine`'s Optuna optimiser is stochastic but is un-importable — DEFECT-D7.)

### Database isolation

No test reads, writes, creates or deletes a real application database.

1. `modules.trial_registry.DB_PATH` is monkeypatched to a `tmp_path` directory.
2. `tests/conftest.py` snapshots the SHA-256 of all seven possible SQLite files at
   **conftest import time** — not in a lazily-evaluated fixture.
3. `test_no_real_database_was_touched` compares against that snapshot.
4. `test_leak_detector_actually_detects_a_leak` is a **self-test for the guard**,
   proving it flags both creation and mutation.

Item 2 and item 4 exist because the first version of this harness had a lazily
evaluated snapshot that was taken *after* a leak occurred and **reported a false
pass**. The leak was real: `import design_persistence` wrote a 36 KB `nano_bio.db`
into the repository root (DEFECT-D11). It was removed (0 rows) and the fixture no
longer imports that module at all.

`pytest.ini` sets `testpaths = tests`, deliberately **excluding** the 8 legacy
root-level `test_*.py` scripts: three mutate real databases
(`test_db_insertion.py`, `test_delete_trial.py`, `test_database.py`) and one makes
live network calls (`test_live_toxcast_api.py`). They remain on disk, untouched.

---

## 3. Defects found and classified

DEFECT-D1 – D7 were identified in the Phase 1 audit. **D8 – D11 are new, found by
executing the code** — which is precisely what Step 0 was for. The audit read
signatures and structure; it could not have found these.

| ID | Severity | Defect | Step 1 status |
|---|---|---|---|
| **D8** | **Critical — feature dead** | `RegulatoryEngine` raises `TypeError` unconditionally | ✅ **CORRECTED** (DECISION 5) |
| **D9** | Medium | Inconsistent `None` handling across scoring functions | ✅ **CORRECTED** |
| **D10** | Medium | Disease-fit can never exceed 68.33; branch unreachable | ⚠️ **PARTIALLY** — field name fixed, verdict withheld (DECISION 6) |
| **D11** | High | Modules create real databases as an import side effect | ✅ **CORRECTED** |
| D6 | Critical | "AI Co-Designer" returns a hard-coded mock DataFrame | ✅ **QUARANTINED** (DECISION 7) |
| D1 | Critical | Silent HCC-S disease substitution | ⏳ open — DECISION 1, later step |
| D2 / D3 | Critical | Hard-coded headline score; favourable score on failure | ⏳ open — DECISION 2, awaiting §8 review |
| D4 | Medium | Real UI subtypes filed as trial ID `UNKNOWN` | ⏳ open |
| D5 | High | No ML model loads; heuristics labelled as ML output | ⏳ open |
| D7 | High | `ai_engine` package is un-importable | ⏳ open — repair not authorised in Step 1 |

### Step 1 corrections in detail

**D8 → corrected (DECISION 5).** `manufacturing_complexity` is now an explicit
integer count in 0–2 computed over normalised inputs
(`engine/input_normalization.py`), replacing `bool + str`. A canonical null
representation (`normalise_ligand` → `None`) means the truthy string `"None"` can
never again be mistaken for a real ligand. `RegulatoryEngine.CALCULATION_VERSION`
= `2.0.0`. Described only as a *"Rule-based manufacturing complexity indicator"*.

**D9 → corrected.** `compute_impact`, `get_recommendations` and
`regulatory_checklist` now share one null contract (`_optional_float` /
`_optional_value`): an absent key and a present-but-`None` value are equivalent.
Required keys still raise `KeyError`. **The defect was broader than first
reported**: `compute_impact` itself was `None`-unsafe for seven keys, and a
present-but-`None` `Ligand` was treated as a *present* ligand — the same sentinel
hazard as D8. Verified by 21 optional keys × 3 functions = 63 checks.

**D10 → partially corrected (DECISION 6).** The field-name error is fixed in **all
five** live occurrences (only one was originally reported). The favourable verdict
remains **disabled**; scores were not rescaled and the threshold was not lowered.
Callers receive `verdict_available: false` and `verdict_status:
"calibration_required"`, while fit and barrier scores continue to be returned.

**D11 → corrected.** All module-level initialisation calls removed. `auth.py` was
calling `init_db()` **twice** at module scope (lines 88 and 1420). Initialisation
is now explicit (`auth.initialize_database()`, called from `Login.py`) plus an
idempotent lazy guard on 32 DB-touching functions.

**D6 → quarantined (DECISION 7).** Detailed in §3.1 below.

### 3.1 The AI Co-Designer was worse than reported

The Step 0 audit identified the five fabricated candidate scores. Quarantining the
page revealed that **all four tabs** were fabricated:

* mock parameter distributions and a fabricated Pareto front;
* fabricated headline metrics (`Best Overall Score 94.2/100`,
  `Feasible Designs 387/500`, `+5.1 vs baseline`);
* fabricated feature-importance and parameter-sensitivity curves;
* **a fabricated audit trail**, with a hard-coded timestamp
  (`2026-03-17 15:30:45 UTC`) and fabricated constraint-violation counts.

The fabricated audit trail is the most serious: it presented governance evidence
for an optimisation run that never happened. Showing a "not operational" banner on
one tab while another still displayed "Best Overall Score 94.2/100" would have
been incoherent, so the whole page was replaced with a labelled non-operational
status. The original is preserved verbatim, banner-labelled as synthetic
demonstration data, at `legacy_streamlit/quarantined/7_AI_Co_Designer.legacy.py` —
outside `pages/`, so Streamlit cannot route to it.

### 3.2 Six masked bugs unmasked by the D8 fix

Correcting D8 exposed bugs that had been unreachable because the `TypeError`
crashed first — exactly the cascade predicted in Step 0. All were mechanical
wrong-name or wrong-object references, fixed without inventing scientific content:

| Location | Bug |
|---|---|
| `engine/mechanistic_engine.py:86`, `:369` | `disease_profile.name` → `.disease_name` |
| `engine/regulatory_engine.py:487`, `:596` | `disease_profile.name` → `.disease_name` |
| `reports/scientific_report_generator.py:186` | `full_report.disease_profile.name` → `.disease_name` |
| `reports/scientific_report_generator.py:127` | assumed all six engine results expose `.basis`; only `PredictionBasis` declares it, so four modules raised `AttributeError` |
| `reports/scientific_report_generator.py:286` | `regulatory_assessment.gmp_pathway_readiness` → `manufacturability_assessment.gmp_pathway_readiness` (field belongs to a different dataclass) |

For the `.basis` case **no basis was invented**: the four modules that declare none
now report the absence explicitly. Giving them a structured prediction basis is
open question Q8 in `docs/SCORING_CANONICALIZATION.md`.

### DEFECT-D8 — `RegulatoryEngine` is completely non-functional

`engine/regulatory_engine.py:224`:

```python
manufacturing_complexity = design_inputs.peg_surface_coating + design_inputs.targeting_ligand
#                          ^ bool                              ^ str
```

`bool + str` raises `TypeError` **for every input, unconditionally**. Verified
against all 6 representative designs and both supported diseases.

Consequences, because the engines chain:

* `RegulatoryEngine.assess_regulatory_position()` — **always fails**
* `ConfidenceEngine.calculate_confidence_profile()` — **can never run** (it consumes
  the regulatory result). No baseline exists for it.
* `ScientificReportGenerator.generate_full_report()` — **always fails**. The full
  scientific report cannot be produced in the legacy application at all.

So **2 of the 6 assessment engines and the entire scientific report generator are
dead code in the running application.** My Phase 1 audit listed all six engines
under "must preserve, directly portable" — that assessment was based on reading
structure. Two of them have never executed successfully.

**I have not guessed a fix.** The intended semantics are ambiguous — see §5, Q1.

### DEFECT-D10 — disease-fit has a ceiling below its own threshold

`regulatory_engine.py:216` reads `disease_profile.name`, but `DiseaseProfile` has
no `name` field (it is `disease_name`), so that branch would raise `AttributeError`.
It is guarded by `if disease_fit.overall_fit_score > 70`.

A sweep of **1,792 parameter combinations** across both supported diseases found the
maximum achievable `overall_fit_score` to be **68.33** — the threshold is never
crossed. Two consequences:

1. The `AttributeError` is a **masked latent bug**: fix the fit scoring and a second
   crash appears.
2. More importantly, the higher-confidence `"predicted"` regulatory language level
   is **unreachable**. The disease-fit engine can never return a favourable verdict
   for any design, on either supported disease. Whether that ceiling is intentional
   conservatism or a scoring bug is unresolved — see §5, Q2.

### DEFECT-D9 — inconsistent `None` handling within one module

`compute_impact()` guards optional numerics with `x if x is not None else default`.
`get_recommendations()` uses `float(design.get(key, default))`, which raises
`TypeError` when the key is **present but `None`**. The same design dict is accepted
by one function and rejected by the other. Pinned by
`test_d9_get_recommendations_rejects_none_that_compute_impact_accepts`.

### DEFECT-D11 — import-time database writes

| Location | Effect |
|---|---|
| `auth.py:88` and `auth.py:1420` | `init_db()` at module scope — **called twice** |
| `design_persistence.py:568` | `init_design_db()` — writes ~36 KB `nano_bio.db` on bare import |
| ~~`auth.py:171`~~ | `_reset_admin_session()` — **RESOLVED**, see §6 |

Monkeypatching cannot mitigate these: the write happens during the `import`
statement. Database initialisation must become an explicit step in the FastAPI
lifespan.

### DEFECT-D6 — the "AI Co-Designer" is a hard-coded table

`pages/7_AI_Co_Designer.py:364-373` renders a literal DataFrame — the code comment
says "Mock candidate designs":

```python
"Score":    [94.2, 91.5, 89.8, 87.3, 84.9],
"Delivery": [92, 89, 87, 85, 82],
"Safety":   [96, 93, 92, 90, 88],
```

Only the `Material` column varies, via a dict lookup on disease/scenario. No
optimisation runs — the real optimiser (`ai_engine`) is un-importable (D7), and
`optuna` is a declared dependency reachable by nothing (its only two importers are
`ai_engine/optimizer.py` and the dead `tabs/optimize.py`). This is the same class of
problem as DECISION 2 and arguably worse, because the fabricated numbers are
presented with a "why these designs were suggested" rationale.

---

## 4. What is *not* covered, and why

Honest gaps in the baseline:

| Not covered | Reason |
|---|---|
| `ConfidenceEngine` | **Blocked by D8.** Cannot execute. Recorded as `BLOCKED.*` vectors with no output. |
| `ScientificReportGenerator` output | **Blocked by D8.** Only the exception is captured. |
| `ai_engine/*` (14 files) | **Blocked by D7.** Un-importable: Optuna optimiser, Pareto front, sensitivity, audit records. |
| The 19 `components/*_predictor.py` `predict_*()` functions | Deferred to Step 3, when they are split from their `display_*_widget()` twins. They are Streamlit-coupled and each needs individual input analysis. **This is the largest remaining coverage gap.** |
| `modules/{simulation,cost,toxicity,design}.py` | 90–99 `st.*` calls each; calculation paths are not yet separable. Deferred to Step 3. |
| `modules/protocol.py` (39 KB) | Text generation, not numerics. Deferred; needs string-output vectors. |
| `tabs/*` | Dead code with a broken `viz/` import. Will not be migrated. |
| `utils/pdf_generator.py`, `professional_report_generator.py` | Binary PDF output; needs a structural rather than byte-exact comparison strategy. |
| Auth / DB / RBAC | Not scientific. Covered separately by Phase 4. |

**Consequence:** the 304 intended vectors are a solid contract for the *scientific
core* (scoring, PK, toxicity, 4 of 6 engines, disease profiles). They are **not**
full coverage of the application. Step 3 must extend this baseline before the
predictor components are refactored.

---

## 5. Unresolved ambiguities — decisions I need from you

Per the instruction not to invent scientific behaviour, these are stopped rather
than guessed.

**Q1 — DEFECT-D8: what should `manufacturing_complexity` mean?**
`bool + str` cannot have been intended. Two readings fit the surrounding code
(`if manufacturing_complexity:` selecting between "requires development" at
confidence 0.65 and "feasible using standard techniques" at 0.85):

- **(a) Truthiness:** `peg_surface_coating or targeting_ligand != "None"` — "PEG or
  a ligand implies added process complexity". Note that with `or`, a bare
  untargeted particle takes the *simpler* branch.
- **(b) Complexity count:** `int(peg_surface_coating) + (targeting_ligand != "None")`
  — a 0–2 score, allowing a future middle tier.

These give different regulatory language and different confidence values for the
same design. I recommend **(a)** as the minimal reading of the original `if`, but
this is a scientific-content decision and I will not choose it unilaterally.
**Until you decide, `RegulatoryEngine` and `ConfidenceEngine` cannot be migrated,
and the scientific report generator stays non-functional.**

**Q2 — DEFECT-D10: is the 68.33 disease-fit ceiling intended?**
No design on either supported disease can be rated a good fit (>70). Is that
deliberate conservatism (in which case the `>70` branch and its
`disease_profile.name` bug should be deleted), or is `_calculate_overall_fit()`
under-scoring (in which case fixing it exposes the `AttributeError`)?

**Q3 — DEFECT-D6: what should the AI Co-Designer do in the new platform?**
Options: (i) repair `ai_engine` (fix the `nanobio_studio.` import prefix) and run
real Optuna optimisation; (ii) omit the feature until the optimiser is reviewed;
(iii) keep the page but label it explicitly as a non-functional demonstration.
It cannot be migrated as-is under DECISION 2.

**Q4 — scoring canonicalisation document.**
DECISION 2 requires `docs/SCORING_CANONICALIZATION.md` **before** implementing the
replacement Overall Score. That is the natural next deliverable, but it is
implementation-adjacent, so I have not written it inside Step 0. Confirm you want it
next and I will derive the proposed formula from `compute_impact()` +
`overall_score_from_impact()` and map every component and weight, with no invented
coefficients.

---

## 6. Vector retirement log

Per §2, a defect vector that fails because the defect was fixed must be retired
deliberately and recorded here.

| Date | Vector | Change |
|---|---|---|
| 2026-07-30 | `DEFECT.import_side_effect::auth.py::_reset_admin_session_at_import` | **Retired → reclassified `intended`** as `RESOLVED.import_side_effect::...`. The security containment removed the module-level `_reset_admin_session()` call, so the test failed (correctly). The vector now asserts the call is **absent**, making a re-introduction a contract failure. Verified: `import auth` no longer mutates the admin `session_start`/`last_activity`. |

### Step 1 reclassifications (2026-07-30)

Pre-correction evidence for every row is preserved in
`baseline_step0_2026-07-30_legacy.json`.

| Vector(s) | From → To | Why |
|---|---|---|
| `DEFECT.regulatory.assess_regulatory_position::*` (6) | `known_defect`, `raised` → **`regulatory.*`, `intended`, `ok`** | D8 corrected. The engine no longer raises; it returns a `RegulatoryAssessment` with `calculation_version`, `manufacturing_complexity` and verdict status. |
| `BLOCKED.confidence.calculate_confidence_profile::*` (6) | `known_defect`, no output → **`confidence.*`, `intended`, `ok`** | Its `RegulatoryAssessment` input can now be produced, so the engine is exercised for the first time. These are **new baselines**, not changed ones — no prior output existed. |
| `DEFECT.report.generate_full_report::*` (2) | `known_defect`, `raised` → **`report.*`, `intended`, `ok`** | The five-engine chain completes. Timestamps normalised for determinism. |
| `core.get_recommendations::none_valued_optionals` | `known_defect`, `raised` → **`intended`, `ok`** | D9 corrected; the input no longer raises. |
| `DEFECT.import_side_effect::auth.py::init_db_at_import` | `known_defect` → **`RESOLVED.*`, `intended`** | D11 corrected. Now asserts absence; also records that the call had appeared **twice**. |
| `DEFECT.import_side_effect::design_persistence.py::init_design_db_at_import` | `known_defect` → **`RESOLVED.*`, `intended`** | D11 corrected. Now asserts absence. |
| **44 new** `D5.*`, `D6.*`, `D9.*` vectors | — → **`intended`** | New coverage for the Step 1 corrections: all four PEG/ligand combinations, sentinel normalisation, regulatory provenance, verdict status, and the null-contract matrix. |
| **1 new** `D7.ai_codesigner_quarantine` | — → **`intended`** | Asserts the fabricated values are absent from the executable page and the original is preserved outside `pages/`. |

### Retired tests (2026-07-30, Step 1)

Two assertions in `TestKnownDefects` failed because the defects they pinned were
fixed — the designed signal. Both are retired in place with an explanatory comment
rather than deleted, and replaced by stronger coverage:

| Retired test | Replacement |
|---|---|
| `test_d8_regulatory_engine_always_raises` | `tests/test_step1_corrections.py::TestDecision5ManufacturingComplexity` and `::TestRestoredExecution` |
| `test_d9_get_recommendations_rejects_none_that_compute_impact_accepts` | `::TestDefectD9NullContract` (21 keys × 3 functions, vs the single input the old test covered) |

The check was also made line-number independent (it now searches for a
column-0 call rather than anchoring to a line), because the containment edit
shifted line numbers. That change surfaced the previously unnoticed **second**
`init_db()` call at `auth.py:1420`.

---

## 7. Regenerating and using the baseline

```powershell
# From the repository root, with the project interpreter active.

# Re-capture the baseline (overwrites baseline.json -- review the diff!)
python -m tests.golden_vectors.capture

# The contract that must hold through migration
python -m pytest tests/golden_vectors -q -m "not known_defect"

# Full suite, including the pinned defects
python -m pytest tests/golden_vectors -q

# Inspect one vector
python -c "import json; b=json.load(open('tests/golden_vectors/baseline.json', encoding='utf-8')); print(json.dumps([v for v in b['vectors'] if v['id']=='core.compute_impact::app_default'][0], indent=2))"
```

**Never regenerate the baseline to make a failing test pass.** A diff in
`baseline.json` is the signal the harness exists to produce. Investigate first;
regenerate only when the change is understood, intended, and recorded in §6.

### Capture environment

| | |
|---|---|
| Python | 3.14.0 |
| NumPy | 2.3.4 |
| pandas | 2.3.4 |
| scikit-learn | 1.7.2 |
| Platform | Windows-11 |

`utils/pk_model.py:11-14` switches between `np.trapezoid` (NumPy ≥ 2) and
`np.trapz`. This baseline was captured on the **`trapezoid`** path. Pinning NumPy in
the backend requirements is therefore a **numerical-reproducibility requirement**,
not housekeeping.

---

## 8. Guard rails asserted by the suite

Beyond diffing 375 vectors, the suite asserts these explicitly so a future change
cannot quietly violate them:

| Test | Guarantee |
|---|---|
| `test_pk_euler_step_is_unchanged` | PK default `dt` is still `0.1`, `duration` `48.0`, and **no `scipy` appears in the solver source**. Enforces the "do not change the hand-rolled PK solver" direction. |
| `test_compute_impact_is_deterministic` | 5 identical runs. |
| `test_pk_model_is_deterministic` | Arrays bit-identical across runs. |
| `test_canonical_weight_set_is_twelve_components` | All 12 DECISION-3A weight components still present. |
| `test_weights_are_renormalised_when_they_do_not_sum_to_one` | Doubling every weight must not change the result. |
| `test_missing_required_keys_raise_rather_than_silently_default` | `Size`/`Charge`/`Encapsulation` absence raises `KeyError` — fails loudly, never silently defaults. |
| `test_compute_impact_output_shape` | Delivery 0–100, Toxicity 0–10, Cost 0–100. |
| `test_no_real_database_was_touched` | No real DB created or modified. |
| `test_leak_detector_actually_detects_a_leak` | The guard above actually works. |
| `test_snapshot_is_taken_at_import_time_not_lazily` | Prevents regressing to the false-pass fixture. |
| `test_vector_set_is_stable` | No vector silently disappears (which would hide a deleted function). |

---

## 9. Security containment applied alongside Step 0

Small, documented, tested. Recorded in full in
`docs/SECURITY_CONTAINMENT_2026-07-30.md`.

The app was restarted and verified after the changes: `authenticate()` still
returns `(True, 'admin')` for valid credentials and `(False, None)` for invalid
ones, `Login.py` executes end-to-end with exit code 0, the server answers
`/healthz` with 200, and all 397 tests pass.
