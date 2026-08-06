# Medical Report Extraction Pipeline

**Created:** 2026-08-02
**Status:** Operational for text-based PDFs and plain text. **OCR unavailable.**
**Supersedes:** the "no extraction engine is connected" status recorded in
`docs/MEDICAL_REPORT_PATHWAY.md` §2.

> **Scientific standing, stated up front.** The extractor is a **rule-based
> reader**. It is not a trained model, has not been calibrated or validated
> against annotated reports, and its accuracy on real-world documents is
> **unmeasured**. Every clinically material field still requires human
> confirmation. The `confidence` figure is a heuristic pattern-strength score,
> **not a probability**.

---

## 1. Approach

Three stages, each with a single responsibility:

| Stage | Module | What it does |
|---|---|---|
| Text recovery | `app/reports/pdf_text.py` | Reads a PDF's embedded text layer with `pypdf`, page by page. Detects pages with no text layer |
| Field extraction | `app/reports/clinical_extractor.py` | Locates labelled fields and known oncology vocabulary by regular expression, returning each with its verbatim excerpt and page |
| Contract & provenance | `app/reports/extraction.py` | Wraps findings in the typed result contract, enforces the provenance rules, attaches versions and limitations |

### Why rule-based rather than a model

A trained clinical NER model needs annotated reports to train and validate
against, and none exist here. A rule-based reader has the compensating virtue
that **every output is traceable to a literal span the reader can check**, which
is what makes human confirmation meaningful rather than ceremonial.

Choosing this deliberately does not make it validated. It is an assistant that
shows its working.

### Text-based PDFs

`pypdf` recovers the embedded text layer. Verified end to end: a PDF generated
by reportlab is read back with all clinical content intact.

### Scanned PDFs — detected, not decoded

A page yielding fewer than 40 characters is treated as image-only. When **every**
page is image-only the document is reported as
`document_unreadable` with an explicit message.

**No OCR engine is installed** — `pytesseract` is absent, the `tesseract`
binary is not on PATH, and `easyocr` is absent. `ocr_available()` checks for
both a wrapper *and* its binary at call time, so installing one takes effect
without a code change.

Returning plausible text for a page nobody could read would be the worst failure
mode available to this pipeline: it would be indistinguishable from a real
reading, and every downstream field would inherit the fabrication. So nothing is
guessed.

The detection is a heuristic and says so: a genuinely near-empty page (a divider,
a signature sheet) also yields little text, so mixed documents report *which*
pages were unreadable rather than asserting the whole document is a scan.

---

## 2. Fields extracted

| Field | Notes |
|---|---|
| `cancer_indication` | Mapped to a curated indication where one exists, so a confirmed value can flow into Disease & Therapeutic Selection without a second guess |
| `histological_subtype` | Specific subtypes beat generic ones (`invasive ductal carcinoma` over `adenocarcinoma`) |
| `tumor_site` | Labels tried in **priority order**, so a generic `Specimen:` earlier in the document cannot beat a specific `Primary site:` later |
| `stage`, `tnm_classification`, `grade` | Normalised (`Stage IIB`, `Grade 3`); Roman and Arabic both accepted |
| `metastatic_sites` | Negation-aware — see §4 |
| `er_status`, `pr_status` | Normalised to Positive / Negative / Equivocal / Not tested |
| `her2_ihc`, `her2_ish` | Read **separately**, because they are separate assays |
| `her2_status` | **Derived** from the two above — always `inferred`, never `explicitly_stated` |
| `her3_status`, `ki67`, `pdl1` | Reported as stated; an explicit "not tested" is a finding, silence is not |
| `genomic_alterations` | Per-gene result across 20 genes, distinguishing "mutation detected" from "no pathogenic variant detected" |
| `pathology_findings`, `current_treatment`, `therapeutic_context`, `laboratory_findings` | Section-based |
| `report_date`, `document_type` | Document metadata |

---

## 3. Provenance model

Every field returns: **value · status · page · supporting excerpt · confidence ·
engine and contract version**.

| Status | Meaning | Directly confirmable? |
|---|---|---|
| `explicitly_stated` | The document says it, with a supporting excerpt | Yes |
| `inferred` | Derived by combining findings | **No** |
| `ambiguous` | Components do not combine unambiguously | **No** |
| `conflicting` | Two different values, unreconciled; both returned | **No** |
| `not_found` | Not in the document. Never a blank guess | Yes (as empty) |
| `user_entered` / `user_corrected` | A human typed or accepted it | Yes |

The contract is enforced by `ExtractionResult.validate()`, which rejects an
`explicitly_stated` field with no excerpt, a `not_found` field carrying a value,
and a `conflicting` field with no competing reading. **The server independently
refuses to confirm an unresolved status**, so a client that skipped the UI would
still be blocked.

### Accepting an unresolved reading

The one route from unresolved to confirmable is the explicit **"Accept this
reading"** action. It records the value as `user_corrected` — the human took
responsibility — while `original_value` preserves what the engine found, so the
override stays visible as an override.

### The HER2 case, worked

The primary fixture reports HER2 IHC **equivocal (2+)** and HER2 ISH
**amplified**. Conventionally that is reported as HER2-positive — but that
conclusion is the *reader's*, not the document's. So:

* `her2_ihc` → `Equivocal (2+)`, **explicitly stated**, confidence 0.90
* `her2_ish` → `Amplified`, **explicitly stated**, confidence 0.90
* `her2_status` → `HER2 positive (by ISH amplification)`, **inferred**,
  confidence 0.50, with a note naming what it was derived from

The inference cannot be confirmed without a human accepting it.

---

## 4. Negation: the most dangerous failure mode

An early version extracted **"therapy administered prior to surgery"** from the
sentence *"No systemic therapy administered prior to surgery."* — dropping the
negation and inverting the clinical claim. The same bug turned *"No evidence of
distant metastatic disease"* into a metastatic finding.

**Root cause:** matching forward from a keyword, so words before it were lost.

**Fix:** treatment and metastasis are now evaluated on the **whole line**, with a
negation cue set matched against that line. Two tests assert the inverted
readings never reappear.

This is worth stating plainly because it is the class of error a rule-based
clinical reader is most prone to, and the one most likely to matter.

---

## 5. Test fixtures

Generated as **real PDFs** at import time (`app/reports/pdf_fixtures.py`) rather
than checked in as binaries, so the clinical content is reviewable in a diff
while the artefact the pipeline receives is a genuine PDF with a real text layer.

| Slug | Exercises |
|---|---|
| `synthetic-pdf-breast-oncology` | The full required field set — the primary end-to-end fixture |
| `synthetic-pdf-conflicting` | Two stages and two grades, unreconciled |
| `synthetic-pdf-sparse` | Biomarkers genuinely absent |
| `synthetic-pdf-scanned` | Image-only, no text layer |

**No fixture stores an expected result.** The values the tests assert are
produced by running the real pipeline over the real PDF; if the extractor stops
finding them, the tests fail. A test scans every fixture dataclass for
result-shaped field names to keep it that way.

### Required identification — all produced by parsing, none hard-coded

```
cancer_indication      Breast Cancer
histological_subtype   invasive ductal carcinoma (NST)
grade                  Grade 3
stage                  Stage IIB
er_status              Positive
pr_status              Positive
her2_ihc               Equivocal (2+)
her2_ish               Amplified
her3_status            Not tested / not available
genomic_alterations    PIK3CA: p.H1047R mutation detected; BRCA1: negative …
her2_status            HER2 positive (by ISH amplification)   [INFERRED]
```

---

## 6. Security and privacy — unchanged and still enforced

The synthetic-only restriction **remains in force**. Real patient reports are
refused at intake because the deployment still has no encryption at rest, no
HTTPS, no scheduled retention job and no recorded legal basis (blockers R4–R7 in
`docs/MEDICAL_REPORT_PATHWAY.md` §10). Adding extraction does not change that
calculus — if anything it raises the stakes.

Controls carried forward unchanged: content-based type detection, 15 MB cap,
executable/archive/active-content refusal, filename neutralisation, attestation
gate, identifier screening, role-based authorisation, ownership-before-existence
checks, append-only audit, real cascading deletion, retention deadlines,
attachment-only downloads.

**Additional controls verified for this slice:**

* extracted clinical values **never** reach `localStorage` or `sessionStorage` —
  asserted in the browser against the live app;
* the audit trail records counts and codes only, never a clinical value;
* a report value cannot reach a calculation — the design-score and PK request
  schemas are disjoint from the clinical field keys, and every field is returned
  with `consumed_by_engines: false`.

---

## 7. Files

**Created:** `app/reports/pdf_text.py` · `app/reports/clinical_extractor.py` ·
`app/reports/pdf_fixtures.py` · `tests/test_report_extraction.py` ·
`docs/REPORT_EXTRACTION.md`

**Materially changed:** `app/reports/extraction.py` (contract v2, live engine) ·
`app/reports/validation.py` (PDFs readable) ·
`app/services/report_service.py` (runs the pipeline, persists recovered text) ·
`app/api/routes/reports.py` (PDF fixtures registered) ·
`src/api/types.ts` (confidence, conflicting, excerpts) ·
`src/pages/report/ReportAssessment.tsx` (evidence display, accept-inference) ·
`src/pages/report/ReportAssessment.css` ·
`tests/test_medical_reports.py` and `src/workflow/ReportAssessment.test.tsx`
(obsolete "no engine" assertions rewritten)

---

## 8. Verification

```powershell
python -m pytest tests\test_report_extraction.py -q   # 58 passed
python -m pytest tests -q                             # 979 passed
cd frontend && npm test                               # 275 passed
npm run typecheck && npm run build                    # clean, succeeded
node verify_extraction.mjs                            # PROBLEMS: none
```

Live browser run against the real backend:

```
engine : rule-based-oncology-extractor 1.0.0
message: Read 22 of 22 fields from the document; 1 needs an explicit decision…
HER2 overall  : Inferred (correct)
stage excerpt : shown      stage page: shown      match strength: shown
confirmed     : yes
mapped to     : Breast Cancer / Trastuzumab (Herceptin)
scanned pdf   : reported unreadable (correct)
storage leak  : none
PROBLEMS: none
```

Screenshots: `docs/screenshots/ext-01` … `ext-04`.

---

## 9. Limitations

1. **Unvalidated.** No measured precision or recall. Every material field
   requires human confirmation, and the interface says why.
2. **No OCR.** Scanned reports cannot be processed at all (R3).
3. **English only**, and tuned to the phrasing of the synthetic fixtures. A real
   hospital's house style will differ, and accuracy on it is unknown.
4. **Breast-weighted vocabulary.** ER/PR/HER2/Ki-67 are covered in most depth;
   other tumour streams have thinner coverage.
5. **No table or layout parsing.** A result presented only in a table cell may be
   missed — text order, not visual structure, is what is read.
6. **Conflict detection is exact-value based.** Two readings that differ only in
   phrasing may be treated as distinct, or a real conflict expressed in different
   words may be missed.
7. **Confidence is not calibrated** and must not be shown to anyone as a
   probability.
8. **Synthetic documents only** — R4–R7 still gate real-PHI intake.

---

## 10. What would make this trustworthy

In order of value:

1. **An annotated corpus** and published precision/recall per field. Without
   this, every other improvement is unmeasurable.
2. **OCR** with its own accuracy measurement (R2, R3).
3. **Table and layout awareness**, since much of a pathology report is tabular.
4. **A second reader** — a trained model — with disagreement surfaced rather than
   silently resolved.
5. **Clinical review of the vocabulary and normalisation rules** by someone
   qualified to judge them.
