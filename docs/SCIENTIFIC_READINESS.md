# Scientific Readiness Framework — Phase 1

**Status:** implemented and connected.
**Rules engine:** `readiness-rules-1.1.0`
**Data dictionary:** `data-dictionary-1.0.0`
**Dashboard:** `/scientific-readiness`

---

## 0. The disclaimer, first

> **Readiness is not accreditation.**
>
> Scientific readiness describes whether the information recorded for a study is
> sufficient and self-consistent for a given kind of analysis. It is **not**
> regulatory approval, **not** clinical validation, **not** scientific
> accreditation, and **not** evidence that any result is correct.
>
> **A study can be fully ready and still be scientifically wrong.**

This wording is not decoration. It lives in exactly one place —
`NOT_ACCREDITATION_NOTICE` in `app/science/statuses.py` — is returned by the API
on every assessment, and is rendered on the dashboard before any area result. A
test asserts it appears even when the assessment request fails, so a reader can
never see a partial page without it.

Readiness answers *"is there enough self-consistent information here to attempt
this?"* It does not answer *"is the answer right?"* Nothing in this framework
inspects a result for correctness, and nothing in it validates a model against
experiment.

---

## 1. Why the framework exists

Before this phase, a study could be carried all the way through the workflow
while most of its scientific inputs were assumed defaults, illustrative
placeholders, or numbers whose measurement conditions nobody had recorded. The
interface offered no way to tell the difference between a diameter measured by
cryo-TEM and one typed in to make a form submit.

Three specific failure modes motivated it:

1. **Completeness read as validity.** A filled-in form looked like a
   characterised material. Progress bars reward typing, not measuring.
2. **Provenance lost at entry.** A value arrived as a bare number. Its method,
   medium, pH, temperature and ionic strength — the things that decide whether
   two values can be compared at all — were never captured, so incompatibilities
   were undetectable in principle.
3. **One score hiding six situations.** A single "readiness" number let strong
   structural data mask absent biological evidence.

The framework addresses each directly, and the three design decisions in §2
follow from them one-to-one.

---

## 2. The three invariants

Everything else in this document is a consequence of these. Each is pinned by
tests in both suites.

### 2.1 A completeness percentage never satisfies a blocking requirement

A study can be **78% complete and BLOCKED**. The percentage and the status are
computed independently: the percentage measures how much of the relevant
dictionary has been populated; the status asks whether every *mandatory* field
is present, valid and mutually compatible. A missing blocking field blocks at
any percentage.

The dashboard renders both on the same card, and where a blocked area is ≥50%
complete it prints a sentence saying so in words, because a large number next to
a red badge is otherwise easy to misread as "nearly there".

```
Formulation assessment          [ Blocked ]
Completeness   78%  ████████████████░░░░
Evidence level E2 — computational prediction

This area is blocked despite being 78% complete. A completeness
percentage never satisfies a mandatory requirement.
```

### 2.2 Evidence level comes from records, not from completeness

Filling in more fields raises the percentage. **Only recorded experimental
evidence raises the evidence level.** A study of sixty assumed defaults is 100%
complete at E0.

The level for an area is the **weakest link** among its required fields, not an
average. One assumed default in a mandatory position holds the whole area at the
level that assumption supports. Averaging would let nine good measurements
conceal one fabricated one, which is the exact reading the framework exists to
prevent.

### 2.3 Six areas, assessed independently, with no combined score

There is deliberately **no overall number**. `ReadinessReport` has no
`overall_percent` and no `overall_status`, and a test asserts the attributes do
not exist so one cannot be added casually. A study may be ready to visualise and
nowhere near ready to model pharmacokinetically; a single figure would be false
in both directions.

---

## 3. The six readiness areas

| Area | Asks | Blocking / conditional / optional fields |
|---|---|---|
| `structural_visualization` | Can the particle be drawn to scale, with its real layers? | 3 / 5 / 3 |
| `formulation_assessment` | Is the formulation characterised well enough to assess? | 6 / 4 / 10 |
| `biological_targeting` | Is there evidence the targeting claim is grounded? | 5 / 11 / 7 |
| `pharmacokinetic_modelling` | Do the inputs match a reviewed model's domain? | 4 / 4 / 7 |
| `safety_assessment` | Is there enough to say anything about safety? | 5 / 2 / 6 |
| `cinematic_animation` | Is there enough structure to animate without inventing it? | 5 / 2 / 0 |

Each area returns its own status, percentage, evidence level, blocking issues,
warnings, incompatible inputs, assumptions in use, missing-data checklist and
recommended actions.

---

## 4. Vocabularies

### 4.1 Scientific status — how a value is known

Ten values, in `ScientificStatus`. The ordering below is by strength of claim.

| Status | Meaning |
|---|---|
| `MEASURED` | Measured on this material, with a recorded method. |
| `EXPERIMENTALLY_DERIVED` | Computed from measurements on this material. |
| `LITERATURE_DERIVED` | Taken from a cited source describing a comparable material. |
| `CALCULATED` | Derived deterministically from other recorded fields. |
| `COMPUTATIONALLY_PREDICTED` | Output of a model, not an observation. |
| `USER_SUPPLIED` | A person entered it; no method, source or conditions recorded. |
| `ASSUMED_DEFAULT` | A placeholder the platform or the user assumed. |
| `ILLUSTRATIVE` | Chosen to exercise the interface. Describes no real material. |
| `MISSING` | Not recorded. |
| `NOT_APPLICABLE` | Meaningless for this architecture. |

Two frozen sets do the real work:

```python
EVIDENCE_BEARING_STATUSES   = {MEASURED, EXPERIMENTALLY_DERIVED}
NON_CONTRIBUTING_STATUSES   = {ASSUMED_DEFAULT, ILLUSTRATIVE, MISSING}
```

`EVIDENCE_BEARING` is the *only* gate that can raise an evidence level.
Note what is absent from it: `LITERATURE_DERIVED` and
`COMPUTATIONALLY_PREDICTED` are legitimate and useful, but they are not
observations of *this* material. `USER_SUPPLIED` is absent too — a number
without a method is not evidence, however confident the person typing it was.

`NON_CONTRIBUTING` values score **zero** in the percentage. An assumed default
is not partial credit; it is the absence of information wearing a number.

### 4.2 Readiness status — what can be done

| Status | Meaning |
|---|---|
| `READY` | Every mandatory input present, valid and compatible. |
| `CONDITIONALLY_READY` | Usable, with stated assumptions or gaps. |
| `INSUFFICIENT` | Too little recorded to attempt this. |
| `BLOCKED` | A mandatory input is missing, invalid or incompatible. |
| `OUTSIDE_MODEL_DOMAIN` | No reviewed model covers this configuration. |

`BLOCKED` and `OUTSIDE_MODEL_DOMAIN` are kept apart on purpose, with different
labels and different tones. The first is fixable by recording data. The second
is not fixable by the user at all — no amount of data entry brings an
unsupported architecture inside a model's validated domain. Collapsing them
would imply the second is a form-filling problem.

### 4.3 Evidence level

The scale has **two halves**, and reading it as one gradient is the mistake it
is now built to prevent.

| Level | Half | Meaning |
|---|---|---|
| `E0` | basis | Illustrative only. |
| `E1` | basis | Literature-derived estimate. |
| `E2` | basis | Computational prediction **or unvalidated measurement**. |
| `E3` | validation | Retrospectively validated. |
| `E4` | validation | Prospectively validated in vitro. |
| `E5` | validation | Validated in vivo. |
| `E6` | validation | Supported by clinical evidence. |

**E0–E2 describe how a value came to exist.** A placeholder, a citation, a model
output, an instrument reading. **E3–E6 describe what was checked.** They assert
that a prediction was tested against an independent result or an experiment.

A measurement is the strongest *basis* there is, and it is still unvalidated —
so it sits at E2. That is not a demotion of measurement; it is a statement that
observing a material and validating a prediction about it are different acts.
Because both a model output and a measurement land there, E2's label names both.

#### How a basis level is reached, per required field

| Recorded status | Level |
|---|---|
| `MEASURED`, `EXPERIMENTALLY_DERIVED`, `CALCULATED`, `COMPUTATIONALLY_PREDICTED` | `E2` |
| `LITERATURE_DERIVED` | `E1` |
| `USER_SUPPLIED`, `ASSUMED_DEFAULT`, `ILLUSTRATIVE`, absent | `E0` |
| `NOT_APPLICABLE` | excluded from the assessment |

The area's basis level is `min()` over those, by the declared ordering — the
weakest link of §2.2. `_BASIS_LEVEL` is enumerated rather than defaulted, and a
test fails if a status is added to the vocabulary without a decision about what
it supports.

#### How a validation level is reached

Only from a **recorded validation of the matching kind**:

| `ValidationKind` | Supports | Requires |
|---|---|---|
| `RETROSPECTIVE_INDEPENDENT` | `E3` | A prediction compared, after the fact, against an independent reference dataset or a recorded outcome that was not used to produce it. |
| `PROSPECTIVE_IN_VITRO` | `E4` | The prediction registered *first*, then tested in a cell-based experiment. |
| `IN_VIVO` | `E5` | An animal study, with species, route, protocol and outcome recorded. |
| `CLINICAL` | `E6` | Formally supported clinical evidence. |

Each kind supports exactly one level. A record of one kind never establishes a
higher one.

#### E3–E6 are unreachable in Phase 1

There is **no Experimental Validation Registry**, so no validation record of any
kind can be stored, and therefore none can be read. `_recorded_validations()`
returns empty, and it is the only place in the engine a validation level may
originate — a test asserts no other function so much as names one. Every path
that assigns a level then passes through `cap_to_attainable_evidence_level()`,
so a future rule that computes E4 from something that is not a validation record
is held rather than published.

The single switch is `VALIDATION_REGISTRY_AVAILABLE`, and flipping it without
implementing the registry raises `NotImplementedError` by design: the capability
and the claim must land together.

**What this means in practice:** a study whose every required field is measured
by cryo-TEM, with a populated in-vivo evidence field, reports **E2**. Under
`readiness-rules-1.0.0` the same study reported E4 or E5. See §15.

Each area reports `evidence_level_rationale` naming the field that set the level
and why it is not higher, and `max_attainable_evidence_level`. The dashboard
renders the rationale beneath the level, so `E2` is never shown bare.

---

## 5. The data dictionary

`app/science/data_dictionary.py`, version `data-dictionary-1.0.0`, **60 fields**:

| Group | Fields |
|---|---|
| `identity` | 11 |
| `characterization` | 12 |
| `payload` | 11 |
| `biological` | 13 |
| `surface` | 6 |
| `pharmacokinetics` | 4 |
| `safety` | 3 |

Each `FieldDefinition` carries: id, label, definition, group, data type,
accepted units, valid range, choices, relevant measurement conditions, supported
statuses, per-area requirement, the condition under which a conditional field
applies, its compatibility rules, and a researcher note.

### 5.1 Ranges are definitional, never plausibility windows

A declared range is only ever a bound that would be **physically or
mathematically impossible** to violate: `0–100` for a percentage, `0–1` for a
polydispersity index, `0–∞` for a quantity that cannot be negative.

There is deliberately no "typical liposome is 80–150 nm" range anywhere. Such a
window would be an invented normative claim, and would flag genuinely unusual
but correct materials as errors. A test enumerates the dictionary and fails if
any field declares a non-zero lower bound or an upper bound outside
`{1, 100, ∞}`.

### 5.2 Measurement method classes

`MEASUREMENT_METHOD_CLASSES` maps a method to a family — DLS and NTA to
`scattering`, TEM/cryo-TEM/SEM/AFM to `microscopy`, and so on. This is what
makes §6.2's compatibility checks possible.

`method_class()` returns **`None` for an unrecognised method**, and callers
treat `None` as "cannot judge" rather than forcing a family. Guessing that an
unfamiliar technique is probably scattering would produce confident, wrong
incompatibility findings about methods the platform has simply never heard of.

---

## 6. The rules engine

`app/science/rules.py`. Deterministic, pure, and versioned as
`readiness-rules-1.0.0`. It takes a list of `ScientificRecord` and returns a
`ReadinessReport`. It reads no database, consults no clock beyond the timestamp
it stamps on the report, and has no randomness — the same records always produce
the same assessment, which is what makes a stored snapshot meaningful.

### 6.1 Structure

```
evaluate_study(records)
└── for each of the six areas: evaluate_area(area, records)
    ├── _check_architecture_model_match()
    ├── _check_measurement_compatibility()
    ├── _check_ligand_density()
    ├── _check_molecular_population()
    ├── _check_biological_evidence()
    ├── _absent_evidence_notes()
    ├── _validation_notes()      → what the data does NOT establish
    ├── _evidence_level()        → weakest basis, then recorded validations
    │   ├── _basis_level()               → never above E2
    │   ├── _recorded_validations()      → empty in Phase 1
    │   └── cap_to_attainable_evidence_level()
    └── _readiness_percent()     → weighted completeness
```

### 6.2 What the checks catch

**Architecture / model match**
`unsupported_architecture`, `bilayer_assumption_misapplied`,
`class_architecture_conflict` — e.g. a lipid-bilayer assumption applied to a
solid metallic particle, which has no bilayer to speak of.

**Measurement compatibility** — the checks that need §5.2's method families:

- `physical_diameter_from_scattering` — a DLS number recorded as a physical
  diameter. DLS measures a hydrodynamic diameter; the two are different
  quantities, not two measurements of one.
- `hydrodynamic_diameter_from_microscopy` — the same error mirrored.
- `hydrodynamic_smaller_than_physical` — physically impossible; the hydrodynamic
  diameter includes the solvation layer.
- `diameter_conditions_differ` — two diameters measured in different media, pH
  or ionic strength, being compared as though they were comparable.
- `distribution_basis_missing` — an intensity-, volume- and number-weighted mean
  of the same sample differ substantially; without the basis the number is
  ambiguous.
- `coating_exceeds_diameter` — geometrically impossible.

**Ligand density**
`ligand_density_unit_missing`, `ligand_density_ambiguous`, `footprint_missing`.
A bare "40%" has no denominator — by mass, by mole, or by surface coverage —
and those are different quantities. The engine **refuses** it rather than
picking one. Choosing a denominator would be inventing data.

**Molecular population**
`payload_molecular_weight_missing`, `payload_quantity_missing` — a molecule
count cannot be derived without both.

**Biological evidence**
`receptor_expression_missing`, `expression_unit_missing`,
`binding_assay_missing`.

**Validation** — two notes stating what recorded data does *not* establish:

- `measurement_is_not_validation` — fires where an area's required fields carry
  measurements. A measurement is an observation of the material, not a check of
  a prediction against an independent result, so it does not reach E3.
- `evidence_field_is_not_validation` — fires where an in-vitro or in-vivo
  evidence field is populated. That records the claim that an experiment exists;
  it does not record that a prediction was registered, tested against it, and
  found to hold. It does not raise the area to E4 or E5.

Both carry no `recommended_action`: there is no action a user can take today,
and offering one would imply the registry exists.

### 6.3 Absent evidence is reported as absent

`_absent_evidence_notes()` exists to enforce one distinction. When no cytotoxicity
evidence has been recorded, the report says so — and says explicitly that this
is **"not a finding that the effect is absent"**. No record is not a negative
result. A framework that let silence read as safety would be worse than no
framework.

### 6.4 The percentage

```python
_WEIGHT = {BLOCKING: 3.0, CONDITIONAL: 2.0, OPTIONAL: 1.0}

percent = 100 * (Σ weight of populated, contributing fields)
              / (Σ weight of all applicable fields)
```

- Fields whose condition does not apply are excluded from both sums, so a
  liposome is not penalised for lacking a metallic core's fields.
- A field whose status is in `NON_CONTRIBUTING` counts as **not populated**.
- The result is *completeness*, nothing more. It is not a confidence, not a
  quality score, and never a permission.

### 6.5 Status resolution

Order matters, and blocking conditions are evaluated **before** the percentage
is consulted:

```
1. OUTSIDE_MODEL_DOMAIN   if no reviewed model covers the configuration
2. BLOCKED                if any blocking issue or incompatible input exists
3. READY                  if percent >= 80
4. CONDITIONALLY_READY    if percent >= 40
5. INSUFFICIENT           otherwise
```

Steps 1 and 2 short-circuit. This is invariant 2.1 expressed in five lines.

The 80 and 40 thresholds are **conventions for describing completeness**, not
scientific findings. They separate "most of the relevant dictionary is
populated" from "some of it is". They can be changed without changing any
scientific claim — which is precisely why they are allowed to be round numbers,
and why they can never override steps 1 and 2.

---

## 7. Adding a rule

1. **Add or amend the fields** in `data_dictionary.py`. If the rule needs a
   value nobody records yet, the field comes first — a rule that reads a
   non-existent field silently never fires.
2. **Write the check** in `rules.py` as a function returning `Finding` objects.
   Classify each: `blocking_issues` stops the work, `incompatible_inputs` means
   two recorded values contradict each other, `warnings` is advisory, and
   `assumptions` surfaces something already in use.
3. **Give every finding a stable `code`.** The UI keys on it and snapshots
   store it; renaming one silently breaks historical comparison.
4. **Give it a `recommended_action`** wherever a user could act on it. A
   finding that only says "no" is a dead end.
5. **Bump `RULES_ENGINE_VERSION`** in `statuses.py`. Any change to what the
   engine concludes is a version change — snapshots record the version they
   were produced under, and that record is worthless if the version is stale.
6. **Test both directions**: that it fires when it should, and that it stays
   quiet when it should not. A rule that fires on everything is as useless as
   one that never fires.

Never let a new rule *raise* a readiness result on the basis of form
completeness. Rules may only add findings or hold an area back.

---

## 8. Persistence

### 8.1 `science_data_records`

One row per (study, field). Unique on `(study_id, field_id)`. Stores the value
as TEXT alongside its status, unit, measurement method, conditions (JSON),
citation, batch, date, laboratory, uncertainty, verification status and notes.

The value is TEXT because the dictionary — not the column type — defines what a
field means. Storing a diameter as REAL would silently discard `"<50"` or
`"100 ± 4"`, which is information.

`measured_on` is the exception: it is validated as a genuine ISO calendar date
before storage and normalised to `YYYY-MM-DD`, so the column holds one
unambiguous shape. A date is only useful for *comparing* records, and a column
mixing `2026-08-01`, `01/08/2026` and `last Tuesday` cannot be compared at all.
Reads stay tolerant — see §8.3.

### 8.3 Reads are tolerant, writes are strict

The two directions have different obligations, and conflating them is what made
one bad keystroke able to make a study permanently unopenable.

**Writing** goes through `parse_iso_date()`, which raises. Rejection happens at
the schema (422, naming the field) *and* in `upsert_record` (400), because the
service is also called directly by scripts, seeding and tests — a bad date must
not reach the column by a route that happens to bypass the schema. Only the
extended form `YYYY-MM-DD` is accepted: `date.fromisoformat` alone also takes
`20260801` and ISO week dates such as `2026-W01-1`, which resolves silently to
2025-12-29 — a different year from the one the typist meant.

**Reading** goes through `parse_stored_date()`, which never raises. It returns
`(date, unparsable_text)`. A row written before this validation existed may hold
anything, and a study must remain loadable, viewable and assessable whatever one
of its sixty dates says. The bad text is kept on the record as
`measured_on_raw`, surfaced in the API as `measured_on_unparsable`, and reported
by `validate_record` as a *warning* — so the user sees a correctable error
rather than a silent absence.

The reason this asymmetry is right: a study that raises on load cannot be opened
to correct the value that makes it raise. The framework exists to *show* what is
wrong with recorded data, which it cannot do from a stack trace.

### 8.2 `science_readiness_snapshots`

Immutable. Stores the full report **and the input records that produced it**,
plus the rules-engine and dictionary versions.

Keeping the inputs is the point: a historical snapshot is never recomputed under
current rules. Recomputation would make the record say what today's engine
thinks, not what was concluded at the time — which would defeat the entire
purpose of taking one.

---

## 9. Migration and startup

Additive and reversible-by-omission. Nothing is dropped, renamed or retyped, so
an older database is never damaged and a rollback is simply running the previous
code against the same file — the two new tables are ignored.

The startup path in `init_auth_db()` does three things in a deliberate order:

```python
pending = await tables_awaiting_creation(engine)   # observe, before creating
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)  # create
if pending:
    print(f"[nanobio] created new tables: {', '.join(pending)}")
applied = await apply_additive_migrations(engine)  # then add missing columns
```

`tables_awaiting_creation` and `apply_additive_migrations` are separate on
purpose. The migration function returns *the changes it actually made* and must
return `[]` once there is nothing left to do. It does not create tables —
`create_all` does — so having it report them both misstated what happened and
never stopped repeating, because nothing it did resolved the condition. (That
regression was introduced and caught during this phase; the split is the fix.)

`tables_awaiting_creation` reports **nothing on a brand-new database**, where
every table is absent and `create_all` builds the whole schema. It only speaks
when the older schema is already present and these tables are not — which is the
only case that constitutes an upgrade worth logging.

### 9.1 Existing studies

Studies saved before the framework existed have no records. Rather than showing
them as empty, `legacy_records_for_study()` derives records from their stored
design inputs:

| Legacy key | Field | Status |
|---|---|---|
| `size_nm` | `physical_diameter` | `USER_SUPPLIED` |
| `hydrodynamic_size_nm` | `hydrodynamic_diameter` | `USER_SUPPLIED` |
| `charge_mv` | `zeta_potential` | `USER_SUPPLIED` |
| `encapsulation_percent` | `encapsulation_efficiency` | `USER_SUPPLIED` |
| `pdi` | `pdi` | `USER_SUPPLIED` |
| `coating_thickness_nm` | `coating_thickness` | `USER_SUPPLIED` |
| `surface_area_nm2` | `surface_area` | `USER_SUPPLIED` |
| `ligand` | `ligand_identity` | `USER_SUPPLIED` |
| `ligand_density_percent` | `ligand_density_value` | `USER_SUPPLIED` |

`USER_SUPPLIED` is the honest classification: a person really did enter these,
but no method, source or conditions were ever recorded, so they carry no
evidence and cannot satisfy a blocking requirement. A legacy ligand percentage
additionally gets `ligand_density_unit = "ambiguous_percent"`, which triggers
§6.2's refusal rather than letting a denominator be assumed.

Legacy import is a *fallback*, used only when a study has no records of its own.
The first real record supersedes it entirely.

### 9.2 Demonstration studies

A study with `origin == DEMO` maps the same inputs to **`ILLUSTRATIVE`**, not
`USER_SUPPLIED`. Nobody supplied those numbers — they were chosen to exercise
the interface and describe no real material, so crediting a researcher with them
would be false.

Because `ILLUSTRATIVE` is non-contributing, every seeded study reads as **0%,
E0, blocked in all six areas**. This is what stops a demonstration database from
resembling a validated one, and it is asserted by test rather than left to
convention.

---

## 10. API

All routes are under `/api/v1/science`, all require authentication, and every
study access goes through `get_owned_study`, which **checks ownership before
revealing whether a study id exists** — so the endpoints cannot be used to probe
for other accounts' study ids.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/vocabulary` | Statuses, areas, evidence levels, versions, notice |
| `GET` | `/dictionary` | The data dictionary (optionally by `group`) |
| `GET` | `/studies/{id}/records` | Records, with legacy fallback |
| `PUT` | `/studies/{id}/records/{field_id}` | Create or replace one record |
| `GET` | `/studies/{id}/readiness` | Assess the six areas |
| `POST` | `/studies/{id}/readiness/snapshots` | Store an immutable snapshot |
| `GET` | `/studies/{id}/readiness/snapshots` | Readiness history |

An error response carries `"readiness_available": false` and **never** an area
result. A failed assessment must not be renderable as a partial one.

`PUT` validates before storing and refuses on error: `unsupported_status`,
`not_a_number`, `out_of_range`, `invalid_choice`, `missing_unit`,
`invalid_unit`, `citation_missing`, `invalid_measured_on`.
`method_not_recorded`, `conditions_not_recorded` and `measured_on_unparsable`
are returned as **warnings**, not errors — they downgrade what the value can
support without preventing it being stored.

A malformed `measured_on` is rejected by the schema with **422** (naming the
field and the expected `YYYY-MM-DD` form) or, when the service is called
directly, by `ReadinessError("invalid_measured_on")` with **400**. Both carry
`"readiness_available": false` and no area result.

`GET /vocabulary` additionally reports, per evidence level, its `requirement`,
whether it `asserts_experimental_validation`, and whether it is `attainable`;
plus `validation_kinds`, `validation_registry_available` and
`max_attainable_evidence_level`. A scale that displayed `E6` without saying it
is unreachable would invite the reading that a study is merely some distance
from it, rather than that no study can get there.

---

## 11. The dashboard

`/scientific-readiness`, reachable from the sidebar, the 3D Builder
(`builder-to-readiness`) and Step 3 (`step3-to-readiness`).

The page **computes nothing**. Every status, percentage, evidence level, block
and warning is rendered from the server's response. There is no client-side
scoring that could disagree with the rules engine. The labels in
`readinessTypes.ts` are duplicated so the page renders before the vocabulary
request returns, but the server's label wins whenever one is supplied.

It also links to `/evidence` and states the difference: `/evidence` reports
which **modules** are built and connected; this page reports whether **this
study's data** supports a kind of work. A module can be fully operational while
a study remains blocked, and vice versa.

---

## 12. Limitations

Stated plainly, because a readiness framework that overstates itself is
self-refuting.

1. **No wet-lab validation.** Nothing here has been checked against experiment.
   The framework assesses *information*, never *correctness*.
2. **E3–E6 are not reachable at all.** No validation record can be stored, so
   none can be read, so no study can exceed **E2**. This is a limitation stated
   as one rather than papered over: the platform cannot presently distinguish a
   validated design from an unvalidated one, and it says so instead of guessing.
   The levels remain in the vocabulary so the ceiling is visible; the API marks
   them `attainable: false`. They become reachable when Phase 2 implements the
   Experimental Validation Registry, and not before.
3. **Citations are not verified.** A `source_citation` is a free-text string.
   The framework checks that one is present where required; it does not check
   that it exists, that it says what is claimed, or that it describes a
   comparable material.
4. **Attachments are not parsed.** `evidence_attachment_id` is a reference. No
   instrument file is read, and no recorded value is checked against one.
5. **Method families are coarse.** `MEASUREMENT_METHOD_CLASSES` distinguishes
   scattering from microscopy; it does not distinguish TEM from cryo-TEM for
   compatibility purposes, though they can differ materially for soft matter.
6. **The rules are not exhaustive.** They catch the incompatibilities that were
   identified and implemented in Phase 1. Silence from the engine means "no rule
   fired", not "nothing is wrong".
7. **Thresholds are conventions.** 80 and 40 describe completeness. They carry
   no scientific meaning and must never be cited as though they did.
8. **Single-assessor.** There is no review workflow, no sign-off, and no second
   opinion. `verification_status` is recorded but nothing acts on it.
9. **No PK parameter library.** `pharmacokinetic_modelling` remains blocked or
   outside the model domain for most configurations. PK-B1 is assessed
   (`docs/PK_B1_TRASTUZUMAB_ASSESSMENT.md`) and deliberately **not** onboarded;
   the library ships empty rather than with combined parameters from
   incompatible studies.
10. **Cinematic animation is vocabulary only.** The area is assessed so its
    prerequisites are visible in advance. The generator itself is not begun.

---

## 13. What this phase did not change

- **No PK equation was modified.** The legacy depot model, the route-aware IV
  models and their golden vectors are untouched. A test asserts it.
- **No scoring equation was modified.**
- **No authentication or authorization was weakened.** The new routes adopt the
  existing ownership-before-existence pattern.
- **No production database, credential or secret is included** in this work or
  in the accompanying archive.
- **The Cinematic Animation Generator was not started**, per the phase brief.

---

## 14. Tests

| Suite | Result |
|---|---|
| `tests/test_scientific_readiness.py` | 70 passed |
| `tests/test_phase1_defect_corrections.py` | 117 passed |
| `tests/test_archive_sanitation.py` | 145 passed |
| Backend, full (`python -m pytest tests -q`) | 1414 passed, 0 failed, 0 skipped |
| `frontend/src/workflow/ScientificReadiness.test.tsx` | 63 passed |
| Frontend, full (`npx vitest run`) | 597 passed, 16 files, 0 failed |
| `frontend/readiness-walkthrough.mjs` | 38 checks, no problems |
| `npm run typecheck` | clean |

One regression was introduced and fixed during this phase: reporting table
creation from `apply_additive_migrations` broke that function's documented
idempotency contract (`test_is_idempotent`,
`test_does_nothing_when_the_table_is_absent`). See §9 for the fix and the reason
the split is correct rather than merely test-satisfying.

---

## 15. Corrections to Phase 1

Two defects found after the phase was first written up, corrected under
`readiness-rules-1.1.0`. Both are recorded here rather than quietly fixed,
because §8.2's snapshots are only interpretable if the rules they were produced
under are documented.

### 15.1 DEFECT-P1-A — evidence levels asserted validation with nothing behind it

`_evidence_level` returned **E3** for any required field marked `MEASURED`, and
promoted an area to **E4** or **E5** whenever an in-vitro or in-vivo evidence
*field* was populated.

Both are category errors. E3 asserts a prediction was checked against an
independent result; "measured by cryo-TEM" says an observation was made, not
that anything was checked against it. E4 asserts a prediction was registered and
then tested in vitro; a populated free-text field asserts only that someone
typed into it. The engine was therefore printing *"prospectively validated in
vitro"* for studies with no validation of any kind — the exact overclaim §0 says
the framework exists to prevent, produced by the framework itself.

**The correction** is §4.3: provenance and validation are separated, the basis
level is capped at E2, validation levels originate only in
`_recorded_validations()`, and — since Phase 1 has no registry to read — E3–E6
are unreachable rather than merely harder to reach. Making them conservatively
unreachable is deliberate: a level that cannot be earned must not be reachable
by accident, and "we cannot tell yet" is the honest answer until the registry
exists.

Two tests in `test_scientific_readiness.py` asserted the defective behaviour
(`test_measurements_reach_e3`, `test_in_vivo_evidence_reaches_e5_only_where_relevant`)
and now assert its absence. They are kept, renamed, with the reversal noted in
each docstring — a test that once encoded the wrong belief is worth more as a
record of the correction than deleted.

### 15.2 DEFECT-P1-B — `measured_on` was unvalidated free text

The API accepted any string up to 32 characters, and both loading paths then
called `date.fromisoformat` on it unguarded. `13/05/2026` stored happily, and
every subsequent read of that study raised `ValueError` — one bad keystroke made
a study permanently unopenable, *including unopenable for correction*.

**The correction** is §8.3: strict on write at both the schema and the service,
tolerant on read, with the unparsable text preserved and reported rather than
discarded. The two halves are tested separately because they fail separately —
rejecting bad input does nothing for rows already written, and tolerating stored
rubbish does nothing to stop more arriving.

### 15.3 DEFECT-P1-C — the sanitized archive was not sanitized

A built archive shipped `users.json` (a SHA-256 password hash and a real
personal email address), `sessions.json` (live session token keys with the
usernames and activity times they belonged to), and `.claude/settings.local.json`
(the build machine's absolute paths). Both copies of the first two — the root
one and the legacy `biotech-lab-main/` one — were included.

The builder scanned for *credentials* and reported "secret scan: clean", which
was true and beside the point. **An account record is not a credential**, and
nothing was looking for one. The scan answered a narrower question than its
output implied, which is the worst failure mode a safety check has: it produced
confidence rather than an error.

**The correction**, in `make_readiness_archive.py`:

| Layer | What it does |
|---|---|
| Denial | `DENY_FILENAMES` refuses account, session, token and machine-config files by bare filename, case-insensitively, at any depth — so a copy in a legacy subtree is refused on the same terms as the root one. `MACHINE_CONFIG_DIRS` drops `.claude/`, `.aws/`, `.ssh/` and kin. |
| Detection | Content patterns for session token keys, assigned session tokens, password hashes (by *field name*, not by "looks like hex"), personal mailboxes and home-directory paths. A denylist cannot catch a token pasted into a README. |
| Enforcement | A content finding **aborts** the build. Refused files are excluded and **reported**, not dropped silently. |
| Verification | The written zip is reopened and re-scanned, and **deleted** if it fails. |

Two decisions worth stating, because both could reasonably have gone the other
way:

- **Refused files are excluded, not fatal.** They legitimately exist in a
  working checkout; a builder that aborted whenever a developer had logged in
  once is a builder nobody runs, and an unrunnable check is an absent one. They
  are printed, so "clean" never silently means "clean after refusing five
  account records".
- **Password hashes are matched on the field name.** The golden vectors are
  full of 64-character hex strings under a `"sha256"` key. A "looks like a
  hash" rule would have stripped the scientific fixtures this project's
  correctness rests on. What makes a hash a *password* hash is the field it
  sits in.

Personal-email detection is likewise keyed on consumer mail providers, so the
project's published business contacts (`info@expertsgroup.me`) and its fictional
fixtures (`admin@nanobio.local`) are not flagged while an individual's real
mailbox is. A rule that flagged every email address would be switched off within
a week.

`tests/test_archive_sanitation.py` holds 145 tests across denial, detection,
enforcement, the shipped artefact and the working tree — including a control
that a clean tree still builds, and a guard that the golden vectors survive
sanitation untouched.

### 15.4 DEFECT-P1-D — plaintext credentials in source

A follow-up sweep, once the scanner could look for plaintext rather than only
hashes, found credentials the first pass had no detector for:

| Where | What |
|---|---|
| 7 × `frontend/*walkthrough.mjs` | A working account password, repeated as a literal in every script |
| Legacy Streamlit login page | Three demo passwords — compared *and printed on the form itself* |
| `db_init.py` | The administrator created with a one-word password, so every database this script made shared it |
| `create_admin.py`, `set_admin_password.py` (both copies) | A provisioning password in the file, echoed to stdout |
| `modules/instructor.py` (both copies) | A password displayed on the page it protected |
| `AUTHENTICATION.md`, `test_phase3_integration.py` (both copies) | The same credentials repeated in documentation and test output |

All are now environment-supplied, and **absent means unavailable, never a
default** — a fallback default is the same defect with an extra step. The
walkthroughs read `NANOBIO_WALKTHROUGH_USER` / `NANOBIO_WALKTHROUGH_PASSWORD`
from one shared module and exit with setup instructions when either is missing;
the legacy page reads `NANOBIO_DEMO_*_PASSWORD` and disables sign-in when none
is set; the provisioning scripts refuse to run without `NANOBIO_ADMIN_PASSWORD`.

Two details worth recording, because both could have gone the other way:

- **The weak-password denylist in `create_admin.py` is a rule, not a list.** A
  list has to *contain* the retired passwords to reject them, which puts them
  back into the source this cleanup removed them from, and only ever rejects
  the ones somebody remembered to add. `^[A-Za-z]+\d+$` catches the whole
  family — the shape of nearly every default password ever shipped.
- **The scanner's known-credential set holds SHA-256 digests, not
  plaintext**, for the same reason: the builder can refuse a value it cannot
  itself disclose, and findings are reported redacted (`a******* (8 chars)`)
  because a build log reaches a terminal, CI, and often a ticket.

The stray root file `%F` — 312 bytes of UTF-16 Streamlit fragment left by a
shell redirection mishap, already noted in
`docs/CURRENT_APPLICATION_AUDIT.md` — was deleted. It carried no secret;
unexplained content in a source archive is its own kind of problem.

`README-ARCHIVE.md` now **generates** its exclusion and detector lists from the
builder's constants, and states what the scan does *not* cover. A sanitation
notice that overstates its scanner is worse than none, because it is believed.

### 15.5 What the corrections did not touch

No PK equation, no scoring equation, no golden vector, and no dictionary field.
`DICTIONARY_VERSION` is unchanged at `data-dictionary-1.0.0` precisely because
no field was added: the registry is a Phase 2 deliverable, and adding fields
that *look* like validation records without a registry behind them would
recreate the defect in a new place. The Cinematic Animation Generator was not
begun.

No Phase 1 *behaviour* changed in 15.4 either: the credential work moved values
out of source into the environment and deleted a stray file. The rules engine,
the readiness API and the dashboard are byte-identical in behaviour, which is
what the unchanged 597-test frontend suite and the 38-check browser walkthrough
confirm.
