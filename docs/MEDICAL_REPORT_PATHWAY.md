# Medical Report Assessment — audit finding, delivered scope, and blockers

**Created:** 2026-08-02
**Status:** Upload, validation, review, confirmation and mapping are operational.
**Automatic extraction is NOT — no extraction engine exists to migrate.**

---

## 1. Audit finding: the capability was never in the legacy application

The request described this as *"a material capability from the legacy Streamlit
application"* that the React version was missing. **It is not.** A sweep of every
file type across the root project and both snapshots (`biotech-lab-main/`,
`nan-bio-studio-4-main/`, `legacy_streamlit/`) found no report-processing code.

### Every upload widget in the repository

| File | What it accepts | Is it a medical report? |
|---|---|---|
| `modules/import_export.py:23` | `file_uploader(type=['json'])` — a saved **nanoparticle design** | No |
| `pages/10_ML_Training.py:62` | `file_uploader(type="csv")` — an **ML training dataset** | No |

That is the complete set (each is duplicated in `biotech-lab-main/`).

### Also absent, everywhere

| Capability | Searched for | Found |
|---|---|---|
| PDF reading | PyPDF2, pdfplumber, fitz/PyMuPDF, pdfminer | **none** |
| OCR | pytesseract, tesseract, easyocr | **none** |
| Clinical NLP | spaCy, scispaCy, medspaCy, negspacy | **none** |
| Field extraction | staging, TNM, receptor, biomarker, histology parsing | **none** |
| Dependency | `requirements.txt` | **none** |
| Documentation | every `.md` in the repository | **none** |

`reportlab` is present, but it *writes* PDFs for report export — the opposite
direction. Earlier grep hits for `ner` were substrings of *spin**ner***,
*contai**ner***, *desig**ner***.

**Conclusion.** This is a new feature, not a migration regression. There was no
genuine pipeline to port, and the instruction *"do not recreate it from memory"*
rules out inventing one. Two decisions were taken with the user (2026-08-02):

1. **Build the secure structure; label processing honestly as unavailable.**
2. **Accept synthetic and de-identified documents only**, enforced technically.

---

## 2. What runs, and what does not

| Stage | Status |
|---|---|
| Upload | **Operational** — content-based type detection, size cap, magic bytes, active-content refusal |
| Intake policy | **Operational** — real patient data refused; attestation required; identifier screening |
| Storage & audit | **Operational** — separate document table, append-only audit, real deletion, retention deadline |
| Document display | **Operational for text/Markdown.** PDFs are stored but cannot be displayed — no reader exists |
| **Automatic extraction** | **NOT OPERATIONAL** — no engine. Every field returns `not_found` |
| Manual review & entry | **Operational** — all 15 clinical fields, provenance recorded |
| Confirmation | **Operational** — inferred/ambiguous cannot be confirmed without an explicit decision |
| Mapping to workflow | **Operational** — validated against the curated disease mapping |
| De-identification | **Limited** — pattern-based redaction, explicitly not HIPAA Safe Harbor |

---

## 3. The extraction contract

`app/reports/extraction.py` defines the shape a real engine must satisfy, and
returns an honest "not available" result until one exists.

### Provenance vocabulary

| Value | Meaning | Confirmable directly? |
|---|---|---|
| `explicitly_stated` | The report says it, with a supporting text span | Yes |
| `inferred` | An engine derived it from context | **No** — must be accepted or replaced |
| `ambiguous` | The document supports more than one reading, or contradicts itself | **No** — must be resolved |
| `not_found` | The document does not contain it | Yes (as empty) |
| `user_entered` | A human typed it | Yes |
| `user_corrected` | A human overrode an engine value; the original is retained | Yes |

`ExtractionResult.validate()` rejects a contract violation — an
`explicitly_stated` field without a supporting span, or a `not_found` field
carrying a value. **The server refuses to confirm an `inferred` or `ambiguous`
value**, so no automatic promotion is possible from any client.

### What a real engine must provide before it may be connected

1. Per-field provenance with the exact page and verbatim supporting span.
2. An honest confidence signal, and `stated` vs `inferred` kept distinct.
3. Explicit contradiction detection rather than silently picking one value.
4. A versioned model identifier recorded with every result.
5. Validation against annotated reports, with published performance.

None exists, which is why the module status is *Limited prototype* and the
engine records itself as `none` / `not-connected`.

---

## 4. Security controls

| Control | Implementation | Honest limit |
|---|---|---|
| **Authentication** | Every route requires a session | — |
| **Authorisation** | Organization-scoped; see §4a. Every lookup applies the boundary in SQL, so a foreign id is never selected | — |
| **Tenant isolation** | `organization_id` on assessments, documents and audit rows, derived from the caller's selection or the stored parent | — |
| **Type validation** | Magic bytes, not filename or client MIME type. Allow-list, never block-list | — |
| **Size cap** | 15 MB, enforced before the body is fully read | — |
| **Malicious content** | Executables, ELF, archives, shebang scripts, PHP refused. PDFs with `/JavaScript`, `/Launch`, `/EmbeddedFile`, `/OpenAction` refused | **Not antivirus.** Detects the checkable classes only |
| **Filename safety** | Path separators, traversal, control characters and null bytes stripped; stored name derived from content | — |
| **PHI gate** | Real patient data refused server-side; attestation required and recorded | — |
| **Identifier screening** | Patterns for email, national ID, phone, postcode | **Warns, does not block.** Cannot detect a name in prose |
| **Audit trail** | Append-only, keyed on `user_id`; upload, view, download, confirm, map, deidentify, delete, refuse | — |
| **Deletion** | Real row deletion cascading to the document body — not a soft flag | — |
| **Retention** | Deadline on every assessment; admin-only purge with dry-run | Not yet scheduled automatically |
| **Download** | `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` | — |
| **Client storage** | Report content never enters `localStorage`, `sessionStorage` or a draft. Asserted by test | — |
| **Logging** | Audit `detail` carries codes and counts only. Asserted by test | — |
| **De-identification** | Pattern redactor, version recorded | **Not HIPAA Safe Harbor, not certified** |

### 4a. Who may do what to a patient assessment

This is the table the whole conversion turns on, and the two absences in it are
the design rather than an oversight. It is `policy.REPORT_ROLE_ACTIONS`,
reproduced; the code is the authority and this is here to be argued with.

| Organization role | View | Create | Amend | Download | Delete | History | Purge |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `OWNER` | — | — | — | — | — | ✓ | ✓ |
| `ADMINISTRATOR` | — | — | — | — | — | ✓ | — |
| `RESEARCHER` | ✓ | ✓ | ✓† | ✓ | ✓† | ✓ | — |
| `REVIEWER` | ✓ | ✓ | ✓† | ✓ | — | ✓ | — |
| `APPROVER` | ✓ | ✓ | ✓† | ✓ | — | ✓ | — |
| `AUDITOR` | — | — | — | — | — | ✓ | — |
| `LAB_CONTRIBUTOR` (external CRO) | — | — | — | — | — | — | — |

† **Author only.** Amending or deleting changes or destroys a clinical
judgement, so it stays with whoever made it. A colleague with organization-wide
scope may *read* a confirmed field; nobody may change it on the author's behalf,
because "who decided this said X" has to stay answerable.

**Why owners and administrators cannot read a report.** An organization
administrator can add themselves to anything. If that also let them read every
clinical document, the account with the most control over access would be the
account with the most access to patient data — and the separation between
managing people and acting on evidence, which the rest of the platform depends
on, would stop at the door of the most sensitive table in the database. They
get the access *trail* instead: who opened it, who downloaded it, when. An
access review needs that and does not need the diagnosis.

**Why a contract laboratory gets nothing at all.** `LAB_CONTRIBUTOR` is the
external role. There is deliberately no assignment, scope or flag that grants a
CRO sight of a patient's report, so the answer cannot be changed by
misconfiguration — only by editing this table.

**Purge is not a clinical act.** It works on retention dates and reads no
content, so it belongs with the organization owner. A platform administrator
may also run it, but only inside an organization they belong to, so it stays
scoped like every other read.

#### Beyond the role: three further gates

Holding the verb is necessary and not sufficient. Each of these is applied
after the table above:

| Gate | Effect |
|---|---|
| **Scope** | An `ASSIGNED_STUDIES` membership reaches only its own records. An assessment hangs off no study, so there is nothing for such a membership to reach a colleague's assessment *through* |
| **Membership state** | `SUSPENDED`, `REVOKED`, `EXPIRED` and a passed `expires_at` all grant nothing. Expiry is evaluated on every request, not by a sweep |
| **Attachment restriction** | `may_download_attachments = false` withholds `DOWNLOAD_REPORT_DOCUMENT` while leaving `VIEW_REPORT` intact — reading results on screen and taking the file away are different acts |

#### What a refused caller learns

Nothing, and that is tested as an equality rather than as a pair of refusals:

| Situation | Answer |
|---|---|
| Assessment in another organization | **404**, byte-identical to an id that never existed |
| Assessment absent | **404** |
| Inside the organization, role does not permit | **403**, with a reason — they can already see the organization |
| Multi-organization caller uploading without selecting | **409 `organization_required`** — never a guess |

The 404 body carries no organization, no owner, no display name, no size, no
hash, no status and no timestamp. Lists, searches and counts are computed from
the scoped query, so a *total* cannot disclose how many assessments another
organization holds.

---

### Not implemented, and stated rather than implied

**Encryption at rest.** Document bytes sit in the SQLite file unencrypted. That
is precisely why real patient data is refused at intake.

---

## 5. A report cannot change a calculation

Enforced structurally, not by convention:

* only three of fifteen fields map onward — disease, subtype, drug — and they
  populate **therapeutic context**, which no connected engine reads;
* `DesignScoreRequest` and `PKSimulationRequest` field sets are **disjoint** from
  the clinical field keys (asserted by test);
* a test computes a design score, confirms clinical fields, recomputes, and
  asserts the result is byte-identical.

The design impact score consumes physicochemical parameters only; the PK model
consumes a dose and four rate constants only.

---

## 6. Synthetic fixtures

Three fabricated documents (`app/reports/fixtures.py`), each carrying a banner
inside the document itself so the classification survives download or print.

| Slug | Demonstrates |
|---|---|
| `synthetic-breast-pathology` | A complete, internally consistent surgical pathology report |
| `synthetic-lung-clinic-letter` | Narrative prose rather than tabulated pathology — much harder to extract from |
| `synthetic-colorectal-conflicting` | **Deliberate contradictions** (two stages, two MSI statuses) and blank sections |

Fictional identities, invented findings, not derived from any real case. A test
asserts no fixture carries a field capable of holding a result — loading one runs
the **same** upload, validation and extraction path as a user's own file, so the
demo shows the platform's real capability including its real limits.

---

## 7. Files

**Created — backend:** `app/reports/{__init__,extraction,validation,fixtures,policy,deidentify,disease_mapping}.py` ·
`app/db/report_models.py` · `app/schemas/medical_report.py` ·
`app/services/report_service.py` · `app/api/routes/reports.py` ·
`tests/test_medical_reports.py`

**Created — frontend:** `src/pages/report/{ReportAssessment.tsx,ReportAssessment.css}` ·
`src/workflow/ReportAssessment.test.tsx` · `verify_report.mjs`

**Changed:** `app/db/auth_session.py` · `app/vertical_slice.py` (router, 422 flag,
CORS DELETE) · `src/api/{types.ts,client.ts}` (multipart handling) ·
`src/App.tsx` · `src/shell/navigation.ts` ·
`src/pages/workflow/SessionStartPage.tsx` (four pathways) ·
`src/workflow/WorkflowContext.tsx` (**cascade bug fix**, §9)

---

## 8. Verification

```powershell
python -m pytest tests\test_medical_reports.py -q   # 90 passed
python -m pytest tests -q                           # 919 passed
cd frontend && npm test                             # 222 passed
npm run typecheck && npm run build                  # clean, succeeded
node verify_report.mjs                              # PROBLEMS: none
```

Live end-to-end against the running backend:

```
offered on the session gate ..... yes
extraction status shown ......... true
PHI policy shown ................ true
synthetic fixtures listed ....... 3
engine recorded ................. none not-connected
document shown verbatim ......... true
every field not-in-report ....... true
pre-filled clinical values ...... 0 (correct)
provenance after typing ......... You entered
fields confirmed ................ yes
indication carried .............. Breast Cancer
drug carried .................... Trastuzumab (Herceptin)
delivery score (calculated) ..... 88.06
PK C_max (calculated) ........... 1.7499988727078915
report content in client storage. none
PROBLEMS: none
```

Screenshots: `docs/screenshots/rpt-01` … `rpt-06`.

---

## 9. A bug this work exposed

`setSelection` in `WorkflowContext.tsx` cleared subtype and drug whenever the
disease changed — correct when a user picks a new indication, wrong when a
caller supplies a **complete valid triple** in one call. Carrying a confirmed
context forward therefore populated only the indication, and Step 1 arrived
half-filled and un-continuable. A child is now cleared only when the patch does
not supply it. Regression test added; the existing cascade tests still pass.

---

## 10. Remaining blockers

| # | Blocker | Needed before it lifts |
|---|---|---|
| **R1** | **No extraction engine.** Every field is entered by hand | A validated engine meeting §3, with published performance against annotated reports. Writing regexes would produce uncalibrated output presented as findings from a patient's report |
| **R2** | **No PDF text extraction.** PDFs are stored but unreadable | A PDF library, plus a decision on scanned documents (OCR) |
| **R3** | **No OCR**, so scanned reports cannot be processed at all | An OCR dependency and validation of its output quality |
| **R4** | **No encryption at rest** | KMS or database-level encryption. **Gates real-PHI intake** |
| **R5** | **No HTTPS** in the current deployment | TLS termination. **Gates real-PHI intake** |
| **R6** | **No scheduled retention job** — purge is manual | A scheduler. **Gates real-PHI intake** |
| **R7** | **No legal basis / DPA / ethics approval** recorded | An organisational decision, not an engineering one. **Gates real-PHI intake** |
| **R8** | **No Alembic migration** for the report tables | Migrations for the whole schema |
| **R9** | De-identification is pattern-based, not certified | A validated de-identification approach if export of real documents is ever required |

R4–R7 together form the gate on accepting real patient reports. All four must be
in place; none is sufficient alone.
