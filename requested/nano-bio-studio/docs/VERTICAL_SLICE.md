# Phase 2 Vertical Slice — React + TypeScript → FastAPI → Canonical Scoring

**Created:** 2026-07-30
**Status:** Implemented and verified end-to-end.
**Scope:** One endpoint, one page. This is **not** the application migration.

> **Scientific positioning.** Every value this slice produces is a computational
> research-planning result. It is not experimentally validated, not clinically
> validated, not a regulatory approval prediction, not a diagnosis, not a
> treatment recommendation, and not a substitute for wet-lab testing.

---

## 1. Architecture and request flow

```
┌──────────────────────────────┐
│ React 18 + TypeScript (Vite) │  http://127.0.0.1:5173
│  frontend/src/App.tsx        │
│   • form + client validation │
│   • loading / empty / error  │
└──────────────┬───────────────┘
               │  fetch POST (CORS, explicit allow-list)
               ▼
┌──────────────────────────────┐
│ FastAPI                      │  http://127.0.0.1:8000
│  app/api/routes/design.py    │  ← transport only, zero science
│  app/schemas/design_score.py │  ← Pydantic validation
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ Adapter (service layer)      │
│  app/services/design_scoring │  ← mapping + provenance, zero science
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ CANONICAL SCIENCE            │
│  core/scoring.py             │  ← called VERBATIM, unmodified
│    compute_impact()          │
└──────────────────────────────┘
```

**The scientific function is imported and called verbatim.** No formula, weight,
threshold or default is reimplemented anywhere in the backend. This is verified
by equivalence tests that compare API output against a direct call to
`compute_impact()` for 20 golden-vector designs and require **bit-exact** match
(`repr()` comparison, not `approx`).

---

## 2. Endpoint contract

### `POST /api/v1/design/score`

**Required** (never defaulted — omitting one is a 422):

| Field | Type | Bounds |
|---|---|---|
| `size_nm` | float | `> 0`, `<= 10000` |
| `charge_mv` | float | `-200 … 200` |
| `encapsulation_percent` | float | `0 … 100` |

**Optional** — omitted ≡ explicit `null`; both apply the canonical default:

`pdi`, `hydrodynamic_size_nm`, `stability_percent`, `surface_area_nm2`,
`degradation_time_days`, `crystallinity_index`, `hydrophobicity_logp`,
`coating_thickness_nm`, `ligand_density_percent`, `receptor_binding_kd_nm`,
`release_predictability_percent`, `ligand`, `surface_coating`,
`functional_groups`.

Unknown fields are **rejected** (`extra="forbid"`), not silently ignored.

### Success — 200

```jsonc
{
  "design_impact_score": { "delivery": 87.52475247524752, "toxicity": 0.8, "cost": 80.75 },
  "score_version": "design-impact-adapter-0.1.0",
  "component_scores": { "delivery": { "value": …, "scale": …, "meaning": … }, … },
  "normalized_inputs": { "Size": 100, "PDI": 0.15, "HydrodynamicSize": 120.0, … },
  "warnings": [ "Optional fields not provided; canonical defaults applied: …" ],
  "prediction_basis": "rule_based_physicochemical_heuristic",
  "evidence_level": "literature_informed_unvalidated",
  "validation_status": "not_experimentally_validated",
  "limitations": [ … ],
  "scientific_source": "core.scoring.compute_impact"
}
```

### Failure — 400 / 422 / 500

```jsonc
{ "error": "calculation_failed", "message": "…", "detail": "…", "score_available": false }
```

**There is no score field on any failure path.** A failed calculation never
returns a number, favourable or otherwise. Enforced by tests on the API, the
service, and the React client independently.

### `GET /health`, `GET /ready`, `GET /`

Retained from the existing backend. `/` carries the research-use-only notice.

---

## 3. Input-to-scoring adapter

`nanobio_studio_backend/nanobio_studio/app/services/design_scoring.py`

| Responsibility | Notes |
|---|---|
| Map snake_case API fields → CapitalCase canonical keys | Mapping declared once, in `DesignScoreRequest.FIELD_MAP` |
| Apply the DEFECT-D9 null contract | **Reuses the canonical helpers** `_optional_float` / `_optional_value`, so it cannot drift from the scoring function's own interpretation |
| Report `normalized_inputs` | The effective values the formula will use |
| Attach provenance | Version, basis, evidence level, validation status |
| Convert failures to structured errors | `ScoringFailure` with a machine-readable code |
| Reject non-finite results | NaN/Inf is a failure, not a score |

Fields the caller never mentions are **omitted** from the dict handed to
`compute_impact`, so the canonical function applies its own defaults. The adapter
does not duplicate them.

---

## 4. Scientific source function

`core/scoring.py::compute_impact(design: dict, weights: dict | None) -> dict`
→ `{"Delivery": 0–100, "Toxicity": 0–10, "Cost": 0–100}`

This is the **Principal Design Score** designated canonical by DECISION 3A.

### Dependence on Step 1 (unapproved)

This slice **depends on the Step 1 corrections** and does not re-open them:

| Step 1 change | How the slice depends on it |
|---|---|
| **DEFECT-D9 null contract** | The adapter imports `REQUIRED_DESIGN_KEYS`, `_optional_float`, `_optional_value` directly. The API's "null ≡ omitted" guarantee *is* the D9 contract, tested over HTTP. |
| **`REQUIRED_DESIGN_KEYS` constant** | Introduced in Step 1; drives required-field handling. |
| Corrections to D8/D10/D11 | Not used here — this slice touches only the design score, not the assessment engines. |

If Step 1 were reverted, the endpoint's null handling would break and its tests
would fail. Step 1 has **not** been silently expanded or rewritten by this work.

---

## 5. Response fields

| Field | Meaning |
|---|---|
| `design_impact_score` | The three canonical measures. **Not** a single composite. |
| `score_version` | Adapter output-contract version. |
| `component_scores` | Same values with scale and meaning attached. |
| `normalized_inputs` | Effective inputs after defaults. Makes the result reproducible. |
| `warnings` | Non-blocking transparency notes (defaults applied, nulls treated as absent, open scientific questions touched). |
| `prediction_basis` | `rule_based_physicochemical_heuristic` — not a trained model. |
| `evidence_level` | `literature_informed_unvalidated`. |
| `validation_status` | `not_experimentally_validated`. |
| `limitations` | Explicit list, always returned. |
| `scientific_source` | The exact function that produced the numbers. |

---

## 6. Local PowerShell commands

All commands run from **Windows PowerShell**. No VS Code required.

### 6.1 Backend dependencies

```powershell
cd D:\Nano_bio_Studio_30-7-2026
python -m pip install fastapi "uvicorn[standard]" pydantic pydantic-settings httpx pytest
```

### 6.2 Start FastAPI

```powershell
cd D:\Nano_bio_Studio_30-7-2026\nanobio_studio_backend
python -m uvicorn nanobio_studio.app.vertical_slice:app --host 127.0.0.1 --port 8000 --reload
```

API docs: `http://127.0.0.1:8000/docs`

> **Superseded (2026-08-02).** This section previously said *"Use `127.0.0.1`,
> not `localhost`"*. That advice treated a symptom and is no longer correct.
>
> The browser never contacts port 8000 directly any more. The dev server proxies
> `/api`, `/health` and `/ready` to the backend (`frontend/vite.config.ts`), so
> every API call is **same-origin** and `localhost`, `127.0.0.1` and a LAN
> address all work.
>
> The reason this matters is the session cookie, which is `SameSite=Lax`. When
> the app was served from `localhost:5173` and called the API at
> `127.0.0.1:8000`, those were **different sites**: the browser accepted the
> cookie on the login response and then refused to send it on anything else,
> signing the user out the instant they signed in. The proxy removes the
> cross-site request rather than working around it. See
> `docs/INTEGRATION_SLICE.md` §9.

### 6.3 Frontend dependencies

```powershell
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm install
```

### 6.4 Start React

```powershell
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm run dev
```

Then open `http://127.0.0.1:5173`.

### 6.5 Backend tests

```powershell
cd D:\Nano_bio_Studio_30-7-2026
python -m pytest tests\test_vertical_slice_api.py -q      # slice only
python -m pytest tests -q                                  # everything
python -m pytest tests -q -m "not known_defect"            # migration contract
```

### 6.6 Frontend checks and tests

```powershell
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm run typecheck
npm test
```

### 6.7 Frontend production build

```powershell
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm run build
npm run preview      # optional: serve the built bundle
```

### 6.8 Configuration

```powershell
# Frontend: copy the example env file
cd D:\Nano_bio_Studio_30-7-2026\frontend
Copy-Item .env.example .env

# Backend: override the CORS allow-list if needed
$env:SLICE_CORS_ORIGINS = '["http://127.0.0.1:5173"]'
```

---

## 7. Test results

| Suite | Command | Result |
|---|---|---|
| Slice API | `pytest tests\test_vertical_slice_api.py -q` | **75 passed** |
| Full backend suite | `pytest tests -q` | **579 passed** |
| Migration contract | `pytest tests -q -m "not known_defect"` | **520 passed**, 59 deselected |
| Known defects | `pytest tests -q -m "known_defect"` | **59 passed** |
| Frontend type check | `npm run typecheck` | **clean, 0 errors** |
| Frontend tests | `npm test` | **18 passed** |
| Frontend build | `npm run build` | **succeeded** — 153 kB JS / 49 kB gzip |

Backend coverage includes request-schema validation, successful scoring,
component scores, null/missing inputs, malformed input, calculation failure
(no favourable fallback), health, and **bit-exact equivalence against the
canonical function across 20 golden-vector designs**.

Frontend coverage includes type checking, production build, API client
behaviour, form validation, success rendering, error rendering, and a test
proving **no scientific result appears before execution**.

**The existing golden-vector suite was not weakened.** All 504 pre-existing
tests still pass unchanged; the slice adds 75.

---

## 8. Known limitations

1. **`component_scores` are the three canonical outputs, not the 12 internal
   sub-scores.** `compute_impact` does not return its internal size/charge/PDI
   sub-scores, and exposing them would mean modifying the canonical function —
   out of scope. Recorded as **Q-VS2** below.
2. **No composite "Overall Score".** DECISION 2 forbids implementing the
   replacement until reviewed, so the API returns three separate measures.
3. **Only the design score.** Assessment engines (safety, disease-fit,
   manufacturability, regulatory, confidence) are deliberately excluded and must
   not be combined with this score.
4. **No persistence, no authentication.** The endpoint is unauthenticated and
   stores nothing.
5. **No uncertainty quantification** — none exists in the codebase (Q5).
6. **TypeScript types are hand-maintained**, not generated from OpenAPI.
7. **`act()` warnings** appear in the frontend test output from the health-check
   effect. Tests pass; the warnings are cosmetic and worth cleaning up later.
8. **Frontend exposes 5 of 17 optional fields.** The form deliberately shows only
   the required inputs plus PDI and ligand; the API accepts all 17.

---

## 9. What remains temporary

| Item | Why temporary | Removed when |
|---|---|---|
| **`sys.path` bootstrap** in `design_scoring.py` | The canonical science still lives in the repo root beside the Streamlit app. The backend inserts the repo root on `sys.path` to import it. | Step 3 moves the scientific core into `backend/app/scientific/` |
| **Separate `vertical_slice.py` app** | The existing `app/main.py` requires PostgreSQL at startup and `loguru` (not installed), so it cannot boot for this slice | Step 2 establishes the consolidated backend skeleton |
| **`core/scoring.py` imports `streamlit`** | The canonical module still imports Streamlit, so the API process loads it | Step 3 decouples the scientific core |
| **Hand-written TS types** | No OpenAPI codegen yet | Codegen added in a later slice |
| **`SCORE_VERSION` on the adapter, not the formula** | The legacy formula is unversioned | A formal formula version is assigned (Q-VS1) |

---

## 10. Before production deployment

Not deployable as-is. Required first:

1. **Authentication and authorisation** — the endpoint is currently open.
2. **Rate limiting** on a compute-bound endpoint.
3. **Remove the `sys.path` bootstrap**; port the scientific core properly.
4. **Consolidate the two FastAPI entry points.**
5. **Drop the `streamlit` import** from the scientific path.
6. **Pin dependencies exactly** — numerical reproducibility depends on the NumPy
   version (`utils/pk_model.py` switches on `trapezoid` vs `trapz`).
7. **Structured logging and request IDs.**
8. **CORS from environment per deployment**, never a wildcard.
9. **Resolve the scoring canonicalisation questions** (Q3/Q5/Q6 in
   `docs/SCORING_CANONICALIZATION.md`) before any composite score ships.
10. **Persistence and reproducibility records** — store inputs, version and
    result so a score can be re-derived.
11. **`render.yaml`, `$PORT` binding, health checks** (Phase 7).
12. **Security review** of the whole surface.

---

## 11. Open questions from this slice

| # | Question |
|---|---|
| **Q-VS1** | The legacy formula has no version. `SCORE_VERSION` currently versions the *adapter contract*, not the science. Should `compute_impact` receive a formal version, so stored results remain interpretable? |
| **Q-VS2** | Should `compute_impact` be extended to return its 12 internal sub-scores? Useful for the UI and for explainability, but it changes the canonical function's signature and needs scientific sign-off. |
| **Q-VS3** | The API exposes 17 optional fields; the prototype form shows 5. Which subset belongs in the real designer UI? |

---

## Appendix — files created

| File | Purpose |
|---|---|
| `nanobio_studio_backend/nanobio_studio/app/services/design_scoring.py` | Adapter to the canonical function |
| `nanobio_studio_backend/nanobio_studio/app/schemas/design_score.py` | Pydantic request/response |
| `nanobio_studio_backend/nanobio_studio/app/api/routes/design.py` | Route (transport only) |
| `nanobio_studio_backend/nanobio_studio/app/vertical_slice.py` | DB-free ASGI app |
| `tests/test_vertical_slice_api.py` | 75 backend tests |
| `frontend/` | React + TypeScript app (Vite) |
| `frontend/src/App.tsx`, `App.css`, `index.css` | UI |
| `frontend/src/api/client.ts`, `types.ts` | Typed API client |
| `frontend/src/App.test.tsx` | 18 frontend tests |
| `docs/VERTICAL_SLICE.md` | This document |

Materially changed: `nanobio_studio_backend/nanobio_studio/app/core/config.py`
(added `slice_cors_origins`).
