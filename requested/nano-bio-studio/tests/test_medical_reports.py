"""Tests for the Medical Report Assessment pathway.

The load-bearing tests here are the honesty and safety ones:

* extraction reports itself as unavailable and invents nothing;
* an inferred or ambiguous reading can never become a confirmed value without
  an explicit human decision;
* real patient data is refused at intake;
* file type is decided by content, never by filename or client MIME type;
* executables, archives and active-content PDFs are refused;
* nothing sensitive reaches the audit trail;
* a report value cannot alter a scientific calculation.
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
from fastapi.testclient import TestClient  # noqa: E402

REPORTS = "/api/v1/reports"

ADMIN_USER, ADMIN_PASSWORD = "rpt_admin", "RptAdmin-2026!"
VIEWER_USER, VIEWER_PASSWORD = "rpt_viewer", "RptViewer-2026!"

client: TestClient

SYNTHETIC_TEXT = (
    b"SYNTHETIC DEMONSTRATION DOCUMENT -- NOT A REAL MEDICAL REPORT\n"
    b"This document is fictional and invented for software testing.\n"
    b"Diagnosis: invasive ductal carcinoma of the left breast.\n"
)


@pytest.fixture(scope="module", autouse=True)
def _client(tmp_path_factory):
    global client

    from tests.conftest import make_isolated_auth_client, run_async

    app, test_client, factory = make_isolated_auth_client(
        tmp_path_factory.mktemp("reports_auth"))

    from nanobio_studio.app.db.auth_models import UserRole
    from nanobio_studio.app.services.auth_service import create_user

    async def _seed():
        async with factory() as session:
            for name, password, role in (
                (ADMIN_USER, ADMIN_PASSWORD, UserRole.ADMIN),
                (VIEWER_USER, VIEWER_PASSWORD, UserRole.VIEWER),
            ):
                try:
                    await create_user(session, username=name, password=password,
                                      role=role)
                except ValueError:
                    pass
            await session.commit()

    run_async(_seed())

    with test_client:
        assert test_client.post("/api/v1/auth/login",
                                json={"username": ADMIN_USER,
                                      "password": ADMIN_PASSWORD}
                                ).status_code == 200
        client = test_client
        yield test_client

    app.dependency_overrides.clear()


def _as_admin():
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login",
                json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})


def _as_viewer():
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login",
                json={"username": VIEWER_USER, "password": VIEWER_PASSWORD})


def _upload(content: bytes = SYNTHETIC_TEXT, filename: str = "report.txt",
            classification: str = "synthetic", attested: bool = True):
    return client.post(
        REPORTS,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        data={"classification": classification, "attested": str(attested).lower()},
    )


def _load_fixture(slug: str = "synthetic-breast-pathology"):
    r = client.post(f"{REPORTS}/synthetic/{slug}")
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# Extraction is honestly unavailable
# ===========================================================================


class TestExtractionHonesty:
    """The engine is connected. These assert it is honest about what it did."""

    def test_engine_reports_itself_as_connected(self):
        from nanobio_studio.app.reports.extraction import engine_is_connected

        assert engine_is_connected() is True

    def test_upload_reports_a_completed_extraction(self):
        body = _upload().json()
        assert body["extraction"]["status"] == "completed"
        assert body["extraction"]["engine_name"] == "rule-based-oncology-extractor"
        assert body["extraction"]["engine_version"]

    def test_values_are_grounded_in_the_document(self):
        """Every stated value must carry the excerpt that produced it."""
        fields = _upload().json()["extraction"]["fields"]
        stated = [f for f in fields if f["provenance"] == "explicitly_stated"]
        assert stated, "the fixture text should yield at least one field"
        for field in stated:
            assert field["supporting_text"], field["key"]
            assert field["page"], field["key"]

    def test_absent_fields_carry_no_value(self):
        for field in _upload().json()["extraction"]["fields"]:
            if field["provenance"] == "not_found":
                assert field["value"] is None, field["key"]

    def test_limitations_state_the_engine_is_unvalidated(self):
        text = " ".join(_upload().json()["extraction"]["limitations"]).lower()
        assert "not a trained model" in text
        assert "unmeasured" in text
        assert "not a probability" in text

    def test_limitations_state_no_clinical_interpretation(self):
        text = " ".join(_upload().json()["extraction"]["limitations"]).lower()
        assert "no clinical interpretation" in text
        assert "no diagnosis" in text
        assert "treatment recommendation" in text

    def test_contract_forbids_a_stated_field_without_evidence(self):
        from nanobio_studio.app.reports.extraction import (
            EngineStatus, ExtractedField, ExtractionResult, FieldProvenance)

        bad = ExtractionResult(
            status=EngineStatus.COMPLETED, engine_name="x", engine_version="1",
            contract_version="1", message="m",
            fields=(ExtractedField(key="stage", label="Stage", value="II",
                                   provenance=FieldProvenance.EXPLICITLY_STATED),))
        with pytest.raises(ValueError, match="supporting text span"):
            bad.validate()

    def test_contract_forbids_a_not_found_field_carrying_a_value(self):
        from nanobio_studio.app.reports.extraction import (
            EngineStatus, ExtractedField, ExtractionResult, FieldProvenance)

        bad = ExtractionResult(
            status=EngineStatus.COMPLETED, engine_name="x", engine_version="1",
            contract_version="1", message="m",
            fields=(ExtractedField(key="stage", label="Stage", value="II",
                                   provenance=FieldProvenance.NOT_FOUND),))
        with pytest.raises(ValueError, match="cannot carry a value"):
            bad.validate()

    def test_contract_forbids_a_conflict_without_the_competing_reading(self):
        from nanobio_studio.app.reports.extraction import (
            EngineStatus, ExtractedField, ExtractionResult, FieldProvenance)

        bad = ExtractionResult(
            status=EngineStatus.COMPLETED, engine_name="x", engine_version="1",
            contract_version="1", message="m",
            fields=(ExtractedField(key="stage", label="Stage", value="II",
                                   provenance=FieldProvenance.CONFLICTING),))
        with pytest.raises(ValueError, match="competing reading"):
            bad.validate()

    def test_engine_versions_are_recorded_on_the_assessment(self):
        detail = client.get(f"{REPORTS}/{_upload().json()['assessment_id']}").json()
        assert detail["extraction_engine"] == "rule-based-oncology-extractor"
        assert detail["extraction_engine_version"]
        assert detail["extraction_contract_version"].startswith(
            "extraction-contract-")


# ===========================================================================
# File validation
# ===========================================================================


class TestFileValidation:

    def test_plain_text_report_is_accepted(self):
        assert _upload().status_code == 201

    def test_pdf_is_accepted_and_its_text_layer_is_read(self):
        from nanobio_studio.app.reports.pdf_fixtures import pdf_fixture_by_slug

        pdf = pdf_fixture_by_slug("synthetic-pdf-breast-oncology").as_bytes()
        body = _upload(content=pdf, filename="report.pdf").json()
        assert body["document_readable"] is True
        assert "invasive ductal carcinoma" in body["document_text"].lower()

    def test_pdf_without_a_text_layer_is_reported_unreadable(self):
        """A scanned document must never be guessed at."""
        from nanobio_studio.app.reports.pdf_fixtures import pdf_fixture_by_slug

        pdf = pdf_fixture_by_slug("synthetic-pdf-scanned").as_bytes()
        body = _upload(content=pdf, filename="scan.pdf").json()
        assert body["extraction"]["status"] == "document_unreadable"
        assert "optical character recognition" in \
            body["extraction"]["message"].lower()

    def test_empty_file_is_refused(self):
        r = _upload(content=b"")
        assert r.status_code == 400
        assert r.json()["error"] == "empty_file"

    def test_oversized_file_is_refused(self):
        from nanobio_studio.app.reports.validation import MAX_UPLOAD_BYTES

        r = _upload(content=b"x" * (MAX_UPLOAD_BYTES + 1))
        assert r.status_code == 413
        assert r.json()["data_available"] is False

    @pytest.mark.parametrize("content,name", [
        (b"MZ\x90\x00" + b"\x00" * 100, "malware.exe"),
        (b"\x7fELF\x02\x01" + b"\x00" * 100, "payload.bin"),
        (b"PK\x03\x04" + b"\x00" * 100, "archive.zip"),
        (b"#!/bin/sh\nrm -rf /\n" + b"x" * 50, "script.sh"),
        (b"<?php system($_GET['c']); ?>" + b"x" * 50, "shell.php"),
    ])
    def test_executables_and_archives_are_refused(self, content, name):
        r = _upload(content=content, filename=name)
        assert r.status_code == 400, name
        assert r.json()["error"] in ("unsafe_file_type", "unsupported_file_type")

    def test_executable_disguised_as_pdf_is_refused_by_content(self):
        """The filename is attacker-controlled; only the content is trusted."""
        r = _upload(content=b"MZ\x90\x00" + b"\x00" * 200,
                    filename="pathology_report.pdf")
        assert r.status_code == 400
        assert r.json()["error"] == "unsafe_file_type"

    def test_non_pdf_content_named_pdf_is_refused(self):
        r = _upload(content=b"just some text, definitely not a pdf" * 3,
                    filename="report.pdf")
        assert r.status_code == 400
        assert r.json()["error"] == "content_does_not_match_extension"

    @pytest.mark.parametrize("marker", [
        b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/OpenAction",
    ])
    def test_pdf_with_active_content_is_refused(self, marker):
        pdf = b"%PDF-1.4\n" + marker + b" (payload)\n" + b"x" * 100
        r = _upload(content=pdf, filename="report.pdf")
        assert r.status_code == 400
        assert r.json()["error"] == "active_content_rejected"

    def test_binary_named_as_text_is_refused(self):
        r = _upload(content=b"\xff\xfe\x00\x01" * 20, filename="report.txt")
        assert r.status_code == 400
        assert r.json()["error"] == "content_not_readable_text"

    def test_unsupported_extension_is_refused(self):
        r = _upload(content=b"some content here to pass the size check",
                    filename="report.docx")
        assert r.status_code == 400
        assert r.json()["error"] == "unsupported_file_type"

    @pytest.mark.parametrize("raw,expected_absent", [
        ("../../../etc/passwd", ".."),
        ("..\\..\\windows\\system32\\config", ".."),
        ("report\x00.txt", "\x00"),
    ])
    def test_dangerous_filenames_are_neutralised(self, raw, expected_absent):
        from nanobio_studio.app.reports.validation import safe_display_name

        safe = safe_display_name(raw)
        assert expected_absent not in safe
        assert "/" not in safe and "\\" not in safe

    def test_stored_name_never_contains_a_path(self):
        body = _upload(filename="../../secret/patient.txt").json()
        assert "/" not in body["display_name"]
        assert ".." not in body["display_name"]


# ===========================================================================
# Intake policy: real patient data is refused
# ===========================================================================


class TestIntakePolicy:

    def test_real_patient_data_is_refused(self):
        r = _upload(classification="real_patient_data")
        assert r.status_code == 400
        assert r.json()["error"] == "real_patient_data_refused"

    def test_refusal_explains_why(self):
        detail = _upload(classification="real_patient_data").json()["detail"]
        assert "encryption at rest" in detail.lower()
        assert "legal basis" in detail.lower()

    def test_refused_upload_stores_nothing(self):
        before = client.get(REPORTS).json()["total"]
        _upload(classification="real_patient_data")
        assert client.get(REPORTS).json()["total"] == before

    def test_attestation_is_required(self):
        r = _upload(attested=False)
        assert r.status_code == 400
        assert r.json()["error"] == "attestation_required"

    def test_deidentified_documents_are_accepted(self):
        assert _upload(classification="deidentified").status_code == 201

    def test_unknown_classification_is_refused(self):
        r = _upload(classification="probably_fine")
        assert r.status_code == 400
        assert r.json()["error"] == "unsupported_classification"

    def test_policy_statement_is_returned_with_every_listing(self):
        statement = client.get(REPORTS).json()["policy_statement"].lower()
        assert "synthetic and de-identified documents only" in statement
        assert "real patient reports are refused" in statement

    def test_identifier_screening_warns_without_blocking(self):
        content = (b"SYNTHETIC test document, fictional content.\n"
                   b"Contact: someone@example.com\n" + b"x" * 40)
        body = _upload(content=content).json()
        warnings = " ".join(body["intake_warnings"]).lower()
        assert "email address" in warnings

    def test_screening_admits_it_is_not_a_guarantee(self):
        warnings = " ".join(_upload().json()["intake_warnings"]).lower()
        assert "does not guarantee" in warnings

    def test_missing_synthetic_marker_is_flagged(self):
        content = b"Pathology report. Diagnosis recorded here." + b"x" * 40
        warnings = " ".join(_upload(content=content).json()["intake_warnings"])
        assert "declared synthetic" in warnings

    def test_attestation_is_recorded_for_audit(self):
        detail = client.get(f"{REPORTS}/{_upload().json()['assessment_id']}").json()
        assert detail["attested"] is True
        assert detail["policy_version"].startswith("intake-policy-")


# ===========================================================================
# Synthetic fixtures
# ===========================================================================


class TestSyntheticFixtures:

    def test_three_fixtures_are_available(self):
        assert len(client.get(f"{REPORTS}/synthetic").json()["reports"]) >= 3

    def test_every_fixture_is_labelled_synthetic(self):
        for r in client.get(f"{REPORTS}/synthetic").json()["reports"]:
            assert r["data_classification"] == "Synthetic demonstration document"

    def test_notice_states_the_patients_do_not_exist(self):
        notice = client.get(f"{REPORTS}/synthetic").json()["notice"].lower()
        assert "do not exist" in notice
        assert "not real patient data" in notice

    def test_fixture_documents_carry_their_own_banner(self):
        from nanobio_studio.app.reports.fixtures import SYNTHETIC_REPORTS

        for report in SYNTHETIC_REPORTS:
            assert "SYNTHETIC DEMONSTRATION DOCUMENT" in report.content
            assert "NOT A REAL MEDICAL REPORT" in report.content

    def test_fixtures_contain_no_stored_extraction_results(self):
        """A fixture is a document. It must not carry answers."""
        from dataclasses import asdict

        from nanobio_studio.app.reports.fixtures import SYNTHETIC_REPORTS

        for report in SYNTHETIC_REPORTS:
            keys = set(asdict(report))
            for forbidden in ("fields", "extraction", "extracted", "result",
                              "confirmed"):
                assert not any(forbidden in k for k in keys), report.slug

    def test_loading_a_fixture_runs_the_real_pipeline(self):
        """The fixture goes through the same extraction path as any upload."""
        body = _load_fixture()
        assert body["extraction"]["status"] == "completed"
        assert body["extraction"]["engine_name"] == "rule-based-oncology-extractor"

    def test_fixture_slug_is_recorded_on_the_assessment(self):
        body = _load_fixture("synthetic-lung-clinic-letter")
        detail = client.get(f"{REPORTS}/{body['assessment_id']}").json()
        assert detail["fixture_slug"] == "synthetic-lung-clinic-letter"
        assert detail["classification"] == "synthetic"

    def test_conflicting_fixture_documents_its_contradictions(self):
        body = _load_fixture("synthetic-colorectal-conflicting")
        text = body["document_text"].lower()
        assert "stage ii" in text and "stage iii" in text
        assert "mss" in text and "msi-high" in text
        assert "deliberate internal contradictions" in text

    def test_unknown_fixture_is_a_structured_404(self):
        r = client.post(f"{REPORTS}/synthetic/not-a-fixture")
        assert r.status_code == 404
        assert r.json()["data_available"] is False


# ===========================================================================
# Review, confirmation and provenance
# ===========================================================================


class TestConfirmation:

    def test_user_entered_value_is_accepted(self):
        aid = _upload().json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "cancer_indication", "value": "Breast Cancer",
             "provenance": "user_entered"}]})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "confirmed"

    @pytest.mark.parametrize("provenance", ["inferred", "ambiguous"])
    def test_inferred_or_ambiguous_cannot_be_confirmed_directly(self, provenance):
        """The central rule: no automatic promotion to a confirmed value."""
        aid = _upload().json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "stage", "value": "Stage II", "provenance": provenance}]})
        assert r.status_code == 400
        assert r.json()["error"] == "provenance_not_confirmable"
        assert "explicitly" in r.json()["detail"].lower()

    def test_not_found_field_may_not_carry_a_value(self):
        aid = _upload().json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "grade", "value": "Grade 3", "provenance": "not_found"}]})
        assert r.status_code == 400
        assert r.json()["error"] == "invalid_field_state"

    def test_unknown_field_is_refused(self):
        aid = _upload().json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "prognosis", "value": "good", "provenance": "user_entered"}]})
        assert r.status_code == 400
        assert r.json()["error"] == "unknown_field"

    def test_a_correction_retains_the_original_value(self):
        aid = _upload().json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "stage", "value": "Stage IIB", "provenance": "user_corrected",
             "original_value": "Stage II"}]})
        assert r.status_code == 200
        stored = r.json()["confirmed_fields"][0]
        assert stored["value"] == "Stage IIB"
        assert stored["original_value"] == "Stage II"

    def test_manual_completion_works_when_the_report_lacks_detail(self):
        """Nothing was extracted, so every field must be enterable by hand."""
        from nanobio_studio.app.reports.extraction import FIELD_KEYS

        aid = _upload().json()["assessment_id"]
        payload = [{"key": k, "value": f"value for {k}",
                    "provenance": "user_entered"} for k in FIELD_KEYS]
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": payload})
        assert r.status_code == 200
        assert len(r.json()["confirmed_fields"]) == len(FIELD_KEYS)

    def test_the_review_screen_lists_every_clinical_field(self):
        detail = client.get(f"{REPORTS}/{_upload().json()['assessment_id']}").json()
        keys = {f["key"] for f in detail["clinical_fields"]}
        for expected in ("cancer_indication", "histological_subtype",
                         "tumor_site", "stage", "grade", "metastatic_sites",
                         "er_status", "pr_status", "her2_ihc", "her2_ish",
                         "her2_status", "her3_status", "ki67", "pdl1",
                         "genomic_alterations", "pathology_findings",
                         "current_treatment", "therapeutic_context",
                         "laboratory_findings", "report_date",
                         "document_type"):
            assert expected in keys

    def test_document_text_is_available_for_review(self):
        body = _upload().json()
        assert "invasive ductal carcinoma" in body["document_text"].lower()


# ===========================================================================
# Mapping into the workflow
# ===========================================================================


class TestWorkflowMapping:

    def _confirmed(self) -> int:
        aid = _upload().json()["assessment_id"]
        client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "cancer_indication", "value": "Breast Cancer",
             "provenance": "user_entered"}]})
        return aid

    def test_valid_triple_is_accepted(self):
        aid = self._confirmed()
        r = client.post(f"{REPORTS}/{aid}/map", json={
            "disease": "Breast Cancer",
            "subtype": "HER2-enriched (ER-, PR-, HER2+)",
            "drug": "Trastuzumab (Herceptin)"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "mapped_to_workflow"
        assert r.json()["mapped_disease"] == "Breast Cancer"

    def test_invalid_combination_is_refused(self):
        aid = self._confirmed()
        r = client.post(f"{REPORTS}/{aid}/map", json={
            "disease": "Breast Cancer",
            "subtype": "Non-Small Cell Lung Cancer (NSCLC)",
            "drug": "Trastuzumab (Herceptin)"})
        assert r.status_code == 400
        assert r.json()["error"] == "invalid_therapeutic_context"

    def test_invented_disease_is_refused(self):
        aid = self._confirmed()
        r = client.post(f"{REPORTS}/{aid}/map", json={
            "disease": "Prostate Cancer", "subtype": "Adenocarcinoma",
            "drug": "Docetaxel"})
        assert r.status_code == 400

    def test_mapping_requires_confirmation_first(self):
        aid = _upload().json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/map", json={
            "disease": "Breast Cancer",
            "subtype": "HER2-enriched (ER-, PR-, HER2+)",
            "drug": "Trastuzumab (Herceptin)"})
        assert r.status_code == 400
        assert r.json()["error"] == "not_confirmed"

    def test_mapping_validates_against_the_curated_data(self):
        from nanobio_studio.app.reports.disease_mapping import (
            is_valid_triple, load_mapping)

        mapping = load_mapping()
        assert "Breast Cancer" in mapping
        assert is_valid_triple("Liver Cancer (HCC)", "AFP-high HCC",
                               "Sorafenib") is True
        assert is_valid_triple("Liver Cancer (HCC)", "AFP-high HCC",
                               "Pembrolizumab") is False


# ===========================================================================
# A report can never alter a calculation
# ===========================================================================


class TestScientificIsolation:

    def test_confirmed_fields_do_not_change_the_design_score(self):
        design = {"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}
        before = client.post("/api/v1/design/score", json=design).json()

        aid = _upload().json()["assessment_id"]
        client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "stage", "value": "Stage IV", "provenance": "user_entered"},
            {"key": "cancer_indication", "value": "Breast Cancer",
             "provenance": "user_entered"}]})

        after = client.post("/api/v1/design/score", json=design).json()
        assert after["design_impact_score"] == before["design_impact_score"]

    def test_the_scoring_schema_accepts_no_clinical_field(self):
        from nanobio_studio.app.schemas.design_score import DesignScoreRequest
        from nanobio_studio.app.reports.extraction import FIELD_KEYS

        accepted = set(DesignScoreRequest.model_fields)
        assert accepted.isdisjoint(set(FIELD_KEYS))

    def test_the_pk_schema_accepts_no_clinical_field(self):
        from nanobio_studio.app.schemas.pk_simulation import PKSimulationRequest
        from nanobio_studio.app.reports.extraction import FIELD_KEYS

        accepted = set(PKSimulationRequest.model_fields)
        assert accepted.isdisjoint(set(FIELD_KEYS))

    def test_only_three_fields_map_onward_at_all(self):
        from nanobio_studio.app.reports.extraction import CLINICAL_FIELDS

        mapped = {f["maps_to_workflow"] for f in CLINICAL_FIELDS
                  if f["maps_to_workflow"]}
        assert mapped == {"disease", "subtype", "drug"}


# ===========================================================================
# Authorisation
# ===========================================================================


class TestAuthorisation:

    def test_upload_requires_authentication(self):
        from nanobio_studio.app.vertical_slice import app

        with TestClient(app) as anonymous:
            r = anonymous.post(
                REPORTS,
                files={"file": ("r.txt", io.BytesIO(SYNTHETIC_TEXT), "text/plain")},
                data={"classification": "synthetic", "attested": "true"})
        assert r.status_code == 401

    def test_viewer_cannot_upload(self):
        _as_viewer()
        r = _upload()
        _as_admin()
        assert r.status_code == 403

    def test_viewer_cannot_delete(self):
        aid = _upload().json()["assessment_id"]
        _as_viewer()
        r = client.delete(f"{REPORTS}/{aid}")
        _as_admin()
        assert r.status_code == 403

    def test_viewer_cannot_confirm(self):
        aid = _upload().json()["assessment_id"]
        _as_viewer()
        r = client.post(f"{REPORTS}/{aid}/confirm", json={"fields": []})
        _as_admin()
        assert r.status_code == 403

    def test_another_users_assessment_is_not_reachable(self):
        aid = _upload().json()["assessment_id"]
        _as_viewer()
        r = client.get(f"{REPORTS}/{aid}")
        _as_admin()
        # 404 not 403: ownership is checked before existence is revealed.
        assert r.status_code == 404

    def test_retention_purge_requires_admin(self):
        _as_viewer()
        r = client.post(f"{REPORTS}/retention/purge")
        _as_admin()
        assert r.status_code == 403


# ===========================================================================
# Deletion, retention and download
# ===========================================================================


class TestLifecycle:

    def test_deletion_removes_the_assessment(self):
        aid = _upload().json()["assessment_id"]
        assert client.delete(f"{REPORTS}/{aid}").status_code == 200
        assert client.get(f"{REPORTS}/{aid}").status_code == 404

    def test_deletion_removes_the_document_body(self):
        from sqlalchemy import select
        from nanobio_studio.app.db.report_models import ReportDocument
        from nanobio_studio.app.db.auth_session import get_auth_session
        from nanobio_studio.app.vertical_slice import app
        from tests.conftest import run_async

        aid = _upload().json()["assessment_id"]
        client.delete(f"{REPORTS}/{aid}")

        override = app.dependency_overrides[get_auth_session]

        async def _count():
            agen = override()
            session = await agen.__anext__()
            try:
                stmt = select(ReportDocument).where(
                    ReportDocument.assessment_id == aid)
                return (await session.execute(stmt)).scalar_one_or_none()
            finally:
                await agen.aclose()

        assert run_async(_count()) is None

    def test_retention_deadline_is_recorded(self):
        body = _upload().json()
        assert body["retain_until"] is not None

    def test_purge_without_confirm_deletes_nothing(self):
        _upload()
        before = client.get(REPORTS).json()["total"]
        r = client.post(f"{REPORTS}/retention/purge")
        assert r.status_code == 200
        assert r.json()["confirmed"] is False
        assert r.json()["deleted"] == 0
        assert client.get(REPORTS).json()["total"] == before

    def test_download_returns_the_original_bytes(self):
        aid = _upload().json()["assessment_id"]
        r = client.get(f"{REPORTS}/{aid}/document")
        assert r.status_code == 200
        assert r.content == SYNTHETIC_TEXT

    def test_download_is_an_attachment_and_not_sniffable(self):
        aid = _upload().json()["assessment_id"]
        r = client.get(f"{REPORTS}/{aid}/document")
        assert r.headers["content-disposition"].startswith("attachment")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["cache-control"] == "no-store"


# ===========================================================================
# De-identification
# ===========================================================================


class TestDeidentification:

    def test_direct_identifiers_are_redacted(self):
        content = (b"SYNTHETIC fictional test document.\n"
                   b"Patient name: Jane Q Example\n"
                   b"Date of birth: 01 January 1970\n"
                   b"Contact: jane@example.com\n"
                   b"Record number: MRN-123456\n")
        aid = _upload(content=content).json()["assessment_id"]
        body = client.post(f"{REPORTS}/{aid}/deidentify").json()

        assert "jane@example.com" not in body["text"]
        assert "MRN-123456" not in body["text"]
        assert body["total_redactions"] > 0

    def test_limitations_are_always_returned(self):
        aid = _upload().json()["assessment_id"]
        body = client.post(f"{REPORTS}/{aid}/deidentify").json()
        text = " ".join(body["limitations"]).lower()
        assert "not hipaa safe harbor" in text
        assert "not certified" in text

    def test_version_is_recorded(self):
        aid = _upload().json()["assessment_id"]
        assert client.post(f"{REPORTS}/{aid}/deidentify").json()["version"]

    def test_unreadable_document_cannot_be_redacted(self):
        pdf = b"%PDF-1.4\n" + b"x" * 200
        aid = _upload(content=pdf, filename="r.pdf").json()["assessment_id"]
        r = client.post(f"{REPORTS}/{aid}/deidentify")
        assert r.status_code == 400
        assert r.json()["error"] == "document_not_readable"


# ===========================================================================
# Audit trail carries no sensitive content
# ===========================================================================


class TestAuditTrail:

    @staticmethod
    def _audit_rows():
        from sqlalchemy import select
        from nanobio_studio.app.db.report_models import ReportAuditLog
        from nanobio_studio.app.db.auth_session import get_auth_session
        from nanobio_studio.app.vertical_slice import app
        from tests.conftest import run_async

        override = app.dependency_overrides[get_auth_session]

        async def _rows():
            agen = override()
            session = await agen.__anext__()
            try:
                return list((await session.execute(
                    select(ReportAuditLog))).scalars().all())
            finally:
                await agen.aclose()

        return run_async(_rows())

    def test_upload_is_audited(self):
        _upload()
        events = {r.event.value for r in self._audit_rows()}
        assert "uploaded" in events

    def test_refusal_is_audited(self):
        _upload(classification="real_patient_data")
        assert "refused" in {r.event.value for r in self._audit_rows()}

    def test_deletion_is_audited_and_the_entry_outlives_the_record(self):
        aid = _upload().json()["assessment_id"]
        client.delete(f"{REPORTS}/{aid}")
        rows = [r for r in self._audit_rows()
                if r.event.value == "deleted" and r.assessment_id == aid]
        assert rows, "deletion must leave an audit entry"

    def test_audit_detail_never_contains_clinical_content(self):
        _upload()
        aid = _upload().json()["assessment_id"]
        client.post(f"{REPORTS}/{aid}/confirm", json={"fields": [
            {"key": "cancer_indication", "value": "Breast Cancer",
             "provenance": "user_entered"}]})

        for row in self._audit_rows():
            detail = (row.detail or "").lower()
            for forbidden in ("carcinoma", "breast", "jane", "patient name",
                              "diagnosis"):
                assert forbidden not in detail, row.detail

    def test_audit_never_stores_the_document_text(self):
        _upload()
        for row in self._audit_rows():
            assert "invasive ductal" not in (row.detail or "").lower()
