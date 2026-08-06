# Integration Slice — Demo Workspace, Persistence, and the Operational Workspace Modules

**Created:** 2026-08-01
**Status:** Implemented and verified end-to-end.
**Predecessors:** `docs/VERTICAL_SLICE.md` (design score), `docs/PK_SLICE.md` (PK),
`docs/MODULE_INVENTORY.md` (the audit this work was planned from).

> **Scientific positioning.** Every value the platform produces is a computational
> research-planning result. Not experimentally validated, not clinically validated,
> not a regulatory approval prediction, not a diagnosis, not a dosing or treatment
> recommendation.

---

## 1. What this slice delivered

| Area | Before | After |
|---|---|---|
| Demo Workspace | did not exist | **Operational** — 7 versioned scenarios, preview, isolated load |
| Simulation History | placeholder page | **Operational** — server-stored runs, filters, delete |
| Compare Designs | placeholder page | **Operational** — aligned comparison, no ranking |
| Projects | placeholder page | **Operational** — server-stored, runs survive deletion |
| Reports | placeholder page | **Limited prototype** — plain-text report from a stored run |
| Persistence | `localStorage` only | **SQLAlchemy async** (SQLite local → PostgreSQL) |

Four placeholder pages were removed by migrating genuine functionality. The
remaining placeholders are unchanged and stay honest, because their engines are
genuinely blocked (§6).

---

## 2. Demo Workspace

### 2.1 The fixture layer

`nanobio_studio_backend/nanobio_studio/app/demo/scenarios.py` — one typed,
versioned module, **not constants scattered through React components**.

* `DEMO_FIXTURE_VERSION = "demo-scenarios-1.0.0"`. Every run started from a
  scenario records this version, so a stored result stays traceable to the exact
  inputs it came from even after the set is revised.
* `DemoScenario` is a frozen dataclass carrying **inputs and teaching metadata
  only**. There is no field on it capable of holding a score, a concentration, a
  half-life or an assessment verdict, so a stored result cannot be expressed —
  and `test_no_scenario_contains_a_stored_scientific_result` scans every field
  name to prove it.

### 2.2 The seven scenarios

Requested coverage was breast, lung, colorectal, pancreatic and **prostate**. The
curated mapping contains **no prostate indication**, so — per the instruction to
adapt to the genuine mappings and never invent a combination — the fifth
indication scenario uses **Liver Cancer (HCC)**, the remaining available
indication and one of only two with a genuine assessment profile.

| # | Slug | Indication / subtype / therapeutic | Teaching purpose |
|---|---|---|---|
| 1 | `breast-her2-targeted` | Breast Cancer / HER2-enriched / Trastuzumab | Clean actively-targeted run, full connected path |
| 2 | `lung-nsclc-checkpoint` | Lung Cancer / NSCLC / Pembrolizumab | Passive targeting; the fixed 60/100 baseline; faster elimination |
| 3 | `colorectal-msi-high` | Colorectal Cancer / MSI-H / Pembrolizumab | Non-PEG coating, positive zeta outside the optimum band |
| 4 | `pancreatic-pdac-stroma` | Pancreatic Cancer / Ductal Adenocarcinoma / Abraxane | Small particle, slow elimination, possibly undeterminable half-life |
| 5 | `liver-hcc-galnac` | Liver Cancer (HCC) / AFP-high HCC / Sorafenib | Reference baseline inside every documented optimum band |
| 6 | `technical-incomplete-inputs` | Breast Cancer / Triple-Negative / Paclitaxel | **Validation and blocked execution** |
| 7 | `technical-boundary-values` | Colorectal Cancer / Adenocarcinoma / Irinotecan | **Warnings without bypassing validation** |

Every triple is verified against the application's own curated mapping by
`test_every_scenario_uses_a_real_triple`, which parses `diseaseData.ts` directly.

### 2.3 What each scenario carries

Name · **"Synthetic demonstration data" badge** · learning purpose · disease ·
subtype · therapeutic · all accepted design inputs · all PK inputs · assumptions ·
expected warnings · engines that will run · engines that will not run (with
reasons) · provenance.

`expected_warnings` is the one place that anticipates engine behaviour. It is
rendered as *"warnings you should expect to see"* and never as the engine's
output — the authoritative list always comes from the response.

**Provenance.** Where a value sits at a documented threshold, the threshold is
cited (`core/scoring.py` size optimum 80–120 nm, zeta ±10 mV, the coating bonus
table, the 60/100 passive-targeting baseline). Scenario 5 reuses the legacy
application's own documented 23-field defaults. Everything else is stated as
synthetic.

### 2.4 Loading a scenario

1. **Preview first** — a scrollable dialog showing every input, the engines that
   will and will not run, assumptions, expected warnings and provenance.
2. **Load** creates an **isolated working copy**: `loadScenario()` builds a new
   session with a new id, so it never overwrites work in progress.
3. Steps 1, 2 and 3 are populated. **Nothing is calculated.**
4. Ordinary validation still applies — proven by scenario 6, which cannot advance
   past Step 2.
5. Every value is editable; edits never touch the template, which lives
   server-side.
6. `session.demo` carries the scenario slug and fixture version through to the
   stored run, so a demo run is **never** presented as the user's own research.

### 2.5 Commands

```powershell
# install or refresh the templates — idempotent, keyed on slug
python nanobio_studio_backend\scripts\demo_data.py seed

# list the fixture set without touching the database
python nanobio_studio_backend\scripts\demo_data.py list

# report exactly what a reset WOULD remove — deletes nothing
python nanobio_studio_backend\scripts\demo_data.py reset

# actually delete demo-generated runs and projects
python nanobio_studio_backend\scripts\demo_data.py reset --confirm

# also drop the seeded templates
python nanobio_studio_backend\scripts\demo_data.py reset --confirm --include-templates
```

Verified idempotent: first run created 7, second reported 7 unchanged, three
further runs left the row count at 7.

**Reset safety.** Every statement is filtered on `origin = 'demo'`. Without
`--confirm` nothing is deleted and the scope is printed, including how many
genuine user records exist and will be untouched. The UI mirrors this: the reset
dialog shows the scope before offering the destructive action.

---

## 3. Persistence

`app/db/workspace_models.py` — the intended production models, running against
SQLite locally and PostgreSQL in deployment through the same declarative layer.

| Table | Purpose |
|---|---|
| `workspace_runs` | A completed or deliberately blocked execution |
| `workspace_projects` | Named grouping of runs |
| `workspace_demo_templates` | Seeded scenario templates (global, not user data) |

### Invariants enforced in the service layer

1. **A result cannot be stored without the inputs that produced it.** An orphan
   result would be an unreproducible record; the API returns `inputs_required`.
2. **`engines_run` is derived, not trusted.** It is computed from which result
   payloads are actually present, so a caller cannot claim an engine ran.
3. **Deleting a project never deletes its runs.** The FK is `ON DELETE SET NULL`,
   so a grouping mistake cannot cost a user their calculated results.
4. **Ownership is checked before existence.** Another user's run returns 404, not
   403, so ids cannot be probed.
5. **`origin` is an indexed column, not a naming convention**, which is what makes
   the reset command's scope provable.

### Limitation

`result_json` is stored as JSON text rather than normalised columns, because the
engine response shapes are versioned contracts owned by the services. Normalising
them here would duplicate the Pydantic models and guarantee drift. Engine version
strings are stored alongside so a record stays interpretable when a contract
changes.

---

## 4. Endpoints added

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/demo/scenarios` | List scenarios (inputs only) |
| GET | `/api/v1/demo/scenarios/{slug}` | Preview one scenario |
| POST | `/api/v1/demo/seed` | Install/refresh templates (admin) |
| POST | `/api/v1/demo/reset` | Scoped demo deletion |
| POST | `/api/v1/runs` | Store a completed run |
| GET | `/api/v1/runs` | Simulation History, with filters |
| GET | `/api/v1/runs/{id}` | Open one stored run |
| DELETE | `/api/v1/runs/{id}` | Delete a run (not viewers) |
| POST | `/api/v1/runs/{id}/project` | Assign/detach a project |
| GET | `/api/v1/runs/compare/select` | Compare 2–4 runs |
| GET/POST | `/api/v1/projects` | List / create |
| DELETE | `/api/v1/projects/{id}` | Delete (runs preserved) |

All authenticated. All failures return a structured error with
`data_available: false` and no data field.

---

## 5. Compare Designs — and what it deliberately does not do

Aligns indication, subtype, therapeutic, origin, formulation inputs, the three
design-impact components, PK inputs, the PK parameters, and both model versions
and validation statuses.

**No combined ranking.** No approved formula exists for merging Delivery,
Toxicity, Cost and PK outputs (blocker **B5**), so the page does not name a best
design and does not sort, sum or average across columns. This is stated in the
API `notice` and again in a closing alert, and asserted by test.

**A value a run does not have renders as "not calculated"** — never as zero, and
never borrowed from another run.

**PK charts are shown side by side, not overlaid.** The model defines no common
scale across runs, so a shared axis would misrepresent the data.

---

## 6. Reports

Generated in the browser **from the stored record**, so a report cannot drift
from what the screen shows or contain a value no engine produced.

Every report states: synthetic-demo origin (when applicable, with the scenario
slug and fixture version, and a `DEMO_` filename prefix) · therapeutic context and
that it did not affect the calculation · exact formulation and PK inputs ·
engines executed · **engines not executed, with reasons** · calculated outputs ·
units · model versions · warnings · assumptions · limitations · quantities the
model does not produce · validation status · research-use-only disclaimer.

**Unit terminology is fixed and asserted by test:** PK outputs are
`dose-scaled compartment amount (arbitrary units)`. They are never called a
concentration. `ng/mL` appears only inside an explicit denial.

**Limitation:** plain text only. Typeset PDF, CSV and JSON export are not built,
which is why Reports is **Limited prototype** and not Operational.

---

## 7. Module status after this slice

| # | Module | Status | Genuine legacy source | Endpoint |
|---|---|---|---|---|
| 1 | Disease & Therapeutic Selection | **Operational** | `data/disease_drug_mapping.py` | client data |
| 2 | Nanoparticle Design Parameters | **Operational** | `pages/1_Design_Parameters.py` | request schema |
| 3 | Design Impact Score | **Operational** | `core/scoring.py` | `POST /api/v1/design/score` |
| 4 | PK Simulation | **Operational** | `utils/pk_model.py` | `POST /api/v1/pk/simulate` |
| 5 | Results | **Operational** | display layer | — |
| 6 | **Demo Workspace** | **Operational** | new (fixtures) | `/api/v1/demo/*` |
| 7 | **Compare Designs** | **Operational** | new | `/api/v1/runs/compare/select` |
| 8 | **Simulation History** | **Operational** | replaces `modules/trial_registry.py` | `/api/v1/runs` |
| 9 | **Projects** | **Operational** | replaces `design_persistence.py` | `/api/v1/projects` |
| 10 | **Reports** | **Limited prototype** | replaces `reports/scientific_report_generator.py` | client-side from stored run |
| 11 | Scientific Assessments | Migration in progress | `engine/` ×6 | — |
| 12 | Protocol Generator | Migration in progress | `modules/protocol.py` | — |
| 13 | Molecular Visualisation | Not yet operational | `components/nanoparticle_3d_viewer.py` | — |
| 14 | ML Training | Limited prototype (not surfaced) | `models_store/` | — |
| 15 | AI Co-Designer | Not yet operational | `ai_engine/` | — |
| 16 | Administration | Migration in progress (auth Operational) | `auth.py` | `/api/v1/auth/*` |
| 17 | Settings | Not yet operational | scattered | — |
| 18 | Help & Tutorial | Not yet operational | `modules/tutorial.py` | — |

---

## 8. Engines NOT migrated, and exactly why

Each was assessed and deliberately left unconnected. None is an engineering
gap; every one needs a scientific decision this work will not make automatically.

| Engine | Blocker | What is needed |
|---|---|---|
| **Scientific Assessments** (`engine/` ×6) | **B1** — `config/disease_profiles.py` defines only `HCC-S` and `PDAC-I`; `get_disease_profile()` silently substitutes HCC for anything else (DEFECT-D1). Connecting them would compute hepatocellular-carcinoma biology under a lung-cancer heading for 3 of the 5 indications | New disease profiles authored and scientifically reviewed |
| **Regulatory verdict** | **B2** — `verdict_available = False`; the favourable disease-fit threshold is uncalibrated and unreachable (ceiling 68.33) | Calibration against real outcomes |
| **AI Co-Designer** | **B4** — `ai_engine/simulator_adapter.py::simulate_design_placeholder()` is an explicit placeholder with toy proxies, so the optimiser optimises a fake objective. The legacy page also showed a hard-coded candidate table (DEFECT-D6) | Wire the objective to the connected engines, then re-validate |
| **ML uptake / particle size** | **B3** — only `toxicity_prediction` models exist in `models_store/`; the legacy code silently falls back to heuristics | Train and validate the missing models, or remove the silent fallback |
| **16 of 19 predictors** | **B6** — uncalibrated heuristics; `intellectual_property` and `publication_readiness` have no defensible basis at all | Prioritise by scientific defensibility; `osmolarity_calculator` is the strongest candidate |
| **Molecular Visualisation** | Engineering, not science — needs a 3-D renderer (react-three-fiber), a substantial new dependency | Scoped separately |

---

## 9. Verification

```powershell
cd D:\Nano_bio_Studio_30-7-2026
python -m pytest tests -q                          # 829 passed
python -m pytest tests\test_workspace_api.py -q     # 65 passed
python -m pytest tests\test_static_frontend.py -q   # 29 passed

cd frontend
npm run typecheck                                   # clean
npm test                                            # 188 passed
npm run build                                       # succeeded
node walkthrough.mjs                                # PROBLEMS: none
```

### Same-origin verification (both loopback spellings, dev and production)

```
dev server (5173, proxied)      prod shape (8000, SPA served by FastAPI)
  / serves the SPA      : yes     / serves the SPA      : yes
  /api descriptor       : ok      /api descriptor       : ok
  /api/v1/nope          : JSON    /api/v1/nope          : JSON 404
  /demo /history        : signed  /demo /history        : signed in
  /compare /projects    :   in    /compare /projects    : signed in
  deep-link /demo cards : 7       deep-link /demo cards : 7
  401s after login      : 0       401s after login      : 0
  react crashes         : none    react crashes         : none
```

Identical at `http://localhost:…` and `http://127.0.0.1:…` in both shapes.

### Live walkthrough (Playwright, desktop 1440×900 + tablet 834×1112)

```
logged in, landed on ...... /start
demo scenario cards ....... 7
preview states not-patient-data ... true
step 1 indication ......... Liver Cancer (HCC)
step 1 drug ............... Sorafenib
step 2 size_nm ............ 100
step 3 k_el ............... 0.1
PK will run ............... true
delivery score (calculated) 90.69      ← genuine, from the scenario's inputs
PK C_max (calculated) ..... 1.4411129411755834
clearance shown as ........ not produced
run saved ................. Stored as run #1, recorded as demo-generated
history rows .............. 2
compare states no ranking . true
report downloaded ......... DEMO_nanobio_run2_..._2026-08-01.txt
AI module honest status ... true
AI module shows no number . true
PROBLEMS: none
```

Screenshots: `docs/screenshots/int-01` … `int-13`.

### Five real defects caught and fixed

**A cross-site session cookie signed the user out the instant they signed in.**
The session cookie is `SameSite=Lax`. The app was served from `localhost:5173`
while calling the API directly at `127.0.0.1:8000` — **different sites** for
cookie purposes. The browser accepted the cookie on the login response and then
refused to send it on every subsequent request, so login appeared to succeed and
the next navigation bounced the user straight back out. Chrome's third-party
cookie restrictions produce the same result; headless Chromium is more
permissive, which is why automated checks missed it.

Earlier guidance in `docs/VERTICAL_SLICE.md` said *"use `127.0.0.1`, not
`localhost`"*. That was a symptom fix — it happened to make both ends agree,
without removing the cross-site request. The actual fix is same-origin serving:

* **Development** — the dev server proxies `/api`, `/health` and `/ready` to the
  backend (`frontend/vite.config.ts`), with `host: true` so either loopback
  spelling works.
* **Production** — `SERVE_FRONTEND=true` makes the FastAPI app serve the built
  SPA from its own origin (`app/api/static_frontend.py`), mounted after every
  router so API routes always win.
* `VITE_API_BASE_URL` now defaults to empty (same-origin) in `.env` *and* in
  `src/api/client.ts`, so a missing env file cannot silently reintroduce the bug.

The cookie keeps its stronger `Lax` posture, and CORS becomes irrelevant in both
shapes. Verified at `localhost` and `127.0.0.1`, in both dev and production
shape: **0 API 401s after login**, session survives navigation across every
route, deep links resolve, and `/api/v1/nope` still returns **JSON 404, not
HTML** — which is what keeps the typed client's error handling intact.

**An expired session left the user stranded, still shown as signed in.**
Sessions carry a 30-minute idle timeout, but `AuthContext` checked `/auth/me`
only once at mount and cached the result. A user who stepped away came back to a
shell that still displayed their name and role while every request returned 401 —
so the Demo Workspace read *"Scenarios unavailable — Sign in to continue."* on a
page they appeared to be authenticated on, with no route out but a manual reload.
`AuthContext.refresh()`, commented "used after a 401", was **never called by
anything**.

`setUnauthorizedHandler()` in `src/api/client.ts` now notifies the auth layer on
any 401 from a data endpoint; `AuthProvider` clears the user, `ProtectedRoute`
redirects, and the login page explains via `sessionExpired`. `api/auth.ts` is
deliberately *not* wired in — its own 401 during the initial "who am I" check is
the ordinary logged-out path and would loop. Verified live against the running
backend: session invalidated mid-session → redirected to login → expiry
explained → not stranded → no crash.

**An object `detail` crashed the whole page.** FastAPI's
`HTTPException(detail={...})` serialises to a nested object — the 401 from
`get_current_user` is `{"detail": {"error": …, "message": …}}`. The API client
copied that straight into `error.detail`, whose declared type is
`string | null`, and every component rendering `{error.detail}` threw
*"Objects are not valid as a React child"*, unmounting the application.

TypeScript could not catch this: the value crosses the network as `unknown`, so
the annotation was an assertion rather than a guarantee. `normaliseDetail()` and
`readErrorBody()` in `src/api/client.ts` now enforce the declared type **at the
boundary**, for all three clients, and additionally surface the envelope's own
message ("Sign in to continue.") instead of a bare "HTTP 401".
`src/api/client.test.ts` reproduces the exact 401 body across every endpoint.

**No error boundary existed.** Any render-time throw anywhere in the tree caused
React to unmount everything, leaving a completely blank page with no explanation
— indistinguishable from a hang, a logged-out state or a dead server. This
surfaced when a long-lived development tab hit a stale hot-reloaded
`WorkflowContext` module and the Demo Workspace called a `loadScenario` that did
not exist on it.

`src/shell/ErrorBoundary.tsx` now wraps the router and the auth provider (so it
still renders when the failure is in one of them) and shows what failed, the
technical detail for a bug report, and a full reload — which is what actually
discards a stale module. It deliberately states that nothing was calculated or
saved and **never substitutes plausible content for the view that failed**;
seven tests assert this, including that no number appears in the crash panel.

**The dialog had no height constraint.**

A long dialog pushed its confirm button off-screen where it could not be
scrolled to at all — the scenario preview was unusable. The panel is now a flex
column with a scrollable body and pinned title/footer, plus a `wide` variant for
content-heavy dialogs and a column-reversed footer under 560 px. **This was a
genuine bug in the shared design-system component, not a test-only fix.**

### Sidebar active state

`activeNavKeyForPath` in `src/shell/navigation.ts` is the single resolver for
which menu entry owns a route. The design workflow is one route family —
`/start`, all four `/workflow/*` steps, review/run, results and every resume
target — so the indicator stays lit for the whole journey.

The sidebar uses a plain `Link`, not `NavLink`: `NavLink` derives `aria-current`
from its own exact-path matching and overrides the prop, which stripped the
attribute on exactly the routes the resolver considers active. Two competing
sources of truth; the resolver wins.

Prefix matching is segment-aware, because `/report` and `/reports` are different
modules and a bare `startsWith` would light up the wrong one.

Verified in the browser at every stage — the 3 px indicator is painted
(`rgb(53, 188, 216)`) with exactly one active row throughout, including after a
refresh on an internal workflow URL, and Simulation History keeps the indicator
when a stored run is opened directly.

### Route render check

All nine routes verified to render real content after the session check
resolves, with no crash and no page error:

```
/start 1486 · /demo 5422 · /history 1335 · /compare 853 · /projects 912
/dashboard 3671 · /ai-co-designer 2083 · /assessments 1656
/workflow/disease 2338          (characters of rendered text)
```

Note that `ProtectedRoute` renders "Restoring session…" while `/auth/me` is in
flight. That is a legitimate transient state, not a blank page, and any check
must wait for `[data-testid=session-checking]` to detach before measuring.

---

## 10. Files

### Created — backend

`app/demo/{__init__,scenarios,seeding}.py` ·
`app/db/workspace_models.py` ·
`app/schemas/workspace.py` ·
`app/services/workspace_service.py` ·
`app/api/routes/workspace.py` ·
`app/api/static_frontend.py` ·
`scripts/demo_data.py` ·
`tests/test_workspace_api.py` · `tests/test_static_frontend.py`

### Created — frontend

`src/pages/demo/{DemoWorkspace.tsx,DemoWorkspace.css}` ·
`src/pages/workspace/{HistoryPage,ComparePage,ProjectsPage,RunDetailPage}.tsx` ·
`src/pages/workspace/{report.ts,WorkspacePages.css}` ·
`src/shell/{ErrorBoundary.tsx,ErrorBoundary.test.tsx}` ·
`src/api/client.test.ts` · `src/auth/SessionExpiry.test.tsx` ·
`src/workflow/DemoWorkspace.test.tsx` · `walkthrough.mjs`

### Created — docs

`docs/MODULE_INVENTORY.md` · `docs/INTEGRATION_SLICE.md` (this file)

### Materially changed

`app/db/auth_session.py` (register workspace models) ·
`app/vertical_slice.py` (workspace router, SPA serving, `/api` descriptor) ·
`app/core/config.py` (`serve_frontend`, `frontend_dist_path`) ·
`src/api/{types.ts,client.ts}` (workspace client, `detail` normalisation,
401 hook, same-origin default) ·
`src/auth/AuthContext.tsx` (401 handling, `sessionExpired`) ·
`src/pages/LoginPage.tsx` (sign-out notice) ·
`src/workflow/WorkflowContext.tsx` (`loadScenario`, `session.demo`) ·
`src/pages/workflow/ResultsStage.tsx` (save-run, demo banner) ·
`src/App.tsx` (routes) · `src/main.tsx` (error boundary) ·
`src/shell/navigation.ts` (statuses, Demo entry) ·
`src/design-system/{components.tsx,components.css}` (dialog fix) ·
`vite.config.ts` (same-origin proxy) · `.env`, `.env.example`

---

## 11. Deployment — one origin

The interface and the API **must** share an origin. This is a correctness
requirement, not a packaging preference: the session cookie is `SameSite=Lax`,
and splitting them across sites breaks sign-in exactly as described in §9.

```powershell
# 1. build the interface
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm run build                      # -> frontend/dist

# 2. serve both from the backend
cd ..\nanobio_studio_backend
$env:SERVE_FRONTEND = "true"
python -m uvicorn nanobio_studio.app.vertical_slice:app --host 0.0.0.0 --port 8000
```

One origin then answers everything:

| Path | Served by |
|---|---|
| `/` and any client-side route (`/demo`, `/history/7`, …) | the built SPA |
| `/api/v1/...`, `/health`, `/ready`, `/docs` | FastAPI |
| `/api` | the service descriptor (it moves off `/` when the SPA is served) |
| `/assets/...` | hashed build assets |

| Setting | Value | Why |
|---|---|---|
| `SERVE_FRONTEND` | `true` | Enables SPA serving. **Off by default**, so API-only development and the test suite are untouched |
| `FRONTEND_DIST_PATH` | `frontend/dist` | Relative paths resolve against the repository root |
| `SESSION_COOKIE_SECURE` | `true` **behind HTTPS** | Already env-driven; must be set in any real deployment |
| `SLICE_CORS_ORIGINS` | *(unused)* | Inert in a same-origin deployment |

A missing build is **not fatal** — the backend logs it and serves API-only,
because refusing to boot over an absent frontend would be a poor trade.

**The rule that must not be broken:** an unknown API path returns **JSON 404,
never HTML**. The typed client parses every response as JSON, so an SPA fallback
that swallowed `/api/v1/nope` would turn every genuine API error into "returned
a response that was not JSON" and hide the real cause. `tests/test_static_frontend.py`
asserts this across four path shapes.

A reverse proxy (nginx, Render, Cloudflare) in front of one origin is an equally
valid arrangement; the requirement is one origin, not this specific mechanism.

---

## 12. Known limitations

1. **Reports are plain text.** No PDF, CSV or JSON export.
2. **Local persistence is SQLite.** Same declarative models as PostgreSQL; only
   `AUTH_DATABASE_URL` changes. **Alembic migrations are not written for the new
   tables** — `create_all` bootstraps them, which is not acceptable for
   production.
3. **Design drafts remain browser-local.** Only *completed runs* are
   server-stored. Server-side draft persistence is a follow-up.
4. **No pagination.** Run listing is capped at 500.
5. **Demo templates are global.** Seeding is admin-only, but a template edit
   affects every user.
6. **The walkthrough leaves 2 demo runs** in the development database. Clear them
   with `demo_data.py reset --confirm`.
7. **A `walkthrough_user` account exists** in the development auth database,
   created for the Playwright run.
8. **Browser verification used Playwright, not the Chrome extension**, which was
   not connected in this session.
