# PK Migration Slice — Two-Compartment Pharmacokinetic Model → FastAPI → React

**Created:** 2026-07-31
**Status:** Implemented and verified.
**Scope:** One scientific engine, one endpoint, two UI surfaces (Step 3 and the
Results page). This is **not** the full simulation module.

> **Scientific positioning.** Every value this slice produces is a computational
> research-planning result. It is not experimentally validated, not clinically
> validated, not a regulatory approval prediction, not a dosing recommendation,
> not a diagnosis, and not a substitute for an in-vivo pharmacokinetic study.

---

## 1. What was identified as "the" legacy PK implementation

Two things in the repository are called a "simulation". Only one is
pharmacokinetics, and only that one was migrated.

| Candidate | What it actually is | Migrated? |
|---|---|---|
| **`utils/pk_model.py`** | A genuine two-compartment PK model: depot → central → peripheral, first-order transfers, explicit forward-Euler integration, plus derived-parameter and release-profile functions. Consumed by the legacy Streamlit page `modules/simulation.py` ("Delivery Simulation (PK/PD)"). | **Yes** |
| `biotech-lab-main/app.py` "📈 Delivery" block | Not pharmacokinetics. It multiplies the design Delivery score by hard-coded environment factors (blood flow 0.8/1.0/1.2, tissue 0.4–1.3, …). There is no time axis, no compartment and no rate constant. | No — and it is not PK |
| `pages/2_Run_Simulation.py` | Calls `core.scoring.compute_impact` and the ML predictor. Never imports `pk_model`. | Already covered by the scoring slice |
| `engine/mechanistic_engine.py` | Mentions "clearance" in prose rationales for a *toxicity* heuristic. Computes no kinetics. | No (out of scope for this slice) |

`utils/pk_model.py` in the repository root and its copy in `biotech-lab-main/`
are byte-identical, so there is a single implementation to migrate.

### Inputs the legacy implementation consumes

| Input | Legacy source | Legacy range | Legacy default |
|---|---|---|---|
| `dose` (mg/kg) | `modules/design.py:179` | 0.1 – 100 | 5.0 / 10.0 depending on preset |
| `kabs` (h⁻¹) | `modules/design.py:197` | 0.01 – 5.0 | 0.5 |
| `kel` (h⁻¹) | `modules/design.py:207` | 0.001 – 2.0 | 0.1 |
| `k12` (h⁻¹) | `modules/design.py:217` | 0.01 – 2.0 | 0.3 |
| `k21` (h⁻¹) | `modules/design.py:227` | 0.01 – 2.0 | 0.2 |
| `duration` (h) | `modules/simulation.py:263` | 12 – 168 | 48 |
| `dt` (h) | `modules/simulation.py:273` | {0.05, 0.1, 0.25, 0.5, 1.0} | 0.1 |

**That is the complete input list.** The model consumes no particle size, no
charge, no coating, no ligand, no disease and no therapeutic agent. The legacy
Streamlit page displayed the formulation next to the curve, but never fed it in.

---

## 2. Architecture and request flow

```
┌──────────────────────────────────┐
│ React 18 + TypeScript (Vite)     │
│  pages/workflow/Step3Review.tsx  │  ← PK inputs collected here
│  pages/workflow/ResultsStage.tsx │  ← separate PK card
│  pages/workflow/PKPanel.tsx      │  ← display, zero derivation
│  charts/ConcentrationTimeChart   │  ← plots returned arrays only
└──────────────┬───────────────────┘
               │  fetch POST (CORS allow-list, HttpOnly session cookie)
               ▼
┌──────────────────────────────────┐
│ FastAPI                          │
│  app/api/routes/pk.py            │  ← transport only, zero science
│  app/schemas/pk_simulation.py    │  ← Pydantic validation
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│ Adapter (service layer)          │
│  app/services/pk_simulation.py   │  ← provenance + failure handling only
└──────────────┬───────────────────┘
               ▼
┌──────────────────────────────────┐
│ LEGACY SCIENCE                   │
│  utils/pk_model.py               │  ← called VERBATIM
│    two_compartment_model()       │
│    calculate_pk_parameters()     │
└──────────────────────────────────┘
```

**The legacy functions are imported and called verbatim.** No equation,
constant, rate law, integration step or derived quantity is reimplemented
anywhere in the backend. Verified by equivalence tests that compare API output
against a direct call for all seven golden-vector parameter sets and require
**bit-exact** match (`repr()` comparison, including every point of the curve).

---

## 3. Separating the calculation from the Streamlit stack

`utils/pk_model.py` never imported Streamlit. It did import
`matplotlib.pyplot` at module scope, purely for `create_pk_plot()`, which meant
any consumer of the *calculation* also had to load the plotting stack.

**Change made:** that import moved inside `create_pk_plot()`, and the return
annotation became a string with a `TYPE_CHECKING` guard.

**Change NOT made:** nothing else. No equation, constant, default, integration
scheme, signature or return value was touched. The golden-vector baseline for
this module is unchanged and still passes, which is the proof.

The FastAPI process now imports the PK model with NumPy alone. A subprocess test
(`test_pk_service_imports_without_streamlit_or_matplotlib`) asserts this, and a
second test confirms `create_pk_plot()` still works for the legacy Streamlit
page.

---

## 4. Scientific equations — unchanged, and why

From `docs/CURRENT_APPLICATION_AUDIT.md` §3.2:

```
dC_depot  = -kabs*C_depot
dC_plasma =  kabs*C_depot - kel*C_plasma - k12*C_plasma + k21*C_tissue
dC_tissue =  k12*C_plasma - k21*C_tissue
```

integrated by **explicit forward Euler at fixed `dt`**.

> **The Euler scheme at `dt = 0.1` IS the model's numerical identity.**
> Substituting `scipy.integrate.solve_ivp` or any adaptive solver changes the
> results. It was not substituted.

Nothing was rewritten, recalibrated or simplified, so **no scientific approval
was required and none is being requested**. Two guards enforce this:

* `test_pk_euler_step_is_unchanged` (pre-existing) — default `dt`, default
  `duration`, and no `scipy` in the solver source;
* `test_the_solver_source_is_unchanged_by_the_decoupling` (new) — the four
  balance terms are still literally present in the source.

### Changes that would need approval, and are therefore not here

| Not done | Why it would need sign-off |
|---|---|
| Replacing Euler with an adaptive solver | Changes every number |
| Changing the default `dt` or `duration` | Changes every number |
| Deriving clearance as Dose/AUC | Introduces a quantity the model never produced (§6) |
| Extrapolating AUC to infinity | New calculation, new assumption |
| Estimating a half-life when the curve never halves | Replaces an honest null with a guess |
| Predicting rate constants from formulation parameters | Entirely new science |

---

## 5. Endpoint contract

### `POST /api/v1/pk/simulate`

Authenticated (HttpOnly session cookie), same as `/api/v1/design/score`.

**Required** — never defaulted; omitting one is a 422:

| Field | Type | Bounds (mirror the legacy widgets) |
|---|---|---|
| `dose_mg_kg` | float | 0.1 – 100 |
| `kabs_per_h` | float | 0.01 – 5.0 |
| `kel_per_h` | float | 0.001 – 2.0 |
| `k12_per_h` | float | 0.01 – 2.0 |
| `k21_per_h` | float | 0.01 – 2.0 |

**Optional** — numerical window settings, not properties of the system. Omitted,
the legacy documented defaults apply and the response says so in `warnings`:

| Field | Bounds | Default |
|---|---|---|
| `duration_h` | 12 – 168 | 48 |
| `time_step_h` | one of 0.05, 0.1, 0.25, 0.5, 1.0 | 0.1 |

Unknown fields are **rejected** (`extra="forbid"`). In particular a `disease`
field is refused rather than ignored, so the API can never appear to consume a
therapeutic context it does not use.

### Success — 200

```jsonc
{
  "concentration_time": {
    "time_h": [0, 0.1, …],            // 481 points at the defaults
    "central_plasma": [0, 0, 0.015, …],
    "peripheral_tissue": [0, 0, 0, …],
    "point_count": 481,
    "concentration_unit": "arbitrary units (dose-scaled amount)",
    "time_unit": "hours"
  },
  "pk_parameters": {
    "peak_concentration_central": 1.4411129411755834,
    "peak_concentration_peripheral": 1.5287460434185478,
    "time_to_peak_central_h": 2.6,
    "time_to_peak_peripheral_h": 12.5,
    "auc_central": 18.92076869856752,
    "auc_peripheral": 56.83108645967397,
    "half_life_central_h": 5.200000000000001,   // nullable
    "tissue_accumulation_ratio": 3.0036351780980555,
    "vss_ratio": 1.0608093229469426
  },
  "calculation_version": "pk-two-compartment-adapter-0.1.0",
  "model_name": "two_compartment_depot_forward_euler",
  "normalized_inputs": { "dose": 3.0, "kabs": 0.5, …, "duration": 48.0, "dt": 0.1 },
  "warnings": [ … ],
  "assumptions": [ … ],
  "limitations": [ … ],
  "quantities_not_produced": [ { "quantity": "clearance", "reason": … }, … ],
  "prediction_basis": "mechanistic_compartmental_ode_forward_euler",
  "evidence_level": "structural_model_with_user_supplied_rate_constants",
  "validation_status": "not_experimentally_validated",
  "scientific_source": "utils.pk_model.two_compartment_model + utils.pk_model.calculate_pk_parameters"
}
```

### Failure — 400 / 422 / 500

```jsonc
{ "error": "calculation_failed", "message": "…", "detail": "…", "results_available": false }
```

**There is no curve, half-life or AUC on any failure path.** A failed
calculation never returns a number, favourable or otherwise. Enforced by tests
on the API, the service and the React client independently.

The shared `RequestValidationError` handler is now path-aware: `/api/v1/pk/*`
failures carry `results_available`, everything else keeps `score_available`, so
each endpoint's failure body matches its own success contract.

---

## 6. What the migrated engine produces — and what it does not

Requirement-by-requirement, honestly:

| Requested output | Produced? | Where it comes from |
|---|---|---|
| Concentration–time data | **Yes** | `two_compartment_model` returns `time`, `C_plasma`, `C_tissue` |
| Half-life | **Yes, nullable** | `t_half_plasma`; `None` when the curve never halves |
| AUC | **Yes** | `AUC_plasma` / `AUC_tissue`, trapezoidal, window-truncated |
| Peak concentration | **Yes** | `C_max_plasma` / `C_max_tissue`, with `T_max` |
| Calculation / model version | **Yes** | Assigned by the adapter (see Q-PK1) |
| Normalized inputs | **Yes** | Effective values including defaulted window settings |
| Assumptions | **Yes** | 9 statements, from the model's own structure |
| Warnings | **Yes** | Defaults applied, null half-life, non-default step, stiffness |
| Limitations | **Yes** | 10 statements, always returned |
| Validation status | **Yes** | `not_experimentally_validated` |
| **Clearance** | **NO** | **Not produced. See below.** |

### Why clearance is absent

The model carries **no volume-of-distribution term**. Its state variables are
dose-scaled amounts, not mass-per-volume concentrations. A clearance in
volume/time therefore cannot be read out of it, and computing one (e.g.
`Dose/AUC`) would be a new scientific quantity the legacy implementation never
produced.

Rather than omit it silently, the response carries a
`quantities_not_produced` list — `clearance`, `volume_of_distribution`,
`bioavailability`, `auc_extrapolated_to_infinity` — each with the reason. The
UI renders "Clearance — not produced — the model has no volume term" as a
first-class tile beside the values that do exist.

### A legacy labelling error that was not carried forward

`modules/simulation.py` labels the PDF report's PK table "ng/mL" while
`create_pk_plot` labels the same values "arbitrary units". The model has no
volume term, so **arbitrary units is correct and ng/mL is wrong**. The migrated
API reports `arbitrary units (dose-scaled amount)`, states the discrepancy in
its limitations, and a test asserts `ng/mL` never appears.

### Not migrated in this slice

`simulate_release_profile()` (4 release modes) is part of `utils/pk_model.py`
but is a drug-release model, not the PK simulation, and was not requested. It
remains untouched and still golden-vector covered. Disease-fit, toxicity, AI
optimisation and the other scientific engines were not touched.

---

## 7. Where it connects in the React workflow

### Step 3 — Review & Run Simulation

The PK inputs are collected **on Step 3**, not Step 2, because they are
simulation inputs rather than formulation properties — the same division the
legacy application made (`modules/simulation.py` gathered duration and time step
on the simulation page). **Step 2 is unchanged by this slice.**

Two deliberate differences from the legacy form:

1. **Nothing is pre-filled.** `modules/simulation.py::get_complete_design()`
   silently merged in `dose=10.0, kabs=0.5, kel=0.1, k12=0.3, k21=0.2` whenever
   a value was absent, so a user could run a "simulation" whose kinetics they
   never chose and never saw. Here every field starts empty.
2. **The model is not called until every required input is present and valid.**
   `pkInputsReady` gates the call. Step 3 states which of the two outcomes will
   happen, before the user runs anything.

The design score and the PK simulation are two independent calls with two
independent outcomes. A failure of one never suppresses or substitutes for the
other.

### Results page

Two separate cards, never merged:

| Card | Version shown | Source |
|---|---|---|
| Design impact score | `design-impact-adapter-0.1.0` | `core.scoring.compute_impact` |
| Pharmacokinetic simulation | `pk-two-compartment-adapter-0.1.0` | `utils.pk_model.*` |

The PK card carries six tabs — Profile (chart), Parameters, Data, Inputs,
Assumptions, Warnings — plus provenance and limitations.

* **The chart is drawn from the returned arrays alone.** No smoothing, no
  resampling, no interpolation, no extrapolation; the axes span the data's own
  range rather than rounded "nice" numbers.
* **Exact values sit alongside it.** The Data tab lists every returned point at
  full `String(value)` precision, so the chart is never the only way to read a
  number.
* **A null half-life renders as "not determined"**, with the reason, and does
  not suppress the rest of the profile.
* **No clinical interpretation.** The legacy page emitted prose such as
  "excellent targeting efficacy", "may need PEGylation" and "suitable for most
  therapeutic applications". None of it is reproduced — the model does not
  support those conclusions. A test asserts each phrase is absent.

### Therapeutic context

Disease, subtype and therapeutic agent stay visible on Step 3 and the Results
page for traceability, with an explicit statement on both:

> Neither calculation below takes a disease as input — the design impact score is
> computed from formulation parameters only, and the pharmacokinetic profile from
> the dose and rate constants only. **Neither result varies with this selection.**

### Honest empty state

When the PK inputs are incomplete, the Results page shows an explicit panel:

> The dose and the four first-order rate constants are required, and were not all
> supplied. The model was therefore not executed. **No concentration–time profile,
> half-life or AUC exists for this session**, and none is shown — substituting
> typical values would report kinetics you never specified.

No empty chart, no zeroed profile, no placeholder number.

---

## 8. Preserved unchanged

| Area | Status |
|---|---|
| Disease → design → review/run → results sequence | Unchanged |
| Authentication, HttpOnly cookie, roles, route guards | Unchanged |
| Navigation, sidebar groups, admin-only Administration | Unchanged (one status *summary* reworded, §9) |
| Saved-draft behaviour | Extended: PK inputs persist; pre-PK drafts still load |
| Scientific disclosures on every surface | Unchanged, plus PK-specific ones |
| Canonical design-impact score | **Untouched.** Still `87.52475247524752` for the walkthrough design |
| Step 2 design-parameter form | Unchanged |
| `core/scoring.py` | Not opened |

### Backward compatibility of drafts

A draft saved before this slice has no `pk` key. `hydrate()` fills it with
blanks, so the draft loads normally and the simulation stays un-runnable until
the user supplies real values — an old draft can never appear to carry kinetics
it never had. A test covers exactly this.

---

## 9. Files created and changed

### Created

| File | Purpose |
|---|---|
| `nanobio_studio_backend/nanobio_studio/app/services/pk_simulation.py` | Adapter to the legacy PK functions |
| `nanobio_studio_backend/nanobio_studio/app/schemas/pk_simulation.py` | Pydantic request/response |
| `nanobio_studio_backend/nanobio_studio/app/api/routes/pk.py` | Route (transport only) |
| `tests/test_pk_simulation_api.py` | 122 backend tests |
| `frontend/src/pages/workflow/pkSchema.ts` | PK field definitions, validation, payload |
| `frontend/src/pages/workflow/PKPanel.tsx` / `.css` | Result presentation |
| `frontend/src/charts/ConcentrationTimeChart.tsx` / `.css` | Chart, returned data only |
| `frontend/src/workflow/PkSimulation.test.tsx` | 38 frontend tests |
| `docs/PK_SLICE.md` | This document |

### Materially changed

| File | Change |
|---|---|
| `utils/pk_model.py` | `matplotlib.pyplot` import moved into `create_pk_plot()`; return annotation quoted. **No equation touched.** |
| `nanobio_studio_backend/.../vertical_slice.py` | Registers the PK router; path-aware validation handler; root endpoint list; app description |
| `frontend/src/api/types.ts` | PK request/response/error types, `PKResult` union |
| `frontend/src/api/client.ts` | `simulatePk()` with the same never-invent-a-result contract |
| `frontend/src/workflow/WorkflowContext.tsx` | `session.pk`, `setPkValue`, `pkResult`, `pkInputsReady`, `hydrate()` |
| `frontend/src/pages/workflow/Step3Review.tsx` / `.css` | PK input section, conditional execution, updated "what will run" |
| `frontend/src/pages/workflow/ResultsStage.tsx` | Separate PK card; pending stages reduced to assessments + visualisation |
| `frontend/src/shell/navigation.ts` | `simulation` summary now distinguishes the migrated engine from the unbuilt standalone module |
| `frontend/src/workflow/Workflow.test.tsx` | Three assertions retargeted to the new, true copy |
| `docs/WORKFLOW.md` | §4 and §6 updated |

---

## 10. Tests

Exact commands and results in §12. Coverage added:

**Backend (`tests/test_pk_simulation_api.py`, 122 tests)**

* endpoint registration, versioned path, design endpoint still intact;
* every scientific input required — missing, null, non-numeric, out of range;
* legacy widget bounds enforced; time step restricted to the legacy choices;
* unknown fields (including `disease`) rejected, not ignored;
* successful run: series lengths, parameter set, version, normalized inputs,
  assumptions, warnings, limitations, validation status;
* **legacy equivalence** — bit-exact parameters and point-for-point curves for
  the four API-reachable golden vectors, plus service-level equivalence for all
  seven including the two numerical edge cases;
* out-of-legacy-range vectors rejected rather than clamped;
* nullable half-life: null preserved, explained, and not suppressing the rest;
* calculation failure: non-finite curve, model exception, parameter-derivation
  exception, 500/400 routes — each returning no numbers at all;
* honesty: no clearance field, absence declared, no clinical prose, no mixing
  with the design score, distinct versions, disease never reaching the
  calculation;
* authentication required, and proven not to change a single number;
* Streamlit/matplotlib decoupling (subprocess), solver source unchanged, legacy
  plotting still functional.

**Frontend (`frontend/src/workflow/PkSimulation.test.tsx`, 38 tests)**

* inputs collected, nothing pre-filled, out-of-range reported not clamped;
* execution gate: no call when incomplete, one call when valid, blank window
  settings omitted from the payload;
* honest empty state: explicit panel, no chart, no number, score still shown;
* calculated results: exact peak/AUC/half-life, chart present, every point
  available as text, version, validation status, inputs, assumptions, warnings,
  limitations;
* honesty: clearance never displayed, null half-life as "not determined",
  arbitrary units not ng/mL, no clinical interpretation, PK visibly distinct
  from the score, therapeutic context visible without a causal claim;
* failure: backend 500, 422, malformed 200 — each with no fallback profile, and
  the design score left intact;
* drafts: PK inputs preserved and saved, no credential stored, pre-PK drafts
  un-runnable rather than defaulted.

---

## 11. Known limitations of this slice

1. **The rate constants are user inputs, not predictions.** The model does not
   infer them from size, charge, coating or ligand, so the profile reflects the
   constants entered rather than the formulation. Stated in the UI and in the
   API's `limitations`.
2. **No clearance, no volume of distribution, no bioavailability, no AUC(0–∞).**
   Declared explicitly rather than omitted (§6).
3. **No uncertainty quantification.** The model is deterministic; none exists in
   the codebase.
4. **Results are not persisted.** Re-running is the only way to recover a
   profile; there is no stored simulation history.
5. **`simulate_release_profile()` was not migrated** — it is a release model,
   not PK, and was out of scope.
6. **The standalone `/simulation` module page is still a placeholder.** The PK
   engine runs inside the Design Workflow only.
7. **The `sys.path` bootstrap remains**, exactly as in the scoring slice: the
   scientific code still lives in the repository root. Removed when the
   scientific core is ported into the backend package.
8. **TypeScript types are hand-maintained** against the Pydantic schemas, not
   generated from OpenAPI.
9. **Numerical reproducibility depends on pinned NumPy.** `pk_model.py` switches
   between `np.trapezoid` and `np.trapz`; the AUC path differs by version.
10. **A browser walkthrough was not performed** — the Chrome extension was not
    connected in this session. Verification was done at the HTTP layer against a
    live uvicorn (§12) and through the 114-test frontend suite.

---

## 12. Verification

### Commands (Windows PowerShell)

```powershell
# Backend — PK slice only
cd D:\Nano_bio_Studio_30-7-2026
python -m pytest tests\test_pk_simulation_api.py -q

# Backend — everything, including the golden-vector scientific suite
python -m pytest tests -q

# Frontend
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm run typecheck
npm test
npm run build
```

### Results

| Suite | Command | Before | After |
|---|---|---|---|
| PK slice API | `pytest tests\test_pk_simulation_api.py -q` | — | **122 passed** |
| Full backend suite | `pytest tests -q` | 613 passed | **735 passed** |
| Frontend tests | `npm test` | 75 passed | **114 passed** |
| TypeScript (strict) | `npm run typecheck` | clean | **clean** |
| Production build | `npm run build` | succeeded | **succeeded** (279 kB JS / 86 kB gzip) |

The pre-existing golden-vector scientific suite passes unchanged, which is the
evidence that moving the matplotlib import altered no number.

### Live end-to-end check

Against `uvicorn nanobio_studio.app.vertical_slice:app` with a real
authenticated session:

```
[unauthenticated] HTTP 401  ->  {"detail": {"error": "not_authenticated", …}}
[login]           HTTP 200  user=pk_live_check
[pk/simulate]     HTTP 200
  points            481
  unit              arbitrary units (dose-scaled amount)
  C_max central     1.4411129411755834
  T_max central     2.6
  AUC central       18.92076869856752
  half-life         5.200000000000001
  version           pk-two-compartment-adapter-0.1.0
  validation        not_experimentally_validated
  clearance field?  False
  not produced      ['clearance', 'volume_of_distribution', 'bioavailability',
                     'auc_extrapolated_to_infinity']

[legacy direct call]
  C_max central     1.4411129411755834
  AUC central       18.92076869856752
  half-life         5.200000000000001

BIT-EXACT MATCH OVER HTTP: True     ← includes all 481 curve points

[invalid kel=99]  HTTP 422  error=validation_error results_available=False has_numbers=False
[missing k21]     HTTP 422  error=validation_error results_available=False
[design/score]    HTTP 200  delivery=87.52475247524752  version=design-impact-adapter-0.1.0
```

The throwaway account used for this check was removed afterwards; the auth
database again contains only `admin`.

---

## 13. Open questions from this slice

| # | Question |
|---|---|
| **Q-PK1** | The legacy PK model has no version. `PK_CALCULATION_VERSION` currently versions the *adapter contract*. Should `two_compartment_model` receive a formal scientific version, so stored profiles stay interpretable across changes? (Mirrors Q-VS1 for the score.) |
| **Q-PK2** | Should the model gain a volume-of-distribution term, so it can report real concentrations and a genuine clearance? This is a scientific change requiring approval, not an equivalence migration. |
| **Q-PK3** | Should the rate constants be *predicted* from formulation parameters — closing the loop between Step 2 and the PK model — and if so, on what evidence? Today they are unrelated inputs, which is why the disease and the formulation do not affect the profile. |
| **Q-PK4** | The legacy PDF report labelled these values ng/mL, contradicting the model. Should that report be corrected as part of a later slice? |
| **Q-PK5** | `simulate_release_profile()` remains unmigrated. Does the release model belong in this endpoint, a separate one, or nowhere in the React workflow? |
| **Q-PK6** | Should PK runs be persisted with their inputs and version, so a profile can be re-derived? (Shared with the scoring slice.) |

---

## 14. Before production deployment

In addition to the items already listed in `docs/VERTICAL_SLICE.md` §10:

1. **Pin NumPy exactly** — the `trapezoid`/`trapz` switch means the AUC path is
   version-dependent (`utils/pk_model.py:11-14`).
2. **Rate-limit `/api/v1/pk/simulate`** — it is compute-bound and the response
   grows with `duration_h / time_step_h` (up to 3 361 points).
3. **Consider a response-size cap or paging** for the full series at the finest
   step over the longest window.
4. **Persist runs** with inputs, version and result, so a profile is reproducible
   after the fact.
5. **Remove the `sys.path` bootstrap** when the scientific core is ported.
