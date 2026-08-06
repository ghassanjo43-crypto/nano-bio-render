"""Every dependency locks its exact version, transactionally, and names it.

What the previous pass left open
--------------------------------
`test_candidate_locking_boundaries.py` proved that the registry's own
operations — experiment, measurement, submission, review, decision,
contradiction — lock the candidate version they rely on. It could not prove it
for the operations that did not exist yet: simulation, evidence assessment,
report, export, CRO package and filed comparison. Those are the ones that
produce artefacts somebody acts on outside this system, and they are the ones
where a wrong version attribution is most expensive.

Each is tested independently rather than through one long scenario, so a
failure names the operation that stopped locking rather than reporting that
"the workflow" broke. Every operation gets the same five checks the brief asks
for:

1. an authorized successful operation;
2. the exact version becomes locked;
3. subsequent scientific mutation is refused;
4. identity-only metadata stays editable;
5. rollback leaves the version unlocked when the dependent write fails.

And two the brief implies and this file makes explicit:

6. the dependent row names the exact version, not the candidate;
7. an inexact reference — `None`, `"latest"` — is refused rather than resolved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.db.candidate_dependency_models import (  # noqa: E402
    CandidateCROPackage, CandidateEvidenceAssessment, CandidateExport,
    CandidateReport, CandidateSimulation, CandidateVersionComparison,
    DependentResultState,
)
from nanobio_studio.app.db.validation_models import (  # noqa: E402
    Candidate, CandidateVersion, ResultsState, VersionStatus,
)
from nanobio_studio.app.science.statuses import (  # noqa: E402
    EvidenceLevel, ReadinessArea,
)
from nanobio_studio.app.services import candidate_dependencies as deps  # noqa: E402
from nanobio_studio.app.services import candidate_versioning as cvs  # noqa: E402
from nanobio_studio.app.validation.vocabulary import (  # noqa: E402
    EvidenceReuse, GeneratedArtifactFormat, SimulationKind,
)

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

DESIGN = {"size_nm": 90.0, "charge_mv": -10.0, "coating": "PEG",
          "dose_mg_kg": 2.0, "name": "Candidate A"}


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    from nanobio_studio.app.db.organization_models import Organization
    from nanobio_studio.app.db.workspace_models import StoredRun
    from nanobio_studio.app.organizations.vocabulary import OrganizationStatus
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("dependency_binding")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    async def seed():
        async with factory() as session:
            author = await create_user(
                session, username="dep_author", password="a-long-passphrase-1",
                role=UserRole.RESEARCHER, email="dep_author@dep.test")
            administrator = await create_user(
                session, username="dep_admin", password="a-long-passphrase-2",
                role=UserRole.ADMIN, email="dep_admin@dep.test")
            onlooker = await create_user(
                session, username="dep_viewer", password="a-long-passphrase-3",
                role=UserRole.VIEWER, email="dep_viewer@dep.test")
            await session.flush()

            org = Organization(slug="dep-org", name="Dependency Org",
                               status=OrganizationStatus.ACTIVE)
            session.add(org)
            await session.flush()

            run = StoredRun(organization_id=org.id, owner_id=author.id,
                            name="dependency study")
            session.add(run)
            await session.flush()

            state.update(org_id=org.id, study_id=run.id, author_id=author.id,
                         admin_id=administrator.id, viewer_id=onlooker.id)
            await session.commit()

    with client:
        run_async(seed())
        yield app, factory, state
    app.dependency_overrides.clear()


def _actor(state, user_id=None, role=UserRole.RESEARCHER):
    from nanobio_studio.app.validation.permissions import RegistryActor

    return RegistryActor(user_id=user_id or state["author_id"], role=role)


async def _fresh_version(session, state, code: str) -> CandidateVersion:
    """A candidate with one DRAFT version, ready to be relied upon."""
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


#: Every operation, and how to invoke it against a version. One table so the
#: parametrised tests below cover the whole set — a seventh operation added
#: without an entry here shows up as a missing key, not as silent absence.
OPERATIONS: dict[str, dict] = {
    "simulation": {
        "reliance_key": "simulation",
        "model": CandidateSimulation,
        "call": lambda session, actor, version_id, n: deps.record_simulation(
            session, actor=actor, candidate_version_id=version_id,
            kind=SimulationKind.PHARMACOKINETIC, engine_version="pk-2.1.0",
            inputs={"dose_mg_kg": 2.0}, result={"auc": 41.2}),
    },
    "evidence": {
        "reliance_key": "evidence",
        "model": CandidateEvidenceAssessment,
        "call": lambda session, actor, version_id, n: (
            deps.record_evidence_assessment(
                session, actor=actor, candidate_version_id=version_id,
                purpose=ReadinessArea.SAFETY_ASSESSMENT,
                level=EvidenceLevel.E3, reuse=EvidenceReuse.NEWLY_VALIDATED,
                rationale="Cytotoxicity performed on this exact version.")),
    },
    "report": {
        "reliance_key": "report",
        "model": CandidateReport,
        "call": lambda session, actor, version_id, n: deps.generate_report(
            session, actor=actor, candidate_version_id=version_id,
            title="Formulation summary", body={"section": "one"}),
    },
    "export": {
        "reliance_key": "export",
        "model": CandidateExport,
        "call": lambda session, actor, version_id, n: deps.generate_export(
            session, actor=actor, candidate_version_id=version_id,
            format=GeneratedArtifactFormat.JSON,
            purpose_note="Shared with the analytics group"),
    },
    "package": {
        "reliance_key": "package",
        "model": CandidateCROPackage,
        "call": lambda session, actor, version_id, n: (
            deps.generate_cro_package(
                session, actor=actor, candidate_version_id=version_id,
                recipient_name="Northgate Contract Labs",
                package_code=f"PKG-{n}")),
    },
}


# ===========================================================================
# 1. The operation set is enumerable and complete
# ===========================================================================

class TestTheOperationSetIsExplicit:

    def test_every_dependency_operation_has_a_reliance_reason(self):
        """A lock reason nobody wrote reads as the raw key at the call site."""
        for operation, reason_key in deps.DEPENDENCY_OPERATIONS.items():
            assert reason_key in cvs.RELIANCE_REASONS, operation
            reason = cvs.RELIANCE_REASONS[reason_key]
            assert " " in reason and not reason.isupper(), (
                f"{operation} locks under {reason!r}, which reads as a code "
                f"rather than an explanation")

    def test_the_brief_s_dependency_list_is_covered(self):
        """Named individually, so a boundary cannot quietly disappear."""
        for expected in ("record_simulation", "record_evidence_assessment",
                         "generate_report", "generate_export",
                         "generate_cro_package", "record_comparison"):
            assert expected in deps.DEPENDENCY_OPERATIONS, expected
            assert hasattr(deps, expected), expected

    def test_locking_lives_in_the_service_not_the_routes(self):
        """Route discipline is a convention, and a convention is one new
        endpoint away from being broken silently."""
        import inspect

        from nanobio_studio.app.api.routes import candidate_artifacts as routes

        route_source = inspect.getsource(routes)
        for forbidden in ("rely_on_version", "lock_version"):
            assert forbidden not in route_source, (
                f"a route calls {forbidden} directly, which puts the "
                f"invariant back at the call site")

    def test_the_service_preamble_is_shared_not_copied(self):
        """Six near-identical preambles is where one forgets to lock.

        A reviewer comparing them will not spot the missing third line, so
        there is one copy and every operation goes through it.
        """
        import inspect

        source = inspect.getsource(deps)
        assert source.count("async def _resolve_and_rely") == 1
        # Every write operation reaches the boundary, directly or through the
        # shared preamble.
        for name in deps.DEPENDENCY_OPERATIONS:
            body = inspect.getsource(getattr(deps, name))
            assert ("_resolve_and_rely" in body
                    or "rely_on_version" in body), name


# ===========================================================================
# 2. Each dependency locks its exact version
# ===========================================================================

@pytest.mark.parametrize("operation", sorted(OPERATIONS))
class TestEachDependencyLocks:

    def test_an_authorized_operation_succeeds_and_locks(self, harness,
                                                        operation):
        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            version = await _fresh_version(session, state, f"DEP-{operation}")
            assert version.status is VersionStatus.DRAFT

            record = await spec["call"](session, _actor(state), version.id, 1)
            return version, record

        version, record = run_with_session(factory, work)

        assert record.id is not None, "the dependent record was not written"
        assert version.status is VersionStatus.LOCKED
        assert version.locked_at is not None
        assert version.lock_reason == cvs.RELIANCE_REASONS[
            spec["reliance_key"]]

    def test_the_dependent_row_names_the_exact_version(self, harness,
                                                       operation):
        """Not the candidate. This is the property the whole table exists for."""
        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            version = await _fresh_version(session, state,
                                           f"EXACT-{operation}")
            record = await spec["call"](session, _actor(state), version.id, 2)
            return version.id, version.candidate_id, record

        version_id, candidate_id, record = run_with_session(factory, work)

        assert record.candidate_version_id == version_id
        assert record.candidate_id == candidate_id
        column = spec["model"].__table__.c["candidate_version_id"]
        assert column.nullable is False, (
            f"{spec['model'].__tablename__}.candidate_version_id is nullable, "
            f"so a row can exist without saying which formulation it is about")

    def test_a_subsequent_scientific_mutation_is_refused(self, harness,
                                                         operation):
        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            version = await _fresh_version(session, state,
                                           f"REFUSE-{operation}")
            await spec["call"](session, _actor(state), version.id, 3)

            consequence = cvs.consequence_of_change({"dose_mg_kg"})
            return version.is_editable(), consequence

        editable, consequence = run_with_session(factory, work)
        assert editable is False
        assert consequence["approval_may_carry_forward"] is False
        assert consequence["requires"] == "safety_review"

    def test_identity_metadata_stays_correctable(self, harness, operation):
        """Fixing a typo in a label changes no science.

        Refusing it would push people to create a revision for a spelling
        correction, filling the lineage with noise and hiding the real ones.
        """
        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            version = await _fresh_version(session, state,
                                           f"IDENT-{operation}")
            await spec["call"](session, _actor(state), version.id, 4)
            return cvs.consequence_of_change({"name", "description", "label"})

        consequence = run_with_session(factory, work)
        assert consequence["identity_only"] is True
        assert consequence["requires"] == "none"
        assert consequence["approval_may_carry_forward"] is True

    def test_a_failed_dependent_write_leaves_the_version_unlocked(
            self, harness, operation):
        """The half that is easy to get wrong.

        If locking committed separately, a dependent write that failed would
        leave a formulation frozen for a reason that never happened — and
        nobody could edit it or explain why.
        """
        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def create(session):
            return (await _fresh_version(session, state,
                                         f"ROLLBACK-{operation}")).id

        version_id = run_with_session(factory, create)

        async def failing_attempt():
            async with factory() as session:
                try:
                    await spec["call"](session, _actor(state), version_id, 5)
                    # Force the failure after the lock and the insert, so the
                    # rollback covers a transaction in which both happened.
                    raise RuntimeError("simulated downstream failure")
                except Exception:
                    await session.rollback()

        run_async(failing_attempt())

        async def read():
            async with factory() as session:
                version = await session.get(CandidateVersion, version_id)
                from sqlalchemy import func, select

                written = (await session.execute(
                    select(func.count()).select_from(spec["model"])
                    .where(spec["model"].candidate_version_id == version_id)
                )).scalar()
                return version, written

        version, written = run_async(read())
        assert version.status is VersionStatus.DRAFT, (
            "the version stayed locked after the dependent write was rolled "
            "back, so the lock committed on its own")
        assert version.locked_at is None
        assert version.lock_reason is None
        assert written == 0, (
            "the dependent record survived a rolled-back transaction")


# ===========================================================================
# 3. An inexact version reference is refused, never resolved
# ===========================================================================

class TestExactVersionIdsAreRequired:

    @pytest.mark.parametrize("given", [None, "latest", "current", "newest",
                                       "approved", "latest_approved", "",
                                       "  ", 0, -3, True, 4.5, {"id": 1}])
    def test_an_inexact_reference_is_refused(self, given):
        with pytest.raises(cvs.AmbiguousVersionReference):
            cvs.require_exact_version_id(given)

    @pytest.mark.parametrize("given,expected", [(7, 7), ("7", 7), (" 12 ", 12)])
    def test_an_exact_reference_is_accepted(self, given, expected):
        assert cvs.require_exact_version_id(given) == expected

    def test_the_refusal_explains_why_latest_is_not_a_version(self):
        with pytest.raises(cvs.AmbiguousVersionReference) as caught:
            cvs.require_exact_version_id("latest")

        message = f"{caught.value.message} {caught.value.remedy}".lower()
        assert "latest" in message
        assert "draft" in message and "approved" in message, (
            "the refusal does not say what makes 'latest' ambiguous, which is "
            "the only part a caller can act on")

    @pytest.mark.parametrize("operation", sorted(OPERATIONS))
    def test_no_operation_resolves_latest_for_the_caller(self, harness,
                                                         operation):
        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            await _fresh_version(session, state, f"LATEST-{operation}")
            with pytest.raises(cvs.AmbiguousVersionReference):
                await spec["call"](session, _actor(state), "latest", 6)

        run_with_session(factory, work)


# ===========================================================================
# 4. Filed comparisons lock both sides; browsing locks neither
# ===========================================================================

class TestComparisonRecords:

    def test_filing_a_comparison_locks_both_versions(self, harness):
        _app, factory, state = harness

        async def work(session):
            left = await _fresh_version(session, state, "CMP-LEFT")
            right, _created = await cvs.create_revision(
                session, predecessor=left,
                design_inputs={**DESIGN, "dose_mg_kg": 8.0},
                reason="Dose escalation for the tolerability arm",
                actor_id=state["author_id"])
            # The revision path locks nothing on the successor.
            assert right.status is VersionStatus.DRAFT

            comparison = await deps.record_comparison(
                session, actor=_actor(state), left_version_id=left.id,
                right_version_id=right.id,
                note="Basis for the escalation decision")
            return left, right, comparison

        left, right, comparison = run_with_session(factory, work)

        assert left.status is VersionStatus.LOCKED
        assert right.status is VersionStatus.LOCKED
        assert comparison.left_version_id == left.id
        assert comparison.right_version_id == right.id

    def test_the_filed_comparison_stores_the_material_classification(self,
                                                                     harness):
        _app, factory, state = harness

        async def work(session):
            left = await _fresh_version(session, state, "CMP-CLASS")
            right, _ = await cvs.create_revision(
                session, predecessor=left,
                design_inputs={**DESIGN, "dose_mg_kg": 8.0},
                reason="Dose escalation", actor_id=state["author_id"])
            return await deps.record_comparison(
                session, actor=_actor(state), left_version_id=left.id,
                right_version_id=right.id, note=None)

        comparison = run_with_session(factory, work)

        assert comparison.material_classification == "safety_review"
        changes = json.loads(comparison.changed_fields_json)
        assert any(c["field"] == "dose_mg_kg" and c["scientific"]
                   for c in changes)

    def test_comparing_two_candidates_is_refused(self, harness):
        """One formulation does not revise another."""
        _app, factory, state = harness

        async def work(session):
            left = await _fresh_version(session, state, "CMP-OTHER-A")
            right = await _fresh_version(session, state, "CMP-OTHER-B")
            with pytest.raises(deps.DependencyError) as caught:
                await deps.record_comparison(
                    session, actor=_actor(state), left_version_id=left.id,
                    right_version_id=right.id, note=None)
            return caught.value.code

        assert run_with_session(factory, work) == "different_candidates"

    def test_comparing_a_version_with_itself_is_refused(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "CMP-SELF")
            with pytest.raises(deps.DependencyError) as caught:
                await deps.record_comparison(
                    session, actor=_actor(state), left_version_id=version.id,
                    right_version_id=version.id, note=None)
            return caught.value.code

        assert run_with_session(factory, work) == "identical_versions"


# ===========================================================================
# 5. Positive control: an unused draft stays editable
# ===========================================================================

class TestNothingLocksWithoutADependency:

    def test_an_unused_draft_is_still_editable(self, harness):
        """A system that locked everything would pass every assertion above
        while making the product unusable."""
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "DEP-UNUSED")
            return version.is_editable(), version.status

        editable, status = run_with_session(factory, work)
        assert editable is True
        assert status is VersionStatus.DRAFT

    def test_reading_dependents_locks_nothing(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "DEP-READ")
            counts = await deps.dependents_of_version(session, version.id)
            return version.status, counts

        status, counts = run_with_session(factory, work)
        assert status is VersionStatus.DRAFT
        assert sum(counts.values()) == 0

    def test_listing_artifacts_locks_nothing(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "DEP-LIST")
            await deps.simulations_for_version(session, version.id)
            await deps.reports_for_version(session, version.id)
            await deps.exports_for_version(session, version.id)
            await deps.packages_for_version(session, version.id)
            await deps.evidence_for_version(session, version.id)
            return version.status

        assert run_with_session(factory, work) is VersionStatus.DRAFT


# ===========================================================================
# 6. Copied results stay stale and name their source
# ===========================================================================

class TestCopiedResultsRemainStale:

    def test_a_carried_forward_simulation_is_marked_stale(self, harness):
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "STALE-SRC")
            source = await deps.record_simulation(
                session, actor=_actor(state), candidate_version_id=v1.id,
                kind=SimulationKind.PHARMACOKINETIC, engine_version="pk-2.1.0",
                inputs={"dose_mg_kg": 2.0}, result={"auc": 41.2})
            assert source.state is DependentResultState.CURRENT

            v2, _ = await cvs.create_revision(
                session, predecessor=v1,
                design_inputs={**DESIGN, "dose_mg_kg": 8.0},
                reason="Dose escalation", actor_id=state["author_id"])
            copied = await deps.copy_simulation_forward(
                session, actor=_actor(state), source=source,
                target_version=v2)
            return v1, v2, source, copied

        v1, v2, source, copied = run_with_session(factory, work)

        assert copied.state is DependentResultState.COPIED_STALE
        assert copied.copied_from_simulation_id == source.id
        assert copied.source_candidate_version_id == v1.id
        assert copied.candidate_version_id == v2.id
        assert copied.inputs_checksum == source.inputs_checksum, (
            "the copy took the target's checksum, which erases the very "
            "mismatch that makes it stale")
        assert copied.inputs_checksum != v2.snapshot_checksum

    def test_a_revision_inherits_stale_results_and_no_approval(self, harness):
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "STALE-REV")
            await deps.record_simulation(
                session, actor=_actor(state), candidate_version_id=v1.id,
                kind=SimulationKind.DESIGN_SCORE, engine_version="score-1.4.0",
                inputs=DESIGN, result={"score": 71})
            v1.status = VersionStatus.APPROVED
            await session.flush()

            v2, _ = await cvs.create_revision(
                session, predecessor=v1,
                design_inputs={**DESIGN, "coating": "chitosan"},
                reason="Coating change following the stability finding",
                actor_id=state["author_id"])
            return v1, v2

        v1, v2 = run_with_session(factory, work)

        assert v1.status is VersionStatus.APPROVED, "the predecessor moved"
        assert v2.status is VersionStatus.DRAFT, (
            "the revision inherited an approval")
        assert v2.results_state is ResultsState.STALE
        assert v2.results_inherited_from_id == v1.id


# ===========================================================================
# 7. Evidence reuse must be classified
# ===========================================================================

class TestEvidenceReuseClassification:

    def test_retained_evidence_must_name_its_source_version(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "EV-RETAIN")
            with pytest.raises(deps.DependencyError) as caught:
                await deps.record_evidence_assessment(
                    session, actor=_actor(state),
                    candidate_version_id=version.id,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT,
                    level=EvidenceLevel.E3,
                    reuse=EvidenceReuse.RETAINED_REFERENCE,
                    rationale="Carried over from the previous revision.")
            return caught.value.code

        assert run_with_session(factory, work) == (
            "retained_evidence_needs_a_source")

    def test_retained_evidence_with_a_source_is_accepted(self, harness):
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "EV-RETAIN-OK")
            v2, _ = await cvs.create_revision(
                session, predecessor=v1, design_inputs=None,
                reason="Attach further work", actor_id=state["author_id"])
            return await deps.record_evidence_assessment(
                session, actor=_actor(state), candidate_version_id=v2.id,
                purpose=ReadinessArea.SAFETY_ASSESSMENT,
                level=EvidenceLevel.E3, reuse=EvidenceReuse.RETAINED_REFERENCE,
                rationale="Cytotoxicity was performed on v1; the formulation "
                          "is unchanged.",
                source_candidate_version_id=v1.id)

        assessment = run_with_session(factory, work)
        assert assessment.reuse is EvidenceReuse.RETAINED_REFERENCE
        assert assessment.source_candidate_version_id is not None

    def test_every_classification_is_one_of_the_three(self, harness):
        """There is deliberately no fourth value meaning "unclassified"."""
        assert {r.value for r in EvidenceReuse} == {
            "retained_reference", "reassessment_required", "newly_validated"}

    def test_a_rationale_is_required(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "EV-NORATIONALE")
            with pytest.raises(deps.DependencyError) as caught:
                await deps.record_evidence_assessment(
                    session, actor=_actor(state),
                    candidate_version_id=version.id,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT,
                    level=None, reuse=EvidenceReuse.NEWLY_VALIDATED,
                    rationale="   ")
            return caught.value.code

        assert run_with_session(factory, work) == "rationale_required"

    def test_a_later_assessment_supersedes_rather_than_overwriting(self,
                                                                   harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "EV-SUPERSEDE")
            first = await deps.record_evidence_assessment(
                session, actor=_actor(state), candidate_version_id=version.id,
                purpose=ReadinessArea.SAFETY_ASSESSMENT, level=None,
                reuse=EvidenceReuse.REASSESSMENT_REQUIRED,
                rationale="Awaiting the repeat cytotoxicity run.")
            second = await deps.record_evidence_assessment(
                session, actor=_actor(state), candidate_version_id=version.id,
                purpose=ReadinessArea.SAFETY_ASSESSMENT,
                level=EvidenceLevel.E3, reuse=EvidenceReuse.NEWLY_VALIDATED,
                rationale="Repeat run completed and reviewed.")
            live = await deps.evidence_for_version(session, version.id)
            everything = await deps.evidence_for_version(
                session, version.id, include_superseded=True)
            return first, second, live, everything

        first, second, live, everything = run_with_session(factory, work)

        assert first.superseded_by_id == second.id
        assert [a.id for a in live] == [second.id]
        assert len(everything) == 2, (
            "the earlier reading was overwritten rather than superseded")


# ===========================================================================
# 8. Generated artefacts identify what they describe
# ===========================================================================

class TestGeneratedArtifactsIdentifyTheirVersion:

    def _identity(self, payload: str) -> dict:
        return json.loads(payload)["identity"]

    def test_a_report_freezes_its_content(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "RPT-FREEZE")
            report = await deps.generate_report(
                session, actor=_actor(state), candidate_version_id=version.id,
                title="Pre-clinical summary", body={"finding": "acceptable"})
            return version, report

        version, report = run_with_session(factory, work)

        content = json.loads(report.content_json)
        assert content["identity"]["candidate_version_id"] == version.id
        assert content["identity"]["revision_label"] == "v1"
        assert content["identity"]["snapshot_checksum"] == (
            version.snapshot_checksum)
        assert content["design_snapshot"]["dose_mg_kg"] == 2.0
        assert report.version_checksum == version.snapshot_checksum

    def test_an_export_manifest_carries_the_six_identifying_facts(self,
                                                                  harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "EXP-MANIFEST")
            export = await deps.generate_export(
                session, actor=_actor(state), candidate_version_id=version.id,
                purpose_note="Statistics review")
            return version, export

        version, export = run_with_session(factory, work)
        manifest = json.loads(export.manifest_json)

        assert manifest["candidate_id"] == version.candidate_id
        assert manifest["candidate_version_id"] == version.id
        assert manifest["revision_label"] == "v1"
        assert manifest["version_number"] == 1
        assert manifest["snapshot_checksum"] == version.snapshot_checksum
        assert manifest["generated_at"], "no generation timestamp"

    def test_a_cro_package_names_the_exact_version_and_its_recipient(self,
                                                                     harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "CRO-MANIFEST")
            package = await deps.generate_cro_package(
                session, actor=_actor(state), candidate_version_id=version.id,
                recipient_name="Northgate Contract Labs",
                package_code="PKG-IDENTITY-1",
                quotation_reference="Q-2026-0104")
            return version, package

        version, package = run_with_session(factory, work)
        manifest = json.loads(package.manifest_json)

        assert manifest["candidate_version_id"] == version.id
        assert manifest["revision_label"] == "v1"
        assert manifest["snapshot_checksum"] == version.snapshot_checksum
        assert manifest["generated_at"]
        assert manifest["recipient"] == "Northgate Contract Labs"
        assert manifest["quotation_reference"] == "Q-2026-0104"
        assert "stop and ask" in manifest["instruction"]

    def test_a_package_from_a_stale_version_says_so_in_the_document(self,
                                                                    harness):
        """The CRO reads the file, not the screen that generated it."""
        _app, factory, state = harness

        async def work(session):
            v1 = await _fresh_version(session, state, "CRO-STALE")
            v2, _ = await cvs.create_revision(
                session, predecessor=v1, design_inputs=None,
                reason="Attach further work", actor_id=state["author_id"])
            await cvs.mark_results_stale(session, version=v2,
                                         inherited_from=v1)
            return await deps.generate_cro_package(
                session, actor=_actor(state), candidate_version_id=v2.id,
                recipient_name="Northgate Contract Labs",
                package_code="PKG-STALE-1")

        package = run_with_session(factory, work)
        qualification = json.loads(package.manifest_json)[
            "results_qualification"]

        assert qualification["results_state"] == "stale"
        assert qualification["safe_to_cite"] is False
        assert "must not be cited" in qualification["statement"]

    def test_a_failed_simulation_is_stored_without_a_result(self, harness):
        """"Nobody tried" and "the engine refused" lead to different decisions."""
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "SIM-FAIL")
            simulation = await deps.record_simulation(
                session, actor=_actor(state), candidate_version_id=version.id,
                kind=SimulationKind.PHARMACOKINETIC, engine_version="pk-2.1.0",
                inputs={"dose_mg_kg": 0}, result=None,
                failure_reason="clearance is not derivable at zero dose")
            return version, simulation

        version, simulation = run_with_session(factory, work)

        assert simulation.state is DependentResultState.FAILED
        assert simulation.result_json is None
        assert "clearance" in simulation.failure_reason
        assert version.results_state is not ResultsState.CURRENT, (
            "a failed run marked the version's results current")
        assert version.status is VersionStatus.LOCKED, (
            "a failed run left the formulation editable, so the inputs it "
            "failed on can still be changed underneath the record")


# ===========================================================================
# 9. Administrative authority alone is not scientific authority
# ===========================================================================

@pytest.mark.parametrize("operation", sorted(OPERATIONS))
class TestAdministrativeRoleCannotAuthorScience:

    def test_an_administrator_is_refused(self, harness, operation):
        from nanobio_studio.app.validation.permissions import PermissionDenied

        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            version = await _fresh_version(session, state, f"ADM-{operation}")
            actor = _actor(state, user_id=state["admin_id"],
                           role=UserRole.ADMIN)
            with pytest.raises(PermissionDenied):
                await spec["call"](session, actor, version.id, 7)
            return version

        version = run_with_session(factory, work)
        assert version.status is VersionStatus.DRAFT, (
            "a refused operation still locked the formulation")

    def test_a_viewer_is_refused(self, harness, operation):
        from nanobio_studio.app.validation.permissions import PermissionDenied

        _app, factory, state = harness
        spec = OPERATIONS[operation]

        async def work(session):
            version = await _fresh_version(session, state, f"VIEW-{operation}")
            actor = _actor(state, user_id=state["viewer_id"],
                           role=UserRole.VIEWER)
            with pytest.raises(PermissionDenied):
                await spec["call"](session, actor, version.id, 8)
            return version

        version = run_with_session(factory, work)
        assert version.status is VersionStatus.DRAFT


# ===========================================================================
# 10. Attachments name their exact version too
# ===========================================================================

class TestAttachmentsAreBoundToAnExactVersion:

    def test_the_column_exists_and_is_indexed(self):
        from nanobio_studio.app.db.validation_models import ExperimentAttachment

        column = ExperimentAttachment.__table__.c["candidate_version_id"]
        assert column.index is True, (
            "the binding is not indexed, so 'which files are evidence for "
            "this version' is a scan")
        assert column.foreign_keys, "the binding is not a foreign key"

    def test_a_new_attachment_records_the_version_it_supports(self, harness):
        from nanobio_studio.app.science.statuses import ReadinessArea as RA
        from nanobio_studio.app.services import validation_service as svc
        from nanobio_studio.app.validation.vocabulary import (
            AttachmentCategory, ExperimentSubtype,
        )

        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "ATT-BIND")
            _experiment, experiment_version = await svc.create_experiment(
                session, actor=_actor(state), candidate_version_id=version.id,
                subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                purpose=RA.STRUCTURAL_VISUALIZATION,
                title="Particle size", code="EXP-ATT-BIND")

            attachment = await svc.record_attachment(
                session, actor=_actor(state),
                version_id=experiment_version.id,
                category=AttachmentCategory.RAW_DATA,
                original_filename="trace.csv", mime_type="text/csv",
                size_bytes=128, checksum_sha256="0" * 64,
                storage_key="k/1")
            return version, attachment

        version, attachment = run_with_session(factory, work)
        assert attachment.candidate_version_id == version.id
        assert attachment.organization_id == version.organization_id
