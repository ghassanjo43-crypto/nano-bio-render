"""Tests for the medical-report extraction pipeline.

The primary end-to-end assertion is
``TestBreastPdfEndToEnd``: it runs the **real** pipeline over a **real** PDF and
requires the specific clinical values to come out. Nothing is stubbed and no
expected value is stored in a fixture — if the extractor stops finding them, the
test fails, which is the whole point.

The other load-bearing groups:

* **negation** — "No systemic therapy administered" must never be read as
  "therapy administered". Dropping a negation inverts clinical meaning and is
  the most dangerous failure this reader can have.
* **derivation** — HER2 read from an equivocal IHC plus an amplified ISH is an
  inference, must be labelled as one, and must be un-confirmable directly.
* **conflict** — two stages in one document surface both, never one.
* **scanned** — no OCR exists, so an image-only PDF is reported, not guessed.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from nanobio_studio.app.reports.clinical_extractor import (  # noqa: E402
    EXTRACTOR_NAME, EXTRACTOR_VERSION, extract_clinical_fields)
from nanobio_studio.app.reports.extraction import (  # noqa: E402
    CLINICAL_FIELDS, EngineStatus, FieldProvenance, extract_from_document)
from nanobio_studio.app.reports.pdf_fixtures import (  # noqa: E402
    SYNTHETIC_PDFS, build_pdf, pdf_fixture_by_slug)
from nanobio_studio.app.reports.pdf_text import (  # noqa: E402
    extract_pdf_text, ocr_available)


def _run(slug: str):
    """Run the real pipeline over a real PDF fixture."""
    fixture = pdf_fixture_by_slug(slug)
    assert fixture is not None, slug
    return extract_from_document(content=fixture.as_bytes(), text=None,
                                 is_pdf=True)


def _field(result, key):
    return next(f for f in result.fields if f.key == key)


@pytest.fixture(scope="module")
def breast():
    return _run("synthetic-pdf-breast-oncology")


# ===========================================================================
# The required end-to-end identification
# ===========================================================================


class TestBreastPdfEndToEnd:
    """Every value below is produced by parsing the PDF, never hard-coded."""

    def test_extraction_completes(self, breast):
        assert breast.status is EngineStatus.COMPLETED
        assert breast.engine_name == EXTRACTOR_NAME
        assert breast.engine_version == EXTRACTOR_VERSION

    def test_identifies_invasive_breast_carcinoma(self, breast):
        f = _field(breast, "cancer_indication")
        assert f.value == "Breast Cancer"
        assert "breast" in f.supporting_text.lower()

    def test_identifies_invasive_ductal_carcinoma(self, breast):
        f = _field(breast, "histological_subtype")
        assert "invasive ductal carcinoma" in f.value.lower()

    def test_identifies_grade_3(self, breast):
        f = _field(breast, "grade")
        assert f.value == "Grade 3"
        assert f.provenance is FieldProvenance.EXPLICITLY_STATED

    def test_identifies_clinical_stage_iib(self, breast):
        f = _field(breast, "stage")
        assert f.value == "Stage IIB"
        assert f.provenance is FieldProvenance.EXPLICITLY_STATED

    def test_identifies_er_positive(self, breast):
        assert _field(breast, "er_status").value == "Positive"

    def test_identifies_pr_positive(self, breast):
        assert _field(breast, "pr_status").value == "Positive"

    def test_identifies_her2_ihc_equivocal_2plus(self, breast):
        f = _field(breast, "her2_ihc")
        assert f.value == "Equivocal (2+)"
        assert "2+" in f.supporting_text

    def test_identifies_her2_ish_amplified(self, breast):
        assert _field(breast, "her2_ish").value == "Amplified"

    def test_identifies_her3_not_tested(self, breast):
        f = _field(breast, "her3_status")
        assert "not tested" in f.value.lower()

    def test_identifies_pik3ca_mutation(self, breast):
        f = _field(breast, "genomic_alterations")
        assert "PIK3CA" in f.value
        assert "mutation detected" in f.value.lower()

    def test_identifies_brca_negative(self, breast):
        f = _field(breast, "genomic_alterations")
        assert "BRCA1" in f.value or "BRCA1/2" in f.value
        assert "negative" in f.value.lower() or "not detected" in f.value.lower()

    def test_identifies_tumour_site(self, breast):
        # A specific "Primary site:" label must beat a generic "Specimen:" that
        # appears earlier in the document.
        assert "upper outer quadrant" in _field(breast, "tumor_site").value.lower()

    def test_identifies_report_date_and_document_type(self, breast):
        assert "2026" in _field(breast, "report_date").value
        assert "pathology" in _field(breast, "document_type").value.lower()

    def test_identifies_ki67(self, breast):
        assert "45" in _field(breast, "ki67").value

    def test_values_are_not_hard_coded_anywhere(self):
        """The fixture is a document; it must contain no stored answers."""
        from dataclasses import asdict

        for pdf in SYNTHETIC_PDFS:
            keys = set(asdict(pdf))
            for forbidden in ("fields", "extraction", "expected", "result",
                              "answers", "confirmed"):
                assert not any(forbidden in k for k in keys), pdf.slug


# ===========================================================================
# Provenance
# ===========================================================================


class TestProvenance:

    def test_every_stated_field_carries_page_and_excerpt(self, breast):
        for f in breast.fields:
            if f.provenance is FieldProvenance.EXPLICITLY_STATED:
                assert f.page and f.page >= 1, f.key
                assert f.supporting_text, f.key

    def test_excerpt_actually_appears_in_the_document(self, breast):
        """A supporting excerpt must be checkable against the source."""
        source = breast.document_text.lower().replace("\n", " ")
        source = " ".join(source.split())
        for f in breast.fields:
            if f.provenance is FieldProvenance.EXPLICITLY_STATED:
                core = f.supporting_text.strip("… ").lower()
                core = " ".join(core.split())[:40]
                assert core in source, f"{f.key}: {core!r} not in document"

    def test_confidence_is_present_and_bounded(self, breast):
        for f in breast.fields:
            assert 0.0 <= f.confidence <= 1.0, f.key
            if f.provenance is FieldProvenance.NOT_FOUND:
                assert f.confidence == 0.0, f.key

    def test_reader_provenance_is_recorded(self, breast):
        assert breast.reader_name == "pypdf"
        assert breast.reader_version

    def test_engine_and_contract_versions_are_recorded(self, breast):
        assert breast.engine_version == EXTRACTOR_VERSION
        assert breast.contract_version.startswith("extraction-contract-")

    def test_confidence_is_labelled_as_not_a_probability(self, breast):
        text = " ".join(breast.limitations).lower()
        assert "not a probability" in text

    def test_result_passes_its_own_contract(self, breast):
        breast.validate()      # raises on any violation


# ===========================================================================
# Derivation — HER2 is inferred, never stated
# ===========================================================================


class TestHer2Derivation:

    def test_overall_her2_is_marked_inferred(self, breast):
        f = _field(breast, "her2_status")
        assert f.provenance is FieldProvenance.INFERRED
        assert "positive" in f.value.lower()

    def test_inference_explains_what_it_was_derived_from(self, breast):
        f = _field(breast, "her2_status")
        assert "derived" in f.note.lower()
        assert "does not state" in f.note.lower()

    def test_inference_needs_a_human_decision(self, breast):
        assert _field(breast, "her2_status").needs_human_decision is True

    def test_components_remain_separately_stated(self, breast):
        assert _field(breast, "her2_ihc").provenance is \
            FieldProvenance.EXPLICITLY_STATED
        assert _field(breast, "her2_ish").provenance is \
            FieldProvenance.EXPLICITLY_STATED

    def test_derived_confidence_is_lower_than_a_stated_value(self, breast):
        assert _field(breast, "her2_status").confidence < \
            _field(breast, "her2_ihc").confidence

    def test_ihc_alone_without_ish_is_not_over_claimed(self):
        pdf = build_pdf(("SYNTHETIC test document.",
                         "HER2 IHC: EQUIVOCAL (2+)",
                         "No in-situ hybridisation was performed."))
        result = extract_from_document(content=pdf, text=None, is_pdf=True)
        f = _field(result, "her2_status")
        # Equivocal IHC with no ISH cannot yield a definite status.
        assert f.provenance in (FieldProvenance.AMBIGUOUS,
                                FieldProvenance.INFERRED)
        assert f.value is None or "positive" not in (f.value or "").lower() \
            or f.provenance is not FieldProvenance.EXPLICITLY_STATED


# ===========================================================================
# Conflict
# ===========================================================================


class TestConflictDetection:

    @pytest.fixture(scope="class")
    def conflicting(self):
        return _run("synthetic-pdf-conflicting")

    def test_two_stages_are_reported_as_conflicting(self, conflicting):
        f = _field(conflicting, "stage")
        assert f.provenance is FieldProvenance.CONFLICTING
        assert f.alternatives, "the competing reading must be returned"

    def test_both_stage_readings_are_present(self, conflicting):
        f = _field(conflicting, "stage")
        readings = {f.value, *f.alternatives}
        assert "Stage II" in readings
        assert "Stage III" in readings

    def test_two_grades_are_reported_as_conflicting(self, conflicting):
        f = _field(conflicting, "grade")
        assert f.provenance is FieldProvenance.CONFLICTING
        assert {f.value, *f.alternatives} == {"Grade 2", "Grade 3"}

    def test_the_extractor_does_not_choose_a_winner(self, conflicting):
        note = _field(conflicting, "stage").note.lower()
        assert "does not choose" in note or "not reconcile" in note

    def test_conflicting_confidence_is_low(self, conflicting):
        assert _field(conflicting, "stage").confidence <= 0.4

    def test_a_conflict_needs_a_human_decision(self, conflicting):
        assert _field(conflicting, "stage").needs_human_decision is True

    def test_a_repeated_identical_value_is_not_a_conflict(self):
        pdf = build_pdf(("SYNTHETIC test document.",
                         "Clinical stage: Stage IIB",
                         "As above, the clinical stage: Stage IIB."))
        f = _field(extract_from_document(content=pdf, text=None, is_pdf=True),
                   "stage")
        assert f.provenance is FieldProvenance.EXPLICITLY_STATED
        assert f.value == "Stage IIB"


# ===========================================================================
# Missing biomarkers
# ===========================================================================


class TestMissingFields:

    @pytest.fixture(scope="class")
    def sparse(self):
        return _run("synthetic-pdf-sparse")

    def test_untested_biomarkers_are_not_found(self, sparse):
        for key in ("er_status", "pr_status", "her2_ihc", "her2_ish",
                    "her3_status", "ki67", "pdl1"):
            f = _field(sparse, key)
            assert f.provenance is FieldProvenance.NOT_FOUND, key
            assert f.value is None, key

    def test_absence_is_never_filled_with_a_default(self, sparse):
        for f in sparse.fields:
            if f.provenance is FieldProvenance.NOT_FOUND:
                assert f.value is None, f.key

    def test_what_the_document_does_state_is_still_read(self, sparse):
        assert _field(sparse, "cancer_indication").value == "Lung Cancer"
        assert _field(sparse, "metastatic_sites").value

    def test_explicit_not_tested_differs_from_absent(self, breast):
        """'Not tested' is a finding; silence is not."""
        stated = _field(breast, "her3_status")
        assert stated.provenance is FieldProvenance.EXPLICITLY_STATED
        assert "not tested" in stated.value.lower()


# ===========================================================================
# Negation — the most dangerous failure mode
# ===========================================================================


class TestNegationHandling:

    def test_no_systemic_therapy_is_not_read_as_therapy_given(self, breast):
        f = _field(breast, "current_treatment")
        assert "no prior systemic therapy" in f.value.lower()
        # The inverted reading must not appear.
        assert f.value.lower() != "therapy administered prior to surgery"

    def test_no_metastatic_disease_is_not_read_as_metastasis(self, breast):
        f = _field(breast, "metastatic_sites")
        assert "no distant metastatic disease" in f.value.lower()

    def test_a_stated_metastatic_site_is_still_found(self):
        pdf = build_pdf(("SYNTHETIC test document.",
                         "Metastatic deposits are present in the liver."))
        f = _field(extract_from_document(content=pdf, text=None, is_pdf=True),
                   "metastatic_sites")
        assert "liver" in f.value.lower()

    def test_negative_genomic_result_is_reported_as_negative(self, breast):
        value = _field(breast, "genomic_alterations").value.lower()
        assert "brca" in value
        assert "negative" in value or "not detected" in value


# ===========================================================================
# Scanned documents and OCR
# ===========================================================================


class TestScannedDocuments:

    def test_ocr_is_genuinely_unavailable(self):
        # This asserts the environment, so the honest message below is accurate.
        assert ocr_available() is False

    def test_scanned_pdf_is_detected(self):
        pdf = pdf_fixture_by_slug("synthetic-pdf-scanned").as_bytes()
        reading = extract_pdf_text(pdf)
        assert reading.is_scanned is True
        assert reading.readable is False

    def test_scanned_pdf_yields_document_unreadable(self):
        result = _run("synthetic-pdf-scanned")
        assert result.status is EngineStatus.DOCUMENT_UNREADABLE

    def test_scanned_pdf_explains_that_ocr_is_missing(self):
        message = _run("synthetic-pdf-scanned").message.lower()
        assert "optical character recognition" in message
        assert "nothing has been guessed" in message

    def test_scanned_pdf_invents_no_field(self):
        for f in _run("synthetic-pdf-scanned").fields:
            assert f.provenance is FieldProvenance.NOT_FOUND, f.key
            assert f.value is None, f.key

    def test_text_pdf_is_not_misreported_as_scanned(self):
        reading = extract_pdf_text(
            pdf_fixture_by_slug("synthetic-pdf-breast-oncology").as_bytes())
        assert reading.is_scanned is False
        assert reading.readable is True


# ===========================================================================
# Failure handling
# ===========================================================================


class TestFailureHandling:

    def test_corrupt_pdf_degrades_gracefully(self):
        result = extract_from_document(content=b"%PDF-1.4\ngarbage" * 20,
                                       text=None, is_pdf=True)
        assert result.status in (EngineStatus.DOCUMENT_UNREADABLE,
                                 EngineStatus.FAILED)
        assert all(f.value is None for f in result.fields)

    def test_empty_text_document_is_unreadable(self):
        result = extract_from_document(content=None, text="   ", is_pdf=False)
        assert result.status is EngineStatus.DOCUMENT_UNREADABLE

    def test_extractor_exception_yields_no_partial_result(self, monkeypatch):
        from nanobio_studio.app.reports import extraction as module

        def _boom(_pages):
            raise RuntimeError("extractor exploded")

        monkeypatch.setattr(module, "extract_clinical_fields", _boom)
        result = extract_from_document(content=None, text="Stage IIB reported.",
                                       is_pdf=False)
        assert result.status is EngineStatus.FAILED
        assert all(f.value is None for f in result.fields)
        assert "manually" in result.message.lower()

    def test_manual_entry_fallback_survives_failure(self, monkeypatch):
        """A failed extraction must still present the full field set."""
        from nanobio_studio.app.reports import extraction as module

        monkeypatch.setattr(module, "extract_clinical_fields",
                            lambda _p: (_ for _ in ()).throw(ValueError("x")))
        result = extract_from_document(content=None, text="Some report text.",
                                       is_pdf=False)
        assert len(result.fields) == len(CLINICAL_FIELDS)

    def test_plain_text_documents_still_extract(self):
        result = extract_from_document(
            content=None,
            text="SYNTHETIC. Clinical stage: Stage IIB. ER: POSITIVE.",
            is_pdf=False)
        assert result.status is EngineStatus.COMPLETED
        assert _field(result, "stage").value == "Stage IIB"
        assert _field(result, "er_status").value == "Positive"


# ===========================================================================
# The scientific-isolation guarantee, restated at the field level
# ===========================================================================


class TestFieldsAreNotConsumed:

    def test_no_field_is_marked_as_consumed_by_an_engine(self):
        from nanobio_studio.app.services.report_service import _result_to_dict

        result = extract_from_document(
            content=None, text="SYNTHETIC. Clinical stage: Stage IIB.",
            is_pdf=False)
        for field in _result_to_dict(result)["fields"]:
            assert field["consumed_by_engines"] is False, field["key"]

    def test_only_three_fields_map_onward(self):
        mapped = {f["maps_to_workflow"] for f in CLINICAL_FIELDS
                  if f["maps_to_workflow"]}
        assert mapped == {"disease", "subtype", "drug"}

    def test_indication_maps_to_a_curated_disease_name(self, breast):
        """So a confirmed indication can flow onward without a second guess."""
        from nanobio_studio.app.reports.disease_mapping import load_mapping

        assert _field(breast, "cancer_indication").value in load_mapping()
