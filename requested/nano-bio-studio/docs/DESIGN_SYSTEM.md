# NanoBio Studio — Frontend Design System & UI Redesign

**Created:** 2026-07-30
**Scope:** Comprehensive UI/UX redesign of the React + TypeScript frontend.
**Preserved unchanged:** backend, authentication, routes, permissions, HttpOnly
cookie architecture, the scoring API contract, and every scientific calculation.

> **Scientific positioning.** Every value the interface displays is a
> computational research-planning result: not experimentally validated, not
> clinically validated, not a regulatory approval prediction, diagnosis or
> treatment recommendation.

---

## 1. Design language

A deep navy foundation (authority, laboratory instrumentation) with a restrained
teal-cyan accent (biological, aqueous). Accent colour is used sparingly so that
scientific data, not chrome, carries the eye.

| Decision | Rationale |
|---|---|
| Tight, low-spread shadows | Scientific tools should read as precise, not soft |
| 14 px body text, tabular numerals | Dense data UI; figures align in columns |
| 8 px base radius | Modern without the "bubbly" look of large radii |
| No glassmorphism beyond one header blur | Legibility over decoration |
| Molecular motifs only on login and dashboard hero | Restraint; never behind data |

### Token layers (`src/design-system/tokens.css`)

Colour (navy/teal/ink ramps + semantic success/warn/danger/info), typography
(9-step scale, 4 weights, 3 line-heights), spacing (10-step), radii (6), elevation
(4), motion (3 durations + one easing), layout (sidebar/header/content metrics)
and z-index. **No component hard-codes a hex value or pixel spacing.**

`prefers-reduced-motion` collapses every duration to zero at the token level, so
the whole application respects it without per-component handling.

---

## 2. Component library (`src/design-system/components.tsx`)

Strictly typed, composable primitives:

`Button` (4 variants × 3 sizes, loading state, icon slots) · `Card` (header,
subtitle, actions, flush, accent) · `Badge` (6 tones, optional status dot) ·
`Alert` (4 tones) · `Tooltip` + `InfoHint` · `TextField` · `SelectField` ·
`PasswordField` · `ChipGroup` · `Skeleton` / `SkeletonBlock` · `EmptyState` ·
`Tabs` (roving-tabindex keyboard nav) · `DataTable` · `Dialog` · `Breadcrumbs` ·
`SectionHeading`.

Charts (`src/charts/ScoreVisuals.tsx`): `ScoreGauge`, `ComponentBars`,
`ComponentRadar` — hand-built SVG, no chart dependency.

### Accessibility built in, not bolted on

* `<label>` contains **only** the field name; units, required/optional chips and
  the info hint sit beside it, so the accessible name stays clean.
* Errors link to inputs via `aria-describedby` and `aria-invalid`.
* Status is conveyed by text **and** a dot, never colour alone.
* One consistent `:focus-visible` treatment; never removed.
* Skip link is the first tab stop on every authenticated page.
* Tabs implement arrow/Home/End keyboard navigation.
* Every chart carries `role="img"` with a full text description, **and** the
  numeral is rendered as visible text — the chart is never the only way to read
  a value.

---

## 3. Application shell

**Sidebar** — four labelled groups (Research · Scientific Analysis · Workspace ·
Platform), line icons, active-route indicator, status dots for non-operational
modules, expanded/collapsed modes with tooltips when collapsed, role-aware
visibility (Administration is not rendered for non-admins), and an off-canvas
drawer with scrim below 900 px.

**Header** — breadcrumbs + current page title, live API status (polled every
30 s), research-use badge, and a user menu with avatar, name, role, profile link
and sign-out. Sign-out goes through a confirmation dialog. **No control is
present that does nothing**: there is no notifications bell and no project
selector, because neither is implemented.

---

## 4. Screens

### Login
Split-screen: value proposition over a subtle nanoparticle motif on the left,
authentication panel on the right; single-column with the motif dropped below
960 px. Show/hide password, per-field validation, distinct states for invalid
credentials, rate limiting and API-unavailable, plus the research-use notice.
**No default credentials are displayed** — that removal from the security
containment work is preserved and asserted by a test.

### Dashboard
Hero with personalised welcome and primary action; available vs unavailable
modules derived from the navigation model; platform migration progress;
scientific validation status; "how a calculation works" onboarding.
**No invented counts, rates, projects, simulations or activity.** Recent activity
renders an onboarding empty state because no activity store exists.

### Nanoparticle Design
Converted from one long form into a **five-step workflow**: Core properties →
Surface characteristics → Targeting configuration → Stability & release →
Review & calculate. Inputs persist across navigation. Every field carries units,
an inline scientific definition in a tooltip, explicit required/optional marking
and the canonical default that applies when left blank. The review step shows
exactly what will be sent versus what the engine will default.

Field definitions live in one declarative schema (`pages/design/schema.ts`) that
drives rendering, validation, the review summary **and** the API payload, so the
four cannot drift apart.

### Results
Three radial gauges (Delivery / Toxicity / Cost) with the numeral inside, then
tabs for Breakdown (comparison bars + component table), Profile (radar), Inputs
(normalised values) and Warnings. Provenance block shows model version,
scientific source, prediction basis, evidence level and validation status;
limitations are listed in full. Next actions: edit the design or recalculate.

**Never called the "Overall Score".** The panel states explicitly that no single
composite score is produced.

### Placeholders
Five honest status labels: Operational · Limited prototype · Migration in
progress · Calibration required · Not yet operational. Each page states the
module's purpose, its planned workflow, a status panel ("Scientific output: None
produced"), and a link to a module that does work. The AI Co-Designer
additionally explains that the removed placeholder candidates will not return.

---

## 5. Responsive behaviour

| Width | Behaviour |
|---|---|
| ≥ 1400 px | Full sidebar, two-column design workflow, sticky results |
| 1100–1400 px | Tightened gutters, narrower workflow column |
| 900–1100 px | Sidebar auto-collapses to icons |
| ≤ 900 px | Off-canvas drawer, single-column pages, stacked result gauges |
| ≤ 560 px | Breadcrumbs hidden, step labels abbreviated, review rows stacked |

Verified with an automated horizontal-overflow check at 1680 / 1366 / 900 /
390 px on login, dashboard, design workflow and results. **Result: no overflow at
any width.**

---

## 6. Defects found during visual review and fixed

Screenshots were inspected, not merely captured. Four real defects were found and
corrected:

| Defect | Cause | Fix |
|---|---|---|
| **Form labels invisible** on login and design | `--ink-800` was written as `#16273400` — an 8-digit hex whose `00` alpha makes it fully transparent. `var(--ink-800, fallback)` does not help, because the variable *is* defined. | Corrected to `#162734`; redundant fallbacks simplified |
| **Horizontal overflow at 390 px** on the result page (449 px > 390 px) | Grid children default to `min-width: auto`, so a long unbreakable default-value string forced the page wider than the viewport | `min-width: 0` on grid children, `overflow-wrap: anywhere` on values, review rows stack below 760 px |
| **Brand text ran together** in the mobile drawer ("NanoBio StudioRESEARCH PLATFO…") | The drawer media query set `display: block`, collapsing the brand's flex column | Drawer keeps `display: flex` for the brand block |
| **"Welcome, Platform"** | Greeting split the display name on the first space, mangling "Platform Administrator" | Use the full display name |

---

## 7. Verification

| Check | Result |
|---|---|
| TypeScript type check (`tsc --noEmit`, strict) | **clean** |
| Frontend tests (`vitest`) | **51 passed** |
| Production build | **succeeded** — 235 kB JS / 74.8 kB gzip, 51.6 kB CSS / 9.3 kB gzip |
| Backend suite | **613 passed** |
| Golden-vector scientific suite | **440 passed** |
| Horizontal overflow, 4 viewports | **none** |
| Live end-to-end (Playwright) | Login → dashboard → workflow → **87.52** rendered |

`87.52` is the canonical `compute_impact` value — the redesign changed
presentation only.

### Test coverage retained

Authentication (login success/failure/rate-limit/API-down), session restoration
and expiry, logout, unauthenticated redirection, role-based admin access, menu
visibility by role, navigation to the real scoring page, design-form validation,
successful score rendering, API-error and empty states, absence of fabricated
dashboard and AI results, and no `localStorage`/`sessionStorage` use.

**Tests were retargeted, not weakened.** Their assertions are unchanged; only the
selectors moved with the markup. Three selector improvements were needed because
the richer UI made loose queries ambiguous — for example the info-hint button's
`aria-label` also matched a loose field-name regex, so those queries now use
`getByRole('textbox', { name: … })`.

---

## 8. Architecture

```
src/
  design-system/   tokens.css · base.css · components.tsx · components.css
  charts/          ScoreVisuals.tsx · ScoreVisuals.css
  shell/           AppShell.tsx · AppShell.css · navigation.ts · Icon.tsx
  auth/            AuthContext.tsx · guards.tsx
  api/             client.ts · auth.ts · types.ts
  pages/
    LoginPage · DashboardPage · ModulePlaceholder · NotFoundPage · UnauthorizedPage
    design/        DesignPage · ResultPanel · schema.ts
```

Strict TypeScript throughout. **No `any`.** `navigation.ts` is the single source
of truth for menu structure and module status, consumed by the sidebar, the
dashboard and the placeholder pages, so they cannot contradict one another.

### One API-surface change (frontend only)

`api/types.ts` previously declared only 6 of the 17 request fields the backend
already accepted. It now mirrors the backend Pydantic schema in full, which is
what allows the workflow to expose surface, targeting and stability parameters.
**No backend change was made** — the endpoint already accepted these fields.

---

## 9. Known limitations

1. Charts are hand-built SVG — sufficient for the current three components, but a
   charting library will be needed for time-series PK curves.
2. TypeScript types are hand-maintained against the backend rather than generated
   from OpenAPI.
3. No toast system yet: there are no genuine background events to announce.
4. No dark theme; tokens are structured to support one.
5. Unsaved design inputs are held in component state and are lost on a full page
   reload — the confirmation dialog warns about this before sign-out.
6. No linter is configured in this project; type checking plus tests are the
   current gate.
