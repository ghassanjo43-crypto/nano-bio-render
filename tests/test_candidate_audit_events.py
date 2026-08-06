"""The version trail is append-only, transactional, redacted and complete.

Four properties, and the order matters
--------------------------------------
1. **Complete.** Every event the brief names is emitted by the operation that
   causes it — not by a route that might be bypassed, and not by a caller who
   might forget.
2. **Transactional.** The event and the thing it records land in the same
   transaction. A trail entry for an operation that rolled back is a lie, and
   an operation that committed without one is an untraceable change.
3. **Redacted.** Nothing here may carry patient data, document content or a
   measurement value. This trail outlives every record it describes, so a
   clinical value written into a summary survives the deletion of the
   assessment it came from and is exported with the trail to whoever asks.
4. **Append-only.** Nothing in the application updates or deletes a row.

Each event carries the exact candidate id, the exact version id, the actor and
the timestamp. Both identifiers, because the version alone cannot be grouped
into a candidate's history without joining to a table this trail deliberately
has no foreign key into — and it has none precisely so it can outlive its
subject.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.db.validation_models import (  # noqa: E402
    Candidate, CandidateVersion, ResultsState, ValidationAuditLog,
    VersionStatus,
)
from nanobio_studio.app.science.statuses import (  # noqa: E402
    EvidenceLevel, ReadinessArea,
)
from nanobio_studio.app.services import candidate_dependencies as deps  # noqa: E402
from nanobio_studio.app.services import candidate_versioning as cvs  # noqa: E402
from nanobio_studio.app.services.audit_redaction import (  # noqa: E402
    REDACTED_MARKER, redact,
)
from nanobio_studio.app.validation.vocabulary import (  # noqa: E402
    CANDIDATE_VERSION_EVENTS, AuditEvent, EvidenceReuse, SimulationKind,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

DESIGN = {"size_nm": 90.0, "charge_mv": -10.0, "coating": "PEG",
          "dose_mg_kg": 2.0}


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    from nanobio_studio.app.db.organization_models import Organization
    from nanobio_studio.app.db.workspace_models import StoredRun
    from nanobio_studio.app.organizations.vocabulary import OrganizationStatus
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("audit_events")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    async def seed():
        async with factory() as session:
            author = await create_user(
                session, username="aud_author", password="a-long-passphrase-1",
                role=UserRole.RESEARCHER, email="aud_author@aud.test")
            approver = await create_user(
                session, username="aud_approver",
                password="a-long-passphrase-2",
                role=UserRole.RESEARCHER, email="aud_approver@aud.test")
            await session.flush()

            org = Organization(slug="aud-org", name="Audit Org",
                               status=OrganizationStatus.ACTIVE)
            session.add(org)
            await session.flush()

            run = StoredRun(organization_id=org.id, owner_id=author.id,
                            name="audit study")
            session.add(run)
            await session.flush()

            state.update(org_id=org.id, study_id=run.id, author_id=author.id,
                         approver_id=approver.id)
            await session.commit()

    with client:
        run_async(seed())
        yield app, factory, state
    app.dependency_overrides.clear()


def _actor(state, user_id=None, role=UserRole.RESEARCHER):
    from nanobio_studio.app.validation.permissions import RegistryActor

    return RegistryActor(user_id=user_id or state["author_id"], role=role)


async def _fresh_version(session, state, code: str) -> CandidateVersion:
    candidate = Candidate(
        organization_id=state["org_id"], study_id=state["study_id"],
        owner_id=state["author_id"], code=code, name=f"candidate {code}")
    session.add(candidate)
    await session.flush()

    snapshot = cvs.canonical_snapshot(DESIGN)
    version = CandidateVersion(
        organization_id=state["org_id"], candidate_id=candidate.id,
        version_number=1, revision_label="v1",
        design_snapshot_json=snapshot,
        snapshot_checksum=cvs.snapshot_checksum(snapshot),
        status=VersionStatus.DRAFT, results_state=ResultsState.NONE,
        created_by=state["author_id"])
    session.add(version)
    await session.flush()
    return version


def run_with_session(factory, work):
    async def scenario():
        async with factory() as session:
            result = await work(session)
            await session.commit()
            return result
    return run_async(scenario())


async def _events_for(session, version_id: int) -> list[ValidationAuditLog]:
    return list((await session.execute(
        select(ValidationAuditLog)
        .where(ValidationAuditLog.candidate_version_id == version_id)
        .order_by(ValidationAuditLog.id))).scalars().all())


def _kinds(events) -> list[str]:
    return [e.event.value for e in events]


# ===========================================================================
# 1. Every event the brief names exists
# ===========================================================================

class TestTheEventVocabularyIsComplete:

    def test_the_brief_s_events_are_all_defined(self):
        """Named individually, so one cannot quietly disappear."""
        for expected in ("REVISION_CREATED", "VERSION_LOCKED",
                         "RECALCULATION_REQUESTED", "RECALCULATION_COMPLETED",
                         "REASSESSMENT_REQUIRED", "VERSION_WITHDRAWN",
                         "SUPERSESSION_PROPOSED", "SUPERSESSION_ACCEPTED",
                         "SUPERSESSION_REFUSED", "REPORT_GENERATED",
                         "EXPORT_GENERATED", "PACKAGE_GENERATED"):
            assert hasattr(AuditEvent, expected), expected

    def test_rejection_is_distinguishable_from_withdrawal(self):
        """"We replaced this" and "we stopped standing behind this" are
        different claims to a regulator, and so are "the author retired it"
        and "review rejected it"."""
        assert AuditEvent.VERSION_WITHDRAWN is not AuditEvent.REJECTED
        assert AuditEvent.SUPERSESSION_ACCEPTED is not AuditEvent.SUPERSEDED

    def test_the_version_event_set_is_declared_as_data(self):
        """So a history screen can ask for exactly these without a hard-coded
        list that drifts from the enum."""
        assert AuditEvent.VERSION_LOCKED in CANDIDATE_VERSION_EVENTS
        assert AuditEvent.REPORT_GENERATED in CANDIDATE_VERSION_EVENTS
        # An experiment-level event is not a version-level one.
        assert AuditEvent.ATTACHMENT_ADDED not in CANDIDATE_VERSION_EVENTS


# ===========================================================================
# 2. Each operation emits its event, with both identifiers
# ===========================================================================

class TestEachOperationIsRecorded:

    def test_locking_records_when_and_why(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-LOCK")
            await cvs.rely_on_version(session, version=version,
                                      reason_key="simulation",
                                      actor_id=state["author_id"])
            return version, await _events_for(session, version.id)

        version, events = run_with_session(factory, work)

        locked = [e for e in events if e.event is AuditEvent.VERSION_LOCKED]
        assert len(locked) == 1
        event = locked[0]
        assert event.candidate_version_id == version.id
        assert event.candidate_id == version.candidate_id
        assert event.actor_id == state["author_id"]
        assert event.organization_id == version.organization_id
        assert event.created_at is not None
        assert "simulation was run against it" in event.reason

    def test_locking_twice_records_once(self, harness):
        """Reliance is monotonic. A second dependency does not re-freeze it."""
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-LOCK-TWICE")
            await cvs.rely_on_version(session, version=version,
                                      reason_key="simulation",
                                      actor_id=state["author_id"])
            await cvs.rely_on_version(session, version=version,
                                      reason_key="report",
                                      actor_id=state["author_id"])
            return await _events_for(session, version.id)

        events = run_with_session(factory, work)
        assert _kinds(events).count("version_locked") == 1

    def test_creating_a_revision_is_recorded_with_its_reason(self, harness):
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "AUD-REV")
            v2, _ = await cvs.create_revision(
                session, predecessor=v1,
                design_inputs={**DESIGN, "dose_mg_kg": 8.0},
                reason="Dose escalation agreed at the tolerability review",
                actor_id=state["author_id"])
            return v1, v2, await _events_for(session, v2.id)

        v1, v2, events = run_with_session(factory, work)

        created = [e for e in events
                   if e.event is AuditEvent.REVISION_CREATED]
        assert len(created) == 1
        assert created[0].candidate_version_id == v2.id
        assert created[0].candidate_id == v1.candidate_id
        assert "Dose escalation" in created[0].reason
        assert "carrying no approval" in created[0].summary

    def test_a_revision_carrying_stale_results_demands_reassessment(self,
                                                                     harness):
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "AUD-REASSESS")
            await cvs.record_recalculation(session, version=v1,
                                           model_version="score-1.4.0",
                                           actor_id=state["author_id"])
            v2, _ = await cvs.create_revision(
                session, predecessor=v1,
                design_inputs={**DESIGN, "coating": "chitosan"},
                reason="Coating change after the stability finding",
                actor_id=state["author_id"])
            return v2, await _events_for(session, v2.id)

        v2, events = run_with_session(factory, work)

        assert v2.results_state is ResultsState.STALE
        reassessment = [e for e in events
                        if e.event is AuditEvent.REASSESSMENT_REQUIRED]
        assert len(reassessment) == 1
        assert "safety_review" in reassessment[0].summary

    def test_recalculation_is_recorded_as_two_events(self, harness):
        """Requested and completed are separate facts.

        Collapsing them would leave a version that somebody asked to have
        recalculated indistinguishable from one that actually was.
        """
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-RECALC")
            await cvs.request_recalculation(
                session, version=version, actor_id=state["author_id"],
                reason="Inputs changed in the revision")
            await cvs.record_recalculation(
                session, version=version, model_version="pk-2.1.0",
                ruleset_version="rules-3.0.0", actor_id=state["author_id"])
            return await _events_for(session, version.id)

        events = run_with_session(factory, work)
        kinds = _kinds(events)

        assert kinds.index("recalculation_requested") < kinds.index(
            "recalculation_completed")
        completed = next(e for e in events
                         if e.event is AuditEvent.RECALCULATION_COMPLETED)
        assert "pk-2.1.0" in completed.summary
        assert "rules-3.0.0" in completed.summary

    def test_withdrawal_is_recorded_with_its_reason(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-WITHDRAW")
            await cvs.withdraw_version(
                session, version=version,
                reason="Synthesis route is not reproducible at scale",
                actor_id=state["author_id"])
            return await _events_for(session, version.id)

        events = run_with_session(factory, work)
        withdrawn = [e for e in events
                     if e.event is AuditEvent.VERSION_WITHDRAWN]
        assert len(withdrawn) == 1
        assert "not reproducible" in withdrawn[0].reason
        assert "without a successor" in withdrawn[0].summary

    def test_supersession_records_all_three_stages(self, harness):
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "AUD-SUPERSEDE")
            await cvs.lock_version(session, version=v1, reason="a report",
                                   actor_id=state["author_id"])
            v2, _ = await cvs.create_revision(
                session, predecessor=v1, design_inputs=None,
                reason="Correcting the recorded zeta potential",
                actor_id=state["author_id"])
            await cvs.lock_version(session, version=v2, reason="a review",
                                   actor_id=state["author_id"])

            await cvs.propose_supersession(
                session, predecessor=v1, successor=v2,
                reason="The corrected version should be used from now on",
                actor_id=state["author_id"])
            await cvs.refuse_supersession(
                session, predecessor=v1,
                reason="The correction needs a second opinion first",
                actor_id=state["approver_id"])
            await cvs.propose_supersession(
                session, predecessor=v1, successor=v2,
                reason="Second opinion obtained",
                actor_id=state["author_id"])
            await cvs.accept_supersession(
                session, predecessor=v1, successor=v2,
                actor_id=state["approver_id"],
                reason="Agreed at the formulation review")
            return await _events_for(session, v1.id)

        events = run_with_session(factory, work)
        kinds = _kinds(events)

        assert kinds.count("supersession_proposed") == 2
        assert kinds.count("supersession_refused") == 1
        assert kinds.count("supersession_accepted") == 1

        accepted = next(e for e in events
                        if e.event is AuditEvent.SUPERSESSION_ACCEPTED)
        assert accepted.actor_id == state["approver_id"]
        assert "Agreed at the formulation review" in accepted.reason

    @pytest.mark.parametrize("operation,event", [
        ("report", AuditEvent.REPORT_GENERATED),
        ("export", AuditEvent.EXPORT_GENERATED),
        ("package", AuditEvent.PACKAGE_GENERATED),
        ("simulation", AuditEvent.SIMULATION_RECORDED),
        ("evidence", AuditEvent.EVIDENCE_ASSESSED),
    ])
    def test_generating_an_artifact_is_recorded(self, harness, operation,
                                                event):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state,
                                           f"AUD-GEN-{operation}")
            actor = _actor(state)
            if operation == "report":
                await deps.generate_report(
                    session, actor=actor, candidate_version_id=version.id,
                    title="Summary", body={})
            elif operation == "export":
                await deps.generate_export(
                    session, actor=actor, candidate_version_id=version.id)
            elif operation == "package":
                await deps.generate_cro_package(
                    session, actor=actor, candidate_version_id=version.id,
                    recipient_name="Northgate Contract Labs",
                    package_code=f"PKG-AUD-{version.id}")
            elif operation == "simulation":
                await deps.record_simulation(
                    session, actor=actor, candidate_version_id=version.id,
                    kind=SimulationKind.PHARMACOKINETIC,
                    engine_version="pk-2.1.0", inputs={}, result={"auc": 1.0})
            else:
                await deps.record_evidence_assessment(
                    session, actor=actor, candidate_version_id=version.id,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT,
                    level=EvidenceLevel.E3,
                    reuse=EvidenceReuse.NEWLY_VALIDATED,
                    rationale="Performed on this exact version.")
            return version, await _events_for(session, version.id)

        version, events = run_with_session(factory, work)

        matching = [e for e in events if e.event is event]
        assert len(matching) == 1, (
            f"{operation} produced {_kinds(events)}, expected one "
            f"{event.value}")
        assert matching[0].candidate_version_id == version.id
        assert matching[0].candidate_id == version.candidate_id
        assert matching[0].actor_id == state["author_id"]


# ===========================================================================
# 3. Audit creation is transactional with the operation
# ===========================================================================

class TestAuditIsTransactional:

    def test_a_rolled_back_operation_leaves_no_trail_entry(self, harness):
        """A trail entry for something that did not happen is worse than none:
        it is a false record that nothing later can contradict."""
        _app, factory, state = harness

        async def create(session):
            return (await _fresh_version(session, state, "AUD-ROLLBACK")).id

        version_id = run_with_session(factory, create)

        async def failing():
            async with factory() as session:
                try:
                    await deps.generate_report(
                        session, actor=_actor(state),
                        candidate_version_id=version_id, title="Doomed",
                        body={})
                    raise RuntimeError("simulated downstream failure")
                except Exception:
                    await session.rollback()

        run_async(failing())

        async def read():
            async with factory() as session:
                return await _events_for(session, version_id)

        events = run_async(read())
        assert _kinds(events) == [], (
            "the audit rows survived a rolled-back transaction, so the trail "
            "records an operation that never committed")

    def test_a_committed_operation_always_leaves_one(self, harness):
        """Positive control for the rollback test.

        A writer that never worked at all would also produce no rows.
        """
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-COMMIT")
            await deps.generate_report(
                session, actor=_actor(state), candidate_version_id=version.id,
                title="Kept", body={})
            return version.id

        version_id = run_with_session(factory, work)

        async def read():
            async with factory() as session:
                return await _events_for(session, version_id)

        assert "report_generated" in _kinds(run_async(read()))

    def test_the_writer_never_commits_on_its_own(self):
        """Read from the source, because this is the property a future edit is
        most likely to break by adding a convenient `await session.commit()`."""
        import inspect

        source = inspect.getsource(cvs.record_version_event)
        assert "commit()" not in source


# ===========================================================================
# 4. Redaction
# ===========================================================================

class TestRedaction:

    @pytest.mark.parametrize("leaked", [
        "patient m.reynolds@clinic.invalid asked for this",
        "DOB 1974-03-11 recorded on the referral",
        "hospital number 884211903 in the chart",
        "see C:\\clinical\\patients\\reynolds\\report.pdf",
        "see /var/lib/reports/patients/reynolds/report.pdf",
        "token " + "A" * 64,
    ])
    def test_content_is_removed_before_storage(self, leaked):
        cleaned = redact(leaked)
        assert REDACTED_MARKER in cleaned
        for fragment in ("@clinic.invalid", "1974-03-11", "884211903",
                         "reynolds", "A" * 64):
            assert fragment not in cleaned

    def test_ordinary_context_survives(self):
        """A redactor that removed everything would pass every test above
        while making the trail useless."""
        kept = redact("v3 locked because a report was generated from it")
        assert kept == "v3 locked because a report was generated from it"
        assert REDACTED_MARKER not in kept

    def test_an_ordinary_identifier_survives(self):
        """Seven digits is the floor precisely so 'version 128' is not eaten."""
        assert redact("version 128 superseded by 129") == (
            "version 128 superseded by 129")

    def test_pasted_structure_is_collapsed(self):
        assert redact("line one\n\n\tline two   ") == "line one line two"

    def test_empty_input_is_none_not_an_empty_string(self):
        """So a caller that passed nothing and one whose text was entirely
        redacted are distinguishable in the stored row."""
        assert redact(None) is None
        assert redact("   ") is None

    def test_truncation_is_marked(self):
        """A reason that ends mid-sentence with no indication reads as though
        the author simply stopped typing."""
        cleaned = redact("dose escalation " * 60, limit=100)
        assert len(cleaned) <= 100
        assert cleaned.endswith("[truncated]")

    def test_a_long_unbroken_token_is_treated_as_a_blob_not_truncated(self):
        """Fifty characters with no break is a hash, a token or base64 — not
        prose. Truncating it would store the first half of a secret."""
        cleaned = redact("x" * 900)
        assert cleaned == REDACTED_MARKER

    def test_a_stored_reason_goes_through_redaction(self, harness):
        """The boundary, not just the helper."""
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-REDACT")
            await cvs.withdraw_version(
                session, version=version,
                reason=("withdrawn at the request of "
                        "j.okafor@hospital.invalid on 2026-02-14"),
                actor_id=state["author_id"])
            return await _events_for(session, version.id)

        events = run_with_session(factory, work)
        withdrawn = next(e for e in events
                         if e.event is AuditEvent.VERSION_WITHDRAWN)

        assert "@hospital.invalid" not in withdrawn.reason
        assert "2026-02-14" not in withdrawn.reason
        assert REDACTED_MARKER in withdrawn.reason
        # The part that explains the decision is kept.
        assert "withdrawn at the request of" in withdrawn.reason

    def test_no_stored_event_carries_a_measurement_value(self, harness):
        """A measurement in the trail outlives the experiment it came from."""
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "AUD-NOMEASURE")
            await deps.record_simulation(
                session, actor=_actor(state), candidate_version_id=version.id,
                kind=SimulationKind.PHARMACOKINETIC, engine_version="pk-2.1.0",
                inputs={"dose_mg_kg": 2.0},
                result={"auc": 41.2, "c_max": 9.7})
            return await _events_for(session, version.id)

        events = run_with_session(factory, work)
        for event in events:
            blob = f"{event.reason or ''} {event.summary or ''}"
            assert "41.2" not in blob and "9.7" not in blob, (
                f"a result value reached the trail: {blob!r}")


# ===========================================================================
# 5. Append-only
# ===========================================================================

class TestAppendOnly:

    def test_no_application_module_updates_or_deletes_a_trail_row(self):
        """Parsed, not grepped.

        A comment saying the table is append-only is not a control. This walks
        every module under `app/` looking for an UPDATE or DELETE aimed at the
        audit table, in raw SQL or through the ORM.
        """
        app_dir = BACKEND_ROOT / "nanobio_studio" / "app"
        offenders: list[str] = []

        for path in sorted(app_dir.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            lowered = source.lower()
            for pattern in ("delete from validation_audit_log",
                            "update validation_audit_log",
                            "delete(validationauditlog",
                            "update(validationauditlog"):
                if pattern in lowered.replace(" ", "").replace(
                        "delete(validationauditlog",
                        "delete(validationauditlog"):
                    pass
            # Checked on the AST for the ORM forms, and on the text for SQL.
            if ("DELETE FROM validation_audit_log" in source
                    or "UPDATE validation_audit_log" in source):
                offenders.append(f"{path.name}: raw SQL against the trail")

            try:
                tree = ast.parse(source)
            except SyntaxError:  # pragma: no cover - would fail elsewhere
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                target = node.func
                name = getattr(target, "id", None) or getattr(
                    target, "attr", None)
                if name not in {"delete", "update"}:
                    continue
                for argument in node.args:
                    if (isinstance(argument, ast.Name)
                            and argument.id == "ValidationAuditLog"):
                        offenders.append(
                            f"{path.name}: {name}(ValidationAuditLog)")

        assert offenders == [], offenders

    def test_the_trail_has_no_foreign_key_to_its_subject(self):
        """Deliberate. The trail must outlive what it describes, which is the
        entire point of auditing a supersession or a deletion."""
        table = ValidationAuditLog.__table__
        for column in ("candidate_id", "candidate_version_id",
                       "experiment_id", "experiment_version_id"):
            assert not table.c[column].foreign_keys, (
                f"{column} is a foreign key, so deleting its subject would "
                f"take the audit history with it")

    def test_the_actor_link_survives_the_actor(self):
        """`ondelete=SET NULL`, not CASCADE. Removing an account must not
        erase the record that something was done."""
        actor = ValidationAuditLog.__table__.c["actor_id"]
        assert actor.foreign_keys
        assert all(fk.ondelete == "SET NULL" for fk in actor.foreign_keys)
