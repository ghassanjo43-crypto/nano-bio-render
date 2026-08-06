"""Experimental Validation Registry — Phase 2, Milestone 1.

The sentence this whole suite defends
-------------------------------------
**E3 means "approved in-vitro evidence for a specific scientific purpose, on a
specific candidate version".** Not that the candidate is validated, not that the
study is validated, and not that any other purpose is supported.

Everything below is a way of failing if that stops being true: the nine golden
vectors from the brief, every eligibility gate in both directions, the
permission rules, immutability after approval, and the guarantee that a study
with no approved experiment behaves exactly as it did in Phase 1.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(BACKEND_ROOT), str(REPO_ROOT)):
    if _p in sys.path:
        sys.path.remove(_p)
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker, create_async_engine,
)

from tests.conftest import run_async  # noqa: E402

from nanobio_studio.app.db.base import Base  # noqa: E402
from nanobio_studio.app.db import auth_models  # noqa: E402,F401
from nanobio_studio.app.db import report_models  # noqa: E402,F401
from nanobio_studio.app.db import science_models  # noqa: E402,F401
from nanobio_studio.app.db import workspace_models  # noqa: E402,F401
from nanobio_studio.app.db import validation_models  # noqa: E402,F401
from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.db.migrations import EXPECTED_TABLES  # noqa: E402
from nanobio_studio.app.db.validation_models import (  # noqa: E402
    ExperimentVersion, ValidationAuditLog,
)
from nanobio_studio.app.db.workspace_models import (  # noqa: E402
    RecordOrigin, RunStatus, StoredRun,
)
from nanobio_studio.app.science.rules import evaluate_study  # noqa: E402
from nanobio_studio.app.science.statuses import (  # noqa: E402
    EvidenceLevel, ReadinessArea,
)
from nanobio_studio.app.validation.eligibility import (  # noqa: E402
    GATE_IDS, ExperimentFacts, evaluate_e3_eligibility,
)
from nanobio_studio.app.validation.permissions import (  # noqa: E402
    Capability, ExperimentContext, PermissionDenied, RegistryActor,
    capabilities_for, require,
)
from nanobio_studio.app.validation.vocabulary import (  # noqa: E402
    GRANTABLE_LEVELS, SUBTYPE_PERMITTED_PURPOSES, AttachmentCategory,
    AuditEvent, ExperimentStatus, ExperimentSubtype, ReviewDecision,
    purpose_is_permitted,
)
from nanobio_studio.app.services import validation_service as svc  # noqa: E402

A = ReadinessArea
ST = ExperimentSubtype

PERFORMER = RegistryActor(user_id=1, role=UserRole.RESEARCHER)
REVIEWER = RegistryActor(user_id=2, role=UserRole.RESEARCHER)
ADMIN = RegistryActor(user_id=3, role=UserRole.ADMIN)
VIEWER = RegistryActor(user_id=4, role=UserRole.VIEWER)


async def _fresh_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = maker()
    await session.execute(text(
        "INSERT INTO auth_users (id, username, email, password_hash, role, "
        "is_active, created_at) VALUES "
        "(1, 'performer', 'p@x.invalid', 'x', 'RESEARCHER', 1, '2026-08-01'), "
        "(2, 'reviewer',  'r@x.invalid', 'x', 'RESEARCHER', 1, '2026-08-01'), "
        "(3, 'admin',     'a@x.invalid', 'x', 'ADMIN', 1, '2026-08-01'), "
        "(4, 'viewer',    'v@x.invalid', 'x', 'VIEWER', 1, '2026-08-01')"))
    await session.commit()
    return engine, session


async def _study(session, owner_id=1) -> StoredRun:
    run = StoredRun(owner_id=owner_id, name="Registry study",
                    origin=RecordOrigin.USER, status=RunStatus.COMPLETE)
    session.add(run)
    await session.flush()
    return run


DESIGN = {"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}


async def _candidate_version(session, study_id, design=None):
    candidate = await svc.create_candidate(
        session, actor=PERFORMER, study_id=study_id, code="CAND-1",
        name="Liposome A")
    return await svc.create_candidate_version(
        session, actor=PERFORMER, candidate_id=candidate.id,
        design_inputs=design or DESIGN)


#: A record that satisfies every gate. Each golden vector below is this, minus
#: exactly one thing — which is what makes each vector a test of one gate.
def _complete_fields(**overrides):
    fields = dict(
        scientific_question="Does candidate A reduce viability in SK-BR-3?",
        hypothesis="Viability falls below 50% at 10 ug/mL.",
        laboratory_name="In-house cell culture laboratory",
        investigator_name="A. Investigator",
        investigator_org="NanoBio Studio Research",
        protocol_identifier="PROT-CYTO-01",
        protocol_version="1.2",
        biological_model="Human breast adenocarcinoma",
        cell_line="SK-BR-3",
        cell_source="ATCC HTB-30",
        cell_authentication_status="STR authenticated 2026-01",
        assay_method="MTT viability assay, 48 h exposure",
        control_positive="Doxorubicin 1 uM",
        control_negative="Untreated cells",
        control_vehicle="0.1% DMSO",
        biological_replicates=3,
        technical_replicates=3,
        replicate_justification="Three independent preparations.",
        statistical_method="One-way ANOVA with Dunnett correction",
        disclosures_confirmed=True,
        deviations="None",
        exclusions="None",
        missing_data="None",
        investigator_conclusion="Criteria met.",
        provenance_declaration="Data generated in-house; raw plate reads "
                               "attached.",
        acceptance_criteria_met=True,
        requested_level=EvidenceLevel.E3,
        acceptance_criteria_json=json.dumps([
            {"endpoint": "viability_percent", "comparator": "<=",
             "value": 50, "unit": "%",
             "description": "Viability at 10 ug/mL must be at or below 50%."}
        ]),
    )
    fields.update(overrides)
    return fields


MEASUREMENTS = [
    {"endpoint_name": "viability_percent", "sample_group": "10 ug/mL",
     "replicate_id": f"R{i}", "result_numeric": value, "result_unit": "%",
     "method": "MTT"}
    for i, value in enumerate((41.0, 44.5, 39.2), start=1)
]


async def _build_qualifying(session, *, study_id, subtype=ST.CYTOTOXICITY,
                            purpose=A.SAFETY_ASSESSMENT, field_overrides=None,
                            measurements=MEASUREMENTS, attach_raw=True,
                            code="EXP-0001", candidate_version=None):
    """Build an experiment that passes every gate, then optionally break one."""
    cversion = candidate_version or await _candidate_version(session, study_id)
    experiment, version = await svc.create_experiment(
        session, actor=PERFORMER, candidate_version_id=cversion.id,
        subtype=subtype, purpose=purpose, title="Cytotoxicity of candidate A",
        code=code)

    fields = _complete_fields(**(field_overrides or {}))
    await svc.update_draft(session, actor=PERFORMER, version_id=version.id,
                           fields=fields)
    if measurements:
        await svc.add_measurements(session, actor=PERFORMER,
                                   version_id=version.id, rows=measurements)
    if attach_raw:
        await svc.record_attachment(
            session, actor=PERFORMER, version_id=version.id,
            category=AttachmentCategory.RAW_DATA,
            original_filename="plate-reads.csv", mime_type="text/csv",
            size_bytes=2048, checksum_sha256="a" * 64, storage_key="k1")
    return experiment, version, cversion


async def _approve(session, version_id, actor=REVIEWER, comments="Reviewed."):
    await svc.submit_version(session, actor=PERFORMER, version_id=version_id)
    await svc.start_review(session, actor=actor, version_id=version_id)
    return await svc.record_decision(
        session, actor=actor, version_id=version_id,
        decision=ReviewDecision.APPROVE, comments=comments)


# ===========================================================================
# 1. Migrations and schema
# ===========================================================================


class TestMigrations:

    def test_every_registry_table_is_declared(self):
        for table in ("validation_candidates", "validation_candidate_versions",
                      "validation_experiments",
                      "validation_experiment_versions",
                      "validation_measurements", "validation_attachments",
                      "validation_audit_log"):
            assert table in EXPECTED_TABLES, table

    def test_every_column_added_to_a_registry_table_is_declared_here(self):
        """Narrowed twice now, and each narrowing was a decision.

        As written for Milestone 1 this asserted that *no* registry table is
        ever ALTERed, which was true then: the registry arrived as whole new
        tables and an upgrade touched nothing.

        Production Hardening added ``organization_id`` to every scoped table.
        The object-storage work added the attachment lifecycle columns —
        ``state``, ``storage_backend``, ``storage_bucket``, ``state_changed_at``,
        ``delete_attempts``, ``last_error_code`` and ``content_removed_at`` —
        because the database and the object store are two systems that can
        disagree, and a row needs somewhere to say how.

        What survives every narrowing is the part that protects the data: an
        added column must be **nullable or defaulted**, so an existing row
        stays valid without a rewrite, and it must not carry a blanket backfill
        that states something the migration cannot know.

        Any further ALTER on a registry table has to be added to this list,
        which is the point of the test.
        """
        from nanobio_studio.app.db.migrations import ADDITIVE_COLUMNS

        permitted = {
            "organization_id",
            # Attachment lifecycle. See db/validation_models.AttachmentState.
            "state", "storage_backend", "storage_bucket", "state_changed_at",
            "delete_attempts", "last_error_code", "content_removed_at",

            # Candidate revision and supersession. A candidate version was an
            # append-only snapshot with an ordinal and nothing else: no link to
            # what it came from, no way to say it had been relied upon, and no
            # record of the rules its numbers were produced under. Every column
            # below exists so that a scientific decision made on one version
            # stays attributable to that version after the formulation moves on.
            #
            #   lineage      predecessor_version_id, revision_reason,
            #                revision_label
            #   workflow     status, locked_at, lock_reason
            #   results      results_state, results_inherited_from_id
            #   provenance   model_version, ruleset_version,
            #                reference_data_version, algorithm_selection
            #   supersession supersession_state, superseded_by_version_id,
            #                superseded_at, superseded_by_user_id,
            #                supersession_reason, supersession_decision_id
            #   concurrency  revision
            "predecessor_version_id", "revision_reason", "revision_label",
            "status", "locked_at", "lock_reason",
            "results_state", "results_inherited_from_id",
            "model_version", "ruleset_version", "reference_data_version",
            "algorithm_selection",
            "supersession_state", "superseded_by_version_id", "superseded_at",
            "superseded_by_user_id", "supersession_reason",
            "supersession_decision_id",
            "revision",

            # Exact-version binding for records that already existed.
            #
            #   validation_attachments.candidate_version_id
            #       The formulation a file is evidence for was reachable only
            #       through a join to the experiment version. Denormalising it
            #       makes "which version is this evidence for" one indexed
            #       predicate that a listing query cannot forget to make.
            #       Nullable, and NOT backfilled here: the value is derivable,
            #       but a two-table UPDATE that guesses on a mismatch is what
            #       the legacy migration exists to avoid. That migration binds
            #       them and reports anything it declines to resolve.
            #
            #   validation_audit_log.candidate_id
            #       The trail recorded the version but not the candidate, so a
            #       candidate's history could not be assembled without joining
            #       to a table the trail deliberately has no foreign key into —
            #       and it has none because it must outlive its subject.
            #
            #   validation_audit_log.reason
            #       The actor's stated reason, kept apart from the summary the
            #       application composes. Mixing them makes it impossible to
            #       tell an explanation from a description, and the brief
            #       requires every version event to carry a reason.
            "candidate_version_id", "candidate_id", "reason",
        }
        #: Columns whose NOT NULL is acceptable because the default restates
        #: what every existing row already was.
        permitted_not_null = {
            "state", "delete_attempts",
            # An existing version was, by definition, a draft that nothing had
            # formally locked — there was no mechanism to lock one. DRAFT is
            # what they were, not a guess. The dedicated migration then locks
            # the ones with dependents, which needs a join and is not something
            # a column default can decide.
            "status",
            # No existing row recorded whether its derived values were current,
            # so NONE is the only honest starting point. Claiming CURRENT for
            # numbers whose provenance was never captured would be a
            # fabrication dressed as a default.
            "results_state",
            # Nothing had been superseded, because supersession did not exist.
            "supersession_state",
            # Optimistic concurrency starts at 1 for every row.
            "revision",
        }
        #: The only backfills allowed, and what each restates rather than guesses.
        permitted_backfills = {
            # Before this column existed, every attachment was written by the
            # local driver — it was the only one. Saying so is a restatement.
            "storage_backend",
            # "v" || version_number. A pure restatement of a column that is
            # already there, so no information is invented.
            "revision_label",
        }

        for column in ADDITIVE_COLUMNS:
            if not column.table.startswith("validation_"):
                continue
            assert column.column in permitted, (
                f"{column.table}.{column.column} would ALTER a registry table "
                f"and is not in the permitted set. Add it here deliberately, "
                f"with a reason, or do not add the column.")

            if column.column in permitted_not_null:
                # NOT NULL is acceptable only with a default that restates
                # what existing rows already were.
                assert "DEFAULT" in column.ddl.upper(), (
                    f"{column.table}.{column.column} is NOT NULL without a "
                    f"default, so adding it would invalidate every existing "
                    f"row.")
            else:
                assert "NOT NULL" not in column.ddl.upper(), (
                    f"{column.table}.{column.column} is NOT NULL, so adding "
                    f"it would invalidate every existing row.")

            if column.backfill is not None:
                assert column.column in permitted_backfills, (
                    f"{column.table}.{column.column} carries a raw SQL "
                    f"backfill. A backfill must restate a fact the migration "
                    f"can be certain of, not assert one it is guessing.")

    def test_the_attachment_state_default_matches_what_existing_rows_were(self):
        """AVAILABLE, because a row's existence *was* the claim.

        Before the lifecycle column, an attachment row meant "the object is
        there" — there was no other state it could be in. Defaulting to
        AVAILABLE restates that. Defaulting to PENDING_UPLOAD would make every
        pre-existing attachment undownloadable on upgrade.
        """
        from nanobio_studio.app.db.migrations import ADDITIVE_COLUMNS

        spec = next(c for c in ADDITIVE_COLUMNS
                    if c.table == "validation_attachments"
                    and c.column == "state")
        assert "'AVAILABLE'" in spec.ddl

    def test_a_clean_database_builds_every_table(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                rows = (await session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ))).scalars().all()
                for table in EXPECTED_TABLES:
                    assert table in rows, table
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 2. Golden vectors — the nine cases from the brief
# ===========================================================================


class TestGoldenVectors:
    """One qualifying record, and eight ways of not qualifying.

    Each vector is the complete record minus exactly one requirement, so a
    failure names the gate that broke rather than leaving it to be found.
    """

    def test_v1_a_complete_qualifying_e3_experiment(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                _, verdict = await _approve(session, version.id)

                assert verdict is not None and verdict.eligible
                assert verdict.approved_level is EvidenceLevel.E3
                assert verdict.failed_gates == []
                assert len(verdict.passed_gates) >= 15
                assert "supports that purpose on that candidate version only" \
                    in verdict.explanation

                stored = await session.get(ExperimentVersion, version.id)
                assert stored.status is ExperimentStatus.APPROVED
                assert stored.approved_level is EvidenceLevel.E3
                assert stored.eligibility_ruleset_version
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v2_a_missing_control_is_refused(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id,
                    field_overrides={"control_negative": None,
                                     "control_vehicle": None})
                verdict = await svc.evaluate_version(
                    session, version_id=version.id, assume_approved_by=2)
                failed = {g.id for g in verdict.failed_gates}
                assert "controls_present" in failed
                assert not verdict.eligible
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v3_missing_raw_data_provenance_is_refused(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id, attach_raw=False,
                    field_overrides={"raw_data_reference": None})
                verdict = await svc.evaluate_version(
                    session, version_id=version.id, assume_approved_by=2)
                failed = {g.id for g in verdict.failed_gates}
                assert "raw_data_available" in failed
                gate = next(g for g in verdict.gates
                            if g.id == "raw_data_available")
                assert "cannot be its own source" in gate.detail
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v4_an_experiment_linked_to_the_wrong_candidate_version(self):
        """The snapshot no longer matches the checksum recorded at link time.

        Simulates a candidate version being altered after the experiment was
        attached to it — the exact failure the immutable snapshot exists to
        make detectable rather than silent.
        """
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, cversion = await _build_qualifying(
                    session, study_id=study.id)

                cversion.design_snapshot_json = json.dumps(
                    {"size_nm": 250, "charge_mv": -5,
                     "encapsulation_percent": 85}, sort_keys=True,
                    separators=(",", ":"))
                await session.flush()

                verdict = await svc.evaluate_version(
                    session, version_id=version.id, assume_approved_by=2)
                failed = {g.id for g in verdict.failed_gates}
                assert "candidate_snapshot_integrity" in failed
                gate = next(g for g in verdict.gates
                            if g.id == "candidate_snapshot_integrity")
                assert "has changed since the experiment was linked" in gate.detail
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v5_failed_acceptance_criteria(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                # Viability well above the <= 50% criterion.
                failing = [dict(m, result_numeric=value) for m, value
                           in zip(MEASUREMENTS, (88.0, 91.5, 86.2))]
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id, measurements=failing,
                    field_overrides={"acceptance_criteria_met": False})
                verdict = await svc.evaluate_version(
                    session, version_id=version.id, assume_approved_by=2)
                failed = {g.id for g in verdict.failed_gates}
                assert "acceptance_criteria_satisfied" in failed
                assert not verdict.eligible

                # And the record survives: a failed experiment is preserved.
                stored = await session.get(ExperimentVersion, version.id)
                assert stored is not None
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v6_an_unresolved_critical_quality_issue(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id,
                    field_overrides={"quality_issues_json": json.dumps([
                        {"severity": "critical",
                         "description": "Plate reader calibration expired.",
                         "resolved": False}])})
                verdict = await svc.evaluate_version(
                    session, version_id=version.id, assume_approved_by=2)
                failed = {g.id for g in verdict.failed_gates}
                assert "no_unresolved_critical_quality_issue" in failed
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v7_a_self_approved_record_is_refused(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)

                # The performer cannot even start their own review.
                with pytest.raises(PermissionDenied):
                    await svc.start_review(session, actor=PERFORMER,
                                           version_id=version.id)

                await svc.start_review(session, actor=REVIEWER,
                                       version_id=version.id)
                with pytest.raises(PermissionDenied) as exc:
                    await svc.record_decision(
                        session, actor=PERFORMER, version_id=version.id,
                        decision=ReviewDecision.APPROVE, comments="Mine.")
                assert "cannot approve it" in str(exc.value)

                stored = await session.get(ExperimentVersion, version.id)
                assert stored.status is ExperimentStatus.UNDER_REVIEW
                assert stored.approved_level is None
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v8_conflicting_approved_experiments_hold_the_level(self):
        """Two approved records for one purpose that disagree.

        The favourable one must not be preferred. The level is held and the
        conflict is reported, with both records preserved.
        """
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                cversion = await _candidate_version(session, study.id)

                _, passing, _ = await _build_qualifying(
                    session, study_id=study.id, code="EXP-PASS",
                    candidate_version=cversion)
                await _approve(session, passing.id)

                # A second approved experiment for the same purpose whose
                # criteria were not met. Its criteria are narrative, so the
                # investigator's determination carries the gate.
                _, failing, _ = await _build_qualifying(
                    session, study_id=study.id, code="EXP-FAIL",
                    candidate_version=cversion,
                    measurements=[{
                        "endpoint_name": "haemolysis_observed",
                        "result_text": "none observed", "method": "visual"}],
                    field_overrides={
                        "acceptance_criteria_json": json.dumps([
                            {"description": "No haemolysis at any dose."}]),
                        "acceptance_criteria_met": False,
                    })
                # It cannot be approved while its criteria are unmet...
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=failing.id)
                await svc.start_review(session, actor=REVIEWER,
                                       version_id=failing.id)
                with pytest.raises(svc.ValidationError):
                    await svc.record_decision(
                        session, actor=REVIEWER, version_id=failing.id,
                        decision=ReviewDecision.APPROVE, comments="ok")

                # ...so the contradiction is constructed the only way it can
                # legitimately arise: an approved record later determined not
                # to have met its criteria.
                stored = await session.get(ExperimentVersion, failing.id)
                stored.status = ExperimentStatus.APPROVED
                stored.approved_level = EvidenceLevel.E3
                stored.acceptance_criteria_met = False
                await session.flush()

                evidence = await svc.approved_evidence_for_study(
                    session, study_id=study.id)
                entry = evidence[A.SAFETY_ASSESSMENT.value]
                assert entry["contradiction"] is not None
                assert "has not been preferred" in entry["contradiction"]
                assert entry["level"] is None
                assert len(entry["experiments"]) == 2
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_v9_one_candidate_different_levels_per_purpose(self):
        """E3 for safety, unchanged for everything else.

        The property that stops one experiment validating a whole candidate.
        """
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await _approve(session, version.id)

                evidence = await svc.approved_evidence_for_study(
                    session, study_id=study.id)
                assert set(evidence) == {A.SAFETY_ASSESSMENT.value}
                assert evidence[A.SAFETY_ASSESSMENT.value]["level"] == "E3"

                # Every other purpose is absent, so the engine promotes none.
                for area in ReadinessArea:
                    if area is A.SAFETY_ASSESSMENT:
                        continue
                    assert area.value not in evidence
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 3. Every gate, in both directions
# ===========================================================================


class TestEligibilityGates:

    def test_every_declared_gate_runs(self):
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3)
        verdict = evaluate_e3_eligibility(facts)
        assert {g.id for g in verdict.gates} == set(GATE_IDS)

    def test_an_empty_draft_is_not_eligible(self):
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3)
        verdict = evaluate_e3_eligibility(facts)
        assert not verdict.eligible
        assert verdict.missing_requirements

    def test_all_gates_run_even_after_one_fails(self):
        """No short-circuit.

        A verdict that stopped at the first failure would be correct and
        useless: the next problem would only be discovered after fixing this
        one.
        """
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3)
        verdict = evaluate_e3_eligibility(facts)
        assert len(verdict.failed_gates) > 5

    def test_the_verdict_is_deterministic(self):
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3)
        assert (evaluate_e3_eligibility(facts).to_dict()
                == evaluate_e3_eligibility(facts).to_dict())

    def test_the_verdict_records_its_ruleset_version(self):
        from nanobio_studio.app.validation.vocabulary import REGISTRY_VERSION
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=None)
        assert evaluate_e3_eligibility(facts).ruleset_version == REGISTRY_VERSION

    def test_e3_is_never_inferred_from_experiment_type(self):
        """A cytotoxicity assay is not evidence because of what it is."""
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.APPROVED, requested_level=EvidenceLevel.E3,
            approved=True, decision_by=2, performed_by=1)
        assert not evaluate_e3_eligibility(facts).eligible

    def test_replicate_counts_must_be_reported_but_no_minimum_is_imposed(self):
        """Disclosure is required; sufficiency is the reviewer's judgement."""
        base = dict(subtype=ST.ZETA_POTENTIAL,
                    purpose=A.FORMULATION_ASSESSMENT,
                    status=ExperimentStatus.DRAFT,
                    requested_level=EvidenceLevel.E3)

        unreported = evaluate_e3_eligibility(ExperimentFacts(**base))
        gate = next(g for g in unreported.gates if g.id == "replicates_reported")
        assert not gate.passed

        # n=1 is disclosed, and passes: a low n reported is a different problem
        # from an n nobody stated, and no universal minimum is hard-coded.
        single = evaluate_e3_eligibility(ExperimentFacts(
            **base, biological_replicates=1, technical_replicates=1))
        gate = next(g for g in single.gates if g.id == "replicates_reported")
        assert gate.passed
        assert "reviewer judgement" in gate.detail

    def test_criteria_recorded_after_the_results_are_refused(self):
        now = datetime.now(timezone.utc)
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3,
            acceptance_criteria=[{"description": "x"}],
            acceptance_criteria_recorded_at=now,
            first_measurement_recorded_at=now - timedelta(hours=2))
        gate = next(g for g in evaluate_e3_eligibility(facts).gates
                    if g.id == "acceptance_criteria_predefined")
        assert not gate.passed
        assert "cannot fail" in gate.detail

    def test_a_numeric_result_without_a_unit_is_refused(self):
        facts = ExperimentFacts(
            subtype=ST.ZETA_POTENTIAL, purpose=A.FORMULATION_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3,
            measurements=[{"endpoint_name": "zeta", "result_numeric": -12.4}])
        gate = next(g for g in evaluate_e3_eligibility(facts).gates
                    if g.id == "structured_results_recorded")
        assert not gate.passed
        assert "not a measurement" in gate.detail

    def test_an_unjustified_exclusion_is_refused(self):
        facts = ExperimentFacts(
            subtype=ST.ZETA_POTENTIAL, purpose=A.FORMULATION_ASSESSMENT,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3,
            disclosures_confirmed=True,
            measurements=[{"endpoint_name": "zeta", "result_numeric": -12.4,
                           "result_unit": "mV", "excluded": True}])
        gate = next(g for g in evaluate_e3_eligibility(facts).gates
                    if g.id == "disclosures_made")
        assert not gate.passed
        assert "without a justification" in gate.detail
        assert "selected result" in (gate.remedy or "")

    def test_a_level_above_e3_cannot_be_requested(self):
        for level in (EvidenceLevel.E4, EvidenceLevel.E5, EvidenceLevel.E6):
            facts = ExperimentFacts(
                subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
                status=ExperimentStatus.DRAFT, requested_level=level)
            verdict = evaluate_e3_eligibility(facts)
            assert not verdict.eligible
            assert any(g.id == "requested_level_grantable"
                       for g in verdict.failed_gates)


# ===========================================================================
# 4. Purpose is not a loophole
# ===========================================================================


class TestPurposeCompatibility:

    def test_a_cytotoxicity_assay_cannot_claim_structural_visualization(self):
        assert not purpose_is_permitted(ST.CYTOTOXICITY,
                                        A.STRUCTURAL_VISUALIZATION)

    def test_no_in_vitro_subtype_can_claim_pharmacokinetics(self):
        """Nothing in a cell-culture plate observes distribution or clearance."""
        for subtype in ExperimentSubtype:
            assert not purpose_is_permitted(subtype,
                                            A.PHARMACOKINETIC_MODELLING)

    def test_no_in_vitro_subtype_can_claim_cinematic_animation(self):
        for subtype in ExperimentSubtype:
            assert not purpose_is_permitted(subtype, A.CINEMATIC_ANIMATION)

    def test_every_subtype_declares_its_permitted_purposes(self):
        for subtype in ExperimentSubtype:
            assert subtype in SUBTYPE_PERMITTED_PURPOSES, subtype

    def test_an_incompatible_pairing_is_refused_at_creation(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                cversion = await _candidate_version(session, study.id)
                with pytest.raises(svc.ValidationError) as exc:
                    await svc.create_experiment(
                        session, actor=PERFORMER,
                        candidate_version_id=cversion.id,
                        subtype=ST.CYTOTOXICITY,
                        purpose=A.STRUCTURAL_VISUALIZATION,
                        title="Wrong purpose", code="EXP-BAD")
                assert exc.value.code == "purpose_not_permitted"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_the_gate_catches_it_even_if_creation_did_not(self):
        facts = ExperimentFacts(
            subtype=ST.CYTOTOXICITY, purpose=A.STRUCTURAL_VISUALIZATION,
            status=ExperimentStatus.DRAFT, requested_level=EvidenceLevel.E3)
        gate = next(g for g in evaluate_e3_eligibility(facts).gates
                    if g.id == "purpose_compatible_with_subtype")
        assert not gate.passed


# ===========================================================================
# 5. Permissions
# ===========================================================================


class TestPermissions:

    DRAFT = ExperimentContext(owner_id=1, status=ExperimentStatus.DRAFT,
                              performed_by=1)
    REVIEWING = ExperimentContext(owner_id=1,
                                  status=ExperimentStatus.UNDER_REVIEW,
                                  performed_by=1)
    APPROVED = ExperimentContext(owner_id=1,
                                 status=ExperimentStatus.APPROVED,
                                 performed_by=1)

    def test_a_viewer_can_only_read(self):
        caps = capabilities_for(VIEWER, self.DRAFT)
        assert Capability.VIEW in caps
        assert Capability.EDIT_DRAFT not in caps
        assert Capability.APPROVE not in caps

    def test_an_administrator_cannot_approve(self):
        """Admin manages access; it does not make scientific decisions."""
        caps = capabilities_for(ADMIN, self.REVIEWING)
        assert Capability.MANAGE_ACCESS in caps
        assert Capability.APPROVE not in caps
        with pytest.raises(PermissionDenied) as exc:
            require(ADMIN, self.REVIEWING, Capability.APPROVE)
        assert "cannot approve scientific records" in str(exc.value)

    def test_an_administrator_cannot_edit_science(self):
        caps = capabilities_for(ADMIN, self.DRAFT)
        assert Capability.EDIT_DRAFT not in caps
        assert Capability.SUBMIT not in caps

    def test_the_performer_cannot_approve(self):
        with pytest.raises(PermissionDenied) as exc:
            require(PERFORMER, self.REVIEWING, Capability.APPROVE)
        assert "you cannot approve it" in str(exc.value).lower()

    def test_an_independent_researcher_can_approve(self):
        assert Capability.APPROVE in capabilities_for(REVIEWER, self.REVIEWING)

    def test_an_unrecorded_performer_is_assumed_to_be_the_owner(self):
        """The conservative reading, so a blank field is not a way in."""
        ctx = ExperimentContext(owner_id=1,
                                status=ExperimentStatus.UNDER_REVIEW,
                                performed_by=None)
        with pytest.raises(PermissionDenied):
            require(PERFORMER, ctx, Capability.APPROVE)

    def test_an_approved_version_cannot_be_edited(self):
        for actor in (PERFORMER, REVIEWER, ADMIN):
            assert Capability.EDIT_DRAFT not in capabilities_for(
                actor, self.APPROVED)

    def test_editing_an_approved_version_is_refused_by_the_service(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await _approve(session, version.id)

                with pytest.raises(PermissionDenied) as exc:
                    await svc.update_draft(
                        session, actor=PERFORMER, version_id=version.id,
                        fields={"investigator_conclusion": "rewritten"})
                assert "frozen" in str(exc.value)
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_viewer_cannot_create_an_experiment(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                cversion = await _candidate_version(session, study.id)
                with pytest.raises(PermissionDenied):
                    await svc.create_experiment(
                        session, actor=VIEWER,
                        candidate_version_id=cversion.id,
                        subtype=ST.CYTOTOXICITY, purpose=A.SAFETY_ASSESSMENT,
                        title="No", code="EXP-V")
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 6. Workflow, versioning and immutability
# ===========================================================================


class TestWorkflow:

    def test_submission_freezes_the_version(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)
                stored = await session.get(ExperimentVersion, version.id)
                assert stored.frozen_at is not None
                with pytest.raises(PermissionDenied):
                    await svc.update_draft(session, actor=PERFORMER,
                                           version_id=version.id,
                                           fields={"hypothesis": "changed"})
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_an_illegal_transition_is_refused(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                # Draft -> under review, skipping submission.
                with pytest.raises((svc.ValidationError, PermissionDenied)):
                    await svc.start_review(session, actor=REVIEWER,
                                           version_id=version.id)
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_decision_requires_comments(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)
                await svc.start_review(session, actor=REVIEWER,
                                       version_id=version.id)
                with pytest.raises(svc.ValidationError) as exc:
                    await svc.record_decision(
                        session, actor=REVIEWER, version_id=version.id,
                        decision=ReviewDecision.REJECT, comments="  ")
                assert exc.value.code == "comments_required"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_revision_preserves_the_approved_record(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await _approve(session, version.id)

                fresh = await svc.create_revision(
                    session, actor=PERFORMER, version_id=version.id)
                old = await session.get(ExperimentVersion, version.id)

                assert fresh.version_number == 2
                assert fresh.status is ExperimentStatus.DRAFT
                # The new version inherits none of the old decision.
                assert fresh.approved_level is None
                assert fresh.decision_by is None
                # The old one is preserved, not deleted or rewritten.
                assert old.status is ExperimentStatus.SUPERSEDED
                assert old.decision_comments == "Reviewed."
                assert old.superseded_by_version_id == fresh.id
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_rejected_experiment_remains_visible(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)
                await svc.start_review(session, actor=REVIEWER,
                                       version_id=version.id)
                await svc.record_decision(
                    session, actor=REVIEWER, version_id=version.id,
                    decision=ReviewDecision.REJECT,
                    comments="Controls insufficient.")
                stored = await session.get(ExperimentVersion, version.id)
                assert stored.status is ExperimentStatus.REJECTED
                assert stored.decision_comments == "Controls insufficient."
                assert stored.approved_level is None
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_an_ineligible_experiment_cannot_be_approved(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id, attach_raw=False,
                    field_overrides={"raw_data_reference": None})
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)
                await svc.start_review(session, actor=REVIEWER,
                                       version_id=version.id)
                with pytest.raises(svc.ValidationError) as exc:
                    await svc.record_decision(
                        session, actor=REVIEWER, version_id=version.id,
                        decision=ReviewDecision.APPROVE, comments="Looks fine.")
                assert exc.value.code == "not_eligible"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())


# ===========================================================================
# 7. Candidate versioning and audit
# ===========================================================================


class TestCandidateVersioningAndAudit:

    def test_a_snapshot_is_a_copy_not_a_reference(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                design = dict(DESIGN)
                cversion = await _candidate_version(session, study.id, design)
                # Mutating the source dictionary must not touch the snapshot.
                design["size_nm"] = 999
                assert json.loads(cversion.design_snapshot_json)["size_nm"] == 100
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_the_checksum_is_order_independent(self):
        a = svc.canonical_snapshot({"b": 2, "a": 1})
        b = svc.canonical_snapshot({"a": 1, "b": 2})
        assert svc.snapshot_checksum(a) == svc.snapshot_checksum(b)

    def test_versions_increment(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                candidate = await svc.create_candidate(
                    session, actor=PERFORMER, study_id=study.id, code="C",
                    name="C")
                v1 = await svc.create_candidate_version(
                    session, actor=PERFORMER, candidate_id=candidate.id,
                    design_inputs={"size_nm": 100})
                v2 = await svc.create_candidate_version(
                    session, actor=PERFORMER, candidate_id=candidate.id,
                    design_inputs={"size_nm": 120})
                assert (v1.version_number, v2.version_number) == (1, 2)
                assert v1.snapshot_checksum != v2.snapshot_checksum
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_the_audit_trail_records_the_whole_lifecycle(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                experiment, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await _approve(session, version.id)

                events = [e.event for e in await svc.audit_trail(
                    session, experiment_id=experiment.id)]
                for expected in (AuditEvent.CREATED, AuditEvent.EDITED,
                                 AuditEvent.ATTACHMENT_ADDED,
                                 AuditEvent.SUBMITTED,
                                 AuditEvent.REVIEW_STARTED,
                                 AuditEvent.REVIEW_DECISION,
                                 AuditEvent.APPROVED,
                                 AuditEvent.EVIDENCE_DECISION):
                    assert expected in events, expected
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_a_refused_approval_is_audited(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                experiment, version, _ = await _build_qualifying(
                    session, study_id=study.id)
                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)
                await svc.start_review(session, actor=REVIEWER,
                                       version_id=version.id)
                with pytest.raises(PermissionDenied):
                    await svc.record_decision(
                        session, actor=PERFORMER, version_id=version.id,
                        decision=ReviewDecision.APPROVE, comments="Mine.")
                events = [e.event for e in await svc.audit_trail(
                    session, experiment_id=experiment.id)]
                assert AuditEvent.PERMISSION_DENIED in events
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_the_audit_table_holds_no_foreign_key_to_its_subject(self):
        """So the trail outlives what it describes."""
        fks = {fk.column.table.name
               for fk in ValidationAuditLog.__table__.foreign_keys}
        assert "validation_experiments" not in fks
        assert "validation_experiment_versions" not in fks


# ===========================================================================
# 8. Scientific Readiness integration
# ===========================================================================


class TestReadinessIntegration:

    def test_only_approved_versions_promote(self):
        async def scenario():
            engine, session = await _fresh_db()
            try:
                study = await _study(session)
                _, version, _ = await _build_qualifying(
                    session, study_id=study.id)

                # Draft: nothing.
                assert await svc.approved_evidence_for_study(
                    session, study_id=study.id) == {}

                await svc.submit_version(session, actor=PERFORMER,
                                         version_id=version.id)
                # Submitted: still nothing.
                assert await svc.approved_evidence_for_study(
                    session, study_id=study.id) == {}

                await svc.start_review(session, actor=REVIEWER,
                                       version_id=version.id)
                assert await svc.approved_evidence_for_study(
                    session, study_id=study.id) == {}

                await svc.record_decision(
                    session, actor=REVIEWER, version_id=version.id,
                    decision=ReviewDecision.APPROVE, comments="ok")
                evidence = await svc.approved_evidence_for_study(
                    session, study_id=study.id)
                assert evidence[A.SAFETY_ASSESSMENT.value]["level"] == "E3"
            finally:
                await session.close()
                await engine.dispose()
        run_async(scenario())

    def test_e0_to_e2_is_unchanged_when_no_approved_evidence_exists(self):
        """The compatibility guarantee, stated directly."""
        from nanobio_studio.app.science.data_dictionary import fields_for_area
        from nanobio_studio.app.science.records import ScientificRecord
        from nanobio_studio.app.science.statuses import ScientificStatus

        records = [
            ScientificRecord(field_id=spec.id, status=ScientificStatus.MEASURED,
                             value="1",
                             unit=(spec.accepted_units[0]
                                   if spec.accepted_units else None),
                             measurement_method="assay")
            for spec in fields_for_area(A.SAFETY_ASSESSMENT)
        ]
        without = evaluate_study(records).area(A.SAFETY_ASSESSMENT)
        with_empty = evaluate_study(records, {}).area(A.SAFETY_ASSESSMENT)
        assert without.evidence_level is EvidenceLevel.E2
        assert with_empty.evidence_level is EvidenceLevel.E2

    def test_approved_evidence_promotes_only_its_own_purpose(self):
        from nanobio_studio.app.science.data_dictionary import fields_for_area
        from nanobio_studio.app.science.records import ScientificRecord
        from nanobio_studio.app.science.statuses import ScientificStatus

        records: list[ScientificRecord] = []
        seen: set[str] = set()
        for area in ReadinessArea:
            for spec in fields_for_area(area):
                if spec.id in seen:
                    continue
                seen.add(spec.id)
                records.append(ScientificRecord(
                    field_id=spec.id, status=ScientificStatus.MEASURED,
                    value="1",
                    unit=(spec.accepted_units[0] if spec.accepted_units
                          else None),
                    measurement_method="assay"))

        evidence = {A.SAFETY_ASSESSMENT.value: {
            "purpose": A.SAFETY_ASSESSMENT.value, "level": "E3",
            "experiments": [], "contradiction": None}}
        report = evaluate_study(records, evidence)

        assert report.area(A.SAFETY_ASSESSMENT).evidence_level is EvidenceLevel.E3
        for area in ReadinessArea:
            if area is A.SAFETY_ASSESSMENT:
                continue
            assert report.area(area).evidence_level is EvidenceLevel.E2, area

    def test_a_contradiction_holds_the_level(self):
        from nanobio_studio.app.science.data_dictionary import fields_for_area
        from nanobio_studio.app.science.records import ScientificRecord
        from nanobio_studio.app.science.statuses import ScientificStatus

        records = [
            ScientificRecord(field_id=spec.id, status=ScientificStatus.MEASURED,
                             value="1",
                             unit=(spec.accepted_units[0]
                                   if spec.accepted_units else None),
                             measurement_method="assay")
            for spec in fields_for_area(A.SAFETY_ASSESSMENT)
        ]
        evidence = {A.SAFETY_ASSESSMENT.value: {
            "purpose": A.SAFETY_ASSESSMENT.value, "level": None,
            "experiments": [],
            "contradiction": "Approved experiments disagree."}}
        area = evaluate_study(records, evidence).area(A.SAFETY_ASSESSMENT)
        assert area.evidence_level is EvidenceLevel.E2

    def test_the_rationale_names_the_registry_when_promoted(self):
        from nanobio_studio.app.science.data_dictionary import fields_for_area
        from nanobio_studio.app.science.records import ScientificRecord
        from nanobio_studio.app.science.statuses import ScientificStatus

        records = [
            ScientificRecord(field_id=spec.id, status=ScientificStatus.MEASURED,
                             value="1",
                             unit=(spec.accepted_units[0]
                                   if spec.accepted_units else None),
                             measurement_method="assay")
            for spec in fields_for_area(A.SAFETY_ASSESSMENT)
        ]
        evidence = {A.SAFETY_ASSESSMENT.value: {
            "purpose": A.SAFETY_ASSESSMENT.value, "level": "E3",
            "experiments": [], "contradiction": None}}
        area = evaluate_study(records, evidence).area(A.SAFETY_ASSESSMENT)
        assert "Experimental Validation Registry" in area.evidence_level_rationale
        assert "any other purpose" in area.evidence_level_rationale

    def test_e4_to_e6_never_arrive_through_this_path(self):
        from nanobio_studio.app.science.data_dictionary import fields_for_area
        from nanobio_studio.app.science.records import ScientificRecord
        from nanobio_studio.app.science.statuses import ScientificStatus

        records = [
            ScientificRecord(field_id=spec.id, status=ScientificStatus.MEASURED,
                             value="1",
                             unit=(spec.accepted_units[0]
                                   if spec.accepted_units else None),
                             measurement_method="assay")
            for spec in fields_for_area(A.SAFETY_ASSESSMENT)
        ]
        for level in ("E4", "E5", "E6"):
            evidence = {A.SAFETY_ASSESSMENT.value: {
                "purpose": A.SAFETY_ASSESSMENT.value, "level": level,
                "experiments": [], "contradiction": None}}
            area = evaluate_study(records, evidence).area(A.SAFETY_ASSESSMENT)
            assert area.evidence_level is EvidenceLevel.E2, level

    def test_the_registry_grants_e3_only(self):
        assert GRANTABLE_LEVELS == frozenset({EvidenceLevel.E3})
