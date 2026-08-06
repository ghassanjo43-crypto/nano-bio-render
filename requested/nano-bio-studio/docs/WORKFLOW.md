# Scientific Design Workflow

**Created:** 2026-07-30
**Scope:** Restructure of the React application around the legacy Streamlit
scientific sequence.
**Preserved unchanged:** backend, authentication, roles, HttpOnly cookie
architecture, the scoring API contract, and every scientific calculation.

> **Note on the reference material.** No screenshots arrived with the request —
> the message contained text only. The sequence and required fields were instead
> taken from the legacy source itself, which is definitive:
> `pages/0_Disease_Selection.py`, `pages/1_Design_Parameters.py`,
> `pages/2_Run_Simulation.py` and `data/disease_drug_mapping.py`.

---

## 1. Sequence

After login the user lands on the **design session gate** (`/start`), not a
dashboard.

```
/login  →  /start ──┬─ Resume current design
                    ├─ Start a new design
                    └─ Open a saved design
                            │
              /workflow/disease   Step 1 — Disease & Therapeutic Selection
                            │     indication → subtype → therapeutic agent
              /workflow/design    Step 2 — Nanoparticle Design Parameters
                            │     core · surface · targeting · stability
              /workflow/review    Step 3 — Review & Run Simulation
                            │     full session review, then execute
              /workflow/results   Results & Scientific Assessments
```

The Dashboard still exists at `/dashboard` as **Overview** in the sidebar, but it
is no longer the mandatory first screen and no longer the primary entry point.

---

## 2. Clinical data source

`src/workflow/diseaseData.ts` is **generated** from
`data/disease_drug_mapping.py`, so the React workflow offers exactly the same
options as the legacy application: **5 indications, 19 subtypes**, each with its
own therapeutic list, plus epidemiology and unmet-need text. No disease, subtype,
drug or statistic was invented, added or edited.

Selecting a different indication clears the subtype and drug, so an invalid
disease/drug pair cannot be carried forward. Only drugs associated with the
chosen subtype are offered.

---

## 3. Connected, stateful session

`src/workflow/WorkflowContext.tsx` holds one session spanning all stages:

| Behaviour | Implementation |
|---|---|
| Selections preserved forwards and backwards | Single session object; steps read and write the same state |
| Required fields gate progress | `step1Complete` / `step2Complete` drive button state **and** route guards |
| Deep links cannot skip ahead | `WorkflowLayout` redirects to the first incomplete step |
| Progress indicator | Persistent rail with complete / current / **unavailable** states |
| Save Draft | Real browser-local drafts, listed on the session gate |
| Stale results flagged | Editing inputs after a run shows a "re-run" warning |

### Storage

Drafts live in `localStorage` and contain **design parameters only** — disease,
subtype, drug and formulation values. They never contain a session token,
password or credential; authentication continues to rely solely on the HttpOnly
cookie that JavaScript cannot read. A test asserts no credential-like string ever
reaches client storage.

Drafts are **browser-local, not server-persisted**, and the UI says so in three
places. The "Open a saved design" list shows only drafts the user actually saved;
when empty it states plainly that it is *"never populated with examples"*.

---

## 4. Where the verified endpoints connect

**Step 3, on "Run Simulation"** — the scientifically appropriate point, matching
the legacy `2_Run_Simulation.py` position. Two migrated engines are called there,
as two independent requests with two independent outcomes.

### 4.1 Design impact score — `POST /api/v1/design/score`

Called with exactly the fields the user supplied; blank optional fields are
omitted so the engine applies its own documented defaults. **The calculation is
untouched** — the live walk-through returns `87.52`, the canonical
`compute_impact` value.

### 4.2 Pharmacokinetic simulation — `POST /api/v1/pk/simulate`

Added 2026-07-31. Runs the legacy two-compartment model
(`utils/pk_model.py`) verbatim, bit-exact against a direct call. Full detail in
**`docs/PK_SLICE.md`**.

Its five scientific inputs — dose and the four first-order rate constants — are
collected **on Step 3**, because they are simulation inputs rather than
formulation properties, the same division the legacy simulation page made.
Step 2 is unchanged.

**Nothing is pre-filled, and the model is not called until every required input
is present and valid.** The legacy page silently merged in a defaults dictionary,
so a user could run a "simulation" whose kinetics they never chose; here an
incomplete set produces an honest "did not run" state instead.

The two calculations are reported in **separate cards with separate versions**
(`design-impact-adapter-0.1.0` and `pk-two-compartment-adapter-0.1.0`) and are
never combined into one figure.

### What the PK engine does and does not produce

| Output | Produced? |
|---|---|
| Concentration–time profile, peak concentration and T_max, AUC, half-life (nullable), tissue accumulation and peak ratios | **Yes** |
| Calculation version, normalized inputs, assumptions, warnings, limitations, validation status | **Yes** |
| **Clearance**, volume of distribution, bioavailability, AUC(0–∞) | **No** — the model has no volume term. Their absence is returned explicitly in `quantities_not_produced` and displayed as such, never derived |

Charts are drawn from the returned arrays alone, and the exact values are listed
beside them, so the chart is never the only way to read a number. No clinical
interpretation is offered — the legacy prose ("excellent targeting efficacy",
"may need PEGylation") is not reproduced, because the model does not support
those conclusions.

### What deliberately does NOT run

The review step and the results page both state this before and after execution:

| Stage | Status | Behaviour |
|---|---|---|
| Design impact score | **Operational** | Runs; real result shown |
| Pharmacokinetic simulation | **Operational, gated** | Runs only when all required inputs are supplied. Otherwise not run, and no curve, half-life or AUC is produced or displayed |
| Scientific assessments | Calibration required | **Not run.** No disease-fit, safety or regulatory output |
| Molecular visualisation | Not yet operational | Not run |

Nothing is fabricated to fill the gap.

### An honesty point worth stating

**Neither** migrated engine accepts a disease.
`core.scoring.compute_impact` takes physicochemical parameters only, and the PK
model takes a dose and four rate constants only. So the therapeutic selection is
recorded and displayed for traceability, but **changes neither result** — the
disease-specific engines that would consume it are the ones not yet migrated.
This is stated on Step 1, on Step 3 and again on the results page, rather than
letting the sequence imply a disease-dependent result that does not exist.

The PK model also does not infer its rate constants from the formulation entered
in Step 2. The profile reflects the constants the user typed, not the particle —
stated on Step 3 and in the API's own limitations.

---

## 5. Sidebar

Four groups, role-aware, with honest status badges:

**Research** — Design Workflow · Overview · Simulations · Results · Compare Designs
**Scientific Analysis** — Scientific Assessments · Molecular Visualisation · AI Co-Designer
**Workspace** — Projects · Simulation History · Reports
**Platform** — Administration *(admin only)* · Settings

Labels: Operational · Limited prototype · Migration in progress · Calibration
required · Not yet operational. **Administration is not rendered at all for
non-admin roles**, and the backend enforces it independently.

---

## 6. Verification

Current, after the PK slice (2026-07-31):

| Check | Result |
|---|---|
| Frontend tests | **114 passed** (38 new PK tests) |
| TypeScript (strict) | **clean** |
| Production build | **succeeded** |
| Backend suite | **735 passed** (122 new PK tests) |
| Golden-vector scientific suite | passes unchanged |
| Horizontal overflow (desktop + mobile) | **none** (unchanged by the PK slice) |

At the workflow-restructure milestone the figures were 75 frontend / 613 backend.

### Live end-to-end walk (Playwright)

```
landed on:                        /start
header title:                     Step 1 — Disease & Therapeutic
delivery gauge:                   87.52        ← canonical value
size preserved after back-nav:    118          ← state preservation
saved drafts listed:              1            ← draft save/resume
review echoes selection:          Liver Cancer (HCC), AFP-high HCC, Sorafenib, 118
PROBLEMS:                         none
```

### Test coverage added

Landing on the session gate (not a dashboard) · start-new · honest empty saved
list · resume offered only when a session exists · Step 1 gating · deep-link
redirects for steps 2 and 3 · advancing through all three steps · locked steps
marked unavailable · selection preserved on back-navigation · design values
preserved · drug cleared when disease changes · only subtype-valid drugs offered ·
review echoes disease/subtype/drug/configuration · review states what will not
run · run calls the real endpoint · payload contains only supplied fields ·
failure produces no fallback number · results list the not-run stages with no
numbers · disease-independence stated · draft save/resume · no credential in
storage · sidebar leads with the workflow.

---

## 7. Known limitations

1. **Drafts are browser-local.** Clearing site data loses them; they do not
   follow the user to another machine. Server-side projects need the persistence
   layer.
2. **No server-side design history**, so "Simulation History" remains a
   placeholder rather than reading real records.
3. **The therapeutic selection has no effect on either computed result** until
   the assessment engines are migrated (§4). The PK model additionally does not
   infer its rate constants from the Step 2 formulation.
4. **Draft conflict resolution is last-write-wins** within a browser; there is no
   multi-device merge.
5. The legacy `1_Design_Parameters.py` exposes 23 fields; the workflow currently
   exposes the 17 the migrated API accepts. The remaining legacy fields
   (`Material`, `Target`, `EncapsulationMethod`, `PorosityLevel`, `PoreSize`,
   `Receptor`, `ReleaseProfile`) feed engines that are not migrated and are not
   collected, rather than being collected and silently discarded.

---

## Appendix — files

### Workflow restructure

**Created:** `src/workflow/{diseaseData.ts, WorkflowContext.tsx, steps.ts, Workflow.test.tsx}`,
`src/pages/workflow/{WorkflowLayout, SessionStartPage, Step1Disease, Step2Design, Step3Review, ResultsStage}` + CSS

**Materially changed:** `src/App.tsx` (routing), `src/shell/navigation.ts`
(workflow-first menu, path resolution), `src/shell/AppShell.tsx` (page titles),
`src/pages/LoginPage.tsx` and `src/auth/guards.tsx` (post-login destination),
`src/pages/DashboardPage.tsx` (CTA), `src/shell/AppShell.test.tsx` (retargeted)

**Screenshots:** `docs/screenshots/wf-*.png`

### PK slice (2026-07-31)

**Created:** `src/pages/workflow/{pkSchema.ts, PKPanel.tsx, PKPanel.css}`,
`src/charts/{ConcentrationTimeChart.tsx, ConcentrationTimeChart.css}`,
`src/workflow/PkSimulation.test.tsx`

**Materially changed:** `src/api/{types.ts, client.ts}`,
`src/workflow/WorkflowContext.tsx` (PK session state and result),
`src/pages/workflow/{Step3Review.tsx, Step3Review.css, ResultsStage.tsx}`,
`src/shell/navigation.ts` (simulation summary), `src/workflow/Workflow.test.tsx`

Full detail, including the backend files and the equivalence evidence, is in
**`docs/PK_SLICE.md`**.
