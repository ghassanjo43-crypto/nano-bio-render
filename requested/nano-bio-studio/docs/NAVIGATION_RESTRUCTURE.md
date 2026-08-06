# Navigation and startup restructure

Scope: information architecture, navigation, routing and workflow entry points.

**No scientific equation, calculation, stored result or engine behaviour was
changed by this work.** The engines, their versions, their inputs and their
outputs are byte-for-byte what they were before it. The 1000-test backend suite
— which includes the golden-vector equivalence tests for the PK model and the
design impact score — passes unchanged.

---

## 1. What changed

### The startup experience

After sign-in the user lands on `/start`, which asks **"How would you like to
begin?"** and offers three pathways:

| Card | Primary action | Continues at |
|---|---|---|
| Patient-Specific Assessment | Upload Medical Report | `/report` |
| Research & Nanoparticle Design | Start Research Study | `/start/research` |
| Demo & Training Workspace | Browse Demo Scenarios | `/demo` |

Each card states its purpose, the journey it leads through, and its verified
status — read from the same navigation registry that drives the sidebar, so a
card cannot claim more than the module itself does.

The research pathway has a second level (`/start/research`) offering nine
research purposes. Purposes whose engines are not connected are **disabled and
labelled**, not hidden.

### Renames

| Before | After |
|---|---|
| Start New Design | Start New Study |
| Design Workflow | Studies (as a workspace section) |

### The sidebar

Five groups: **START**, **WORKSPACE**, **SCIENTIFIC TOOLS**, **INTELLIGENCE**,
**SYSTEM**. Administration remains admin-only.

Every entry carries a verified `ModuleStatus`. Access to a menu entry does not
imply scientific availability: a module can be reachable and still say, on its
own page, that its engine is not connected. Hiding an unbuilt module would make
the gap invisible rather than honest.

### Routes

| Route | Renders |
|---|---|
| `/start` | Pathway chooser |
| `/start/research` | Research purpose |
| `/start/session` | Drafts gate (the previous single entry point) |
| `/home` | Platform status (`/dashboard` redirects here) |
| `/studies`, `/studies/:id` | My Studies |
| `/patient-assessments` | Patient assessment studies |
| `/research-designs` | Research design studies |
| `/history`, `/history/:id` | Simulation History (`:id` still resolves) |
| `/evidence` | Evidence & Validation |
| `/protocol`, `/experimental-planning`, `/ml-training`, `/help` | Honest placeholders |

`/dashboard` and `/history/:id` are **redirects and aliases, not removals** — no
existing link or bookmark breaks.

---

## 2. One workflow, three pathways

`/workflow/*` is shared by all three pathways. The same four steps run whether
a study began from a report, a research question or a demonstration. **No
scientific workflow was duplicated to fill the menu.**

This creates one design problem worth stating plainly: the route alone cannot
decide which sidebar entry is active. `/workflow/design` belongs to Patient
Assessments, Research Designs or Demo Workspace depending on the study — not on
the URL. So `activeNavKeyForPath(path, { pathway })` takes the study's pathway
as an input:

```ts
if (isWithin(path, '/workflow')) return navKeyForPathway(context.pathway);
```

Without this, a patient assessment mid-workflow would highlight "Research
Designs", which would simply be untrue.

Active state is resolved **once per render**, centrally, in
`src/shell/navigation.ts`. There are no exact-path checks scattered across
components. The sidebar and the breadcrumbs both call the same resolver, so
they cannot disagree.

---

## 3. The unified study record

`StoredRun` gained four columns:

| Column | Meaning |
|---|---|
| `pathway` | `patient_assessment` / `research_design` / `demo_scenario` |
| `research_purpose` | Second-level purpose, for research designs |
| `inputs_are_synthetic` | True for demonstrations |
| `report_assessment_id` | Opaque integer link to a report; **not** a foreign key |

### Why `origin` was kept

`RecordOrigin` stays the two-value `USER`/`DEMO` flag. `reset_demo_data` scopes
its deletion on it, and that safety property is already tested. Rather than
overload `origin` with a third value and weaken it, `pathway` carries the richer
fact and `origin` is **derived from it on write**:

```python
if pathway is StudyPathway.DEMO_SCENARIO:
    is_demo = True
```

A demonstration cannot escape the reset by claiming not to be one.

### Why the report link is not a foreign key

Deleting a report must not cascade into deleting the study built from it, and
the study must not keep the report alive past its retention period. The link is
an opaque integer that carries no name, date of birth or other identifier.

---

## 4. Privacy

No patient name or other identifier appears in a breadcrumb, URL, browser title,
log or analytics payload. This is enforced structurally, not by convention:

* `StudyContext` — the only type `StudyContextBar` accepts — has no field that
  could hold an identifier. `crumbsForPath` never includes the study name, and a
  test asserts this with a name deliberately containing an MRN.
* `pageTitleForPath` returns a static route title. Study names never reach it.
* Route parameters are opaque integer ids.
* `StoredRun` has no `patient_name`, `date_of_birth`, `mrn` or `report_text`
  column. A test asserts their absence, so no code path can add one silently.
* The study name **is** shown in the on-screen context header, because the user
  chose it and needs to see which study they are in. It is never persisted to a
  title, URL or log.

The synthetic-only restriction on report upload is **unchanged**. It remains in
force until the security, privacy, retention and deletion safeguards for
identifiable reports are implemented and verified.

---

## 5. Database migration

`Base.metadata.create_all` creates missing *tables* but never alters an existing
one, so a development database predating these columns would fail with an opaque
`no such column` error. `app/db/migrations.py` adds them in place at startup:
additive only, idempotent, never dropping, renaming or retyping.

This is a **deliberate interim measure**. Proper Alembic migrations remain a
prerequisite for production and are still tracked as a known limitation.

### A defect found and fixed during this work

The first version of that module compared `origin` against the enum **value**
(`'demo'`). SQLAlchemy's `Enum(..., native_enum=False)` persists the enum
**member name** (`'DEMO'`). The comparison therefore matched nothing and failed
*silently*: four demonstration runs in the development database were backfilled
as research designs.

Three things were wrong, and all three are fixed:

1. The migration literals now use member names.
2. A `REPAIRS` pass corrects rows the defective version mislabelled. It is
   idempotent and scoped to demo-origin rows, so it can never touch user work.
   It ran on the development database and repaired 4 rows, logged at startup.
3. **The test was the root cause.** It built its "legacy" fixture table by hand
   using assumed lowercase values, so it agreed with the bug. It now uses the
   spelling SQLAlchemy genuinely writes, and a separate test pins that storage
   format directly so the assumption cannot drift again unnoticed.

---

## 6. Verification

| Check | Result |
|---|---|
| Backend suite | **1000 passed** |
| Frontend suite | **296 passed** |
| TypeScript (strict, `noUncheckedIndexedAccess`) | clean |
| Production build | succeeded |
| `nav-walkthrough.mjs` | **PROBLEMS: none** |
| `walkthrough.mjs` (integration) | **PROBLEMS: none** |

The navigation walkthrough drives the live app and checks, mechanically:

* the startup heading and exactly three pathway cards;
* all five sidebar groups and the renamed entries, and the **absence** of the
  old "Start New Design" / "Design Workflow" labels;
* exactly one active indicator on every screen, surviving every workflow stage;
* breadcrumbs routing through the pathway that owns the study;
* legacy links (`/dashboard`, `/history`) resolving rather than 404ing;
* no identifier in the browser title, URL or `localStorage`;
* every sidebar entry keyboard-reachable;
* no horizontal overflow at 1440px, 834px and 390px.

Screens captured to `docs/screenshots/nav-*.png` at all three widths.

### One robustness fix

A record from an older backend carries no pathway. The lists and the context
header previously indexed a lookup table with it directly, which would render
`undefined` or throw. They now report **"Not recorded"** — the honest answer.
TypeScript cannot catch this: the value crosses the network as `unknown`.

---

## 7. Not done, recorded not fixed

* **No Alembic migrations.** The additive module is an interim measure.
* **The scientific blockers B1–B6 are untouched** by this work. In particular
  the assessment engines still have disease profiles for only two of five
  indications, and no model on this platform has been validated against
  experimental or clinical outcome data.
* **OCR remains unavailable.** Scanned reports are detected and reported as
  unreadable; they are not read.
* **Nothing was pushed or deployed.**
