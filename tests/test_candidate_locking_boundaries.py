"""Locking happens at every dependency-creation boundary, transactionally.

The gap this closes
-------------------
The previous pass built the immutability machinery — `lock_version`, the status
model, the revision path — and wired none of it into the operations that
actually create scientific reliance. So a version could still be edited in
place after an experiment had been designed against it, which is the exact
failure the whole scheme exists to prevent.

Two properties, and the second is the one that is easy to get wrong:

1. **Every dependency locks.** Creating an experiment, recording measurements,
   submitting, reviewing, deciding and resolving a contradiction all lock the
   candidate version they rely on.

2. **The lock and the dependent record share a transaction.** There must be no
   interleaving in which the dependency exists and the version is still
   editable, and none in which the version is locked but the dependent write
   was rolled back. That second half is what the rollback tests below are for.

Each boundary is tested independently rather than through one long scenario, so
a failure names the operation that stopped locking rather than reporting that
"the workflow" broke.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.db.validation_models import (  # noqa: E402
    Candidate, CandidateVersion, ResultsState, VersionStatus,
)
from nanobio_studio.app.services import candidate_versioning as cvs  # noqa: E402
from nanobio_studio.app.services import validation_service as svc  # noqa: E402

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

DESIGN = {"size_nm": 90.0, "charge_mv": -10.0, "coating": "PEG",
          "dose_mg_kg": 2.0}


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    from nanobio_studio.app.db.organization_models import Organization
    from nanobio_studio.app.db.workspace_models import StoredRun
    from nanobio_studio.app.organizations.vocabulary import OrganizationStatus
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("locking_boundaries")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    async def seed():
        async with factory() as session:
            author = await create_user(
                session, username="lock_author", password="a-long-passphrase-1",
                role=UserRole.RESEARCHER, email="lock_author@lock.test")
            reviewer = await create_user(
                session, username="lock_reviewer",
                password="a-long-passphrase-2",
                role=UserRole.RESEARCHER, email="lock_reviewer@lock.test")
            await session.flush()

            org = Organization(slug="lock-org", name="Locking Org",
                               status=OrganizationStatus.ACTIVE)
            session.add(org)
            await session.flush()

            run = StoredRun(organization_id=org.id, owner_id=author.id,
                            name="locking study")
            session.add(run)
            await session.flush()

            state.update(org_id=org.id, study_id=run.id, author_id=author.id,
                         reviewer_id=reviewer.id)
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


# ===========================================================================
# 1. The boundary set is enumerable
# ===========================================================================

class TestTheBoundarySetIsExplicit:

    def test_every_reliance_reason_is_a_sentence_not_a_code(self):
        """These strings are read by whoever wonders why a version froze."""
        for key, reason in svc.RELIANCE_REASONS.items():
            assert reason.strip(), key
            assert " " in reason, (
                f"{key!r} reads as a code rather than an explanation: {reason!r}")
            assert not reason.isupper()

    def test_the_documented_dependencies_are_all_present(self):
        """The brief's list, pinned so a boundary cannot quietly disappear."""
        for expected in ("experiment", "measurement", "submission", "review",
                         "decision", "contradiction", "report", "export",
                         "package", "comparison", "evidence", "attachment"):
            assert expected in svc.RELIANCE_REASONS, expected

    def test_locking_lives_in_the_service_not_the_routes(self):
        """Route discipline is a convention, and a convention is one new
        endpoint away from being broken silently."""
        import inspect

        source = inspect.getsource(svc)
        assert "async def _rely_on_candidate_version" in source

        from nanobio_studio.app.api.routes import validation as routes

        route_source = inspect.getsource(routes)
        assert "_rely_on_candidate_version" not in route_source, (
            "a route calls the locking helper directly, which puts the "
            "invariant back at the call site")


# ===========================================================================
# 2. Each boundary locks
# ===========================================================================

class TestEachDependencyLocks:

    def test_creating_an_experiment_locks_the_candidate_version(self, harness):
        from nanobio_studio.app.science.statuses import ReadinessArea
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-EXP")
            assert version.status is VersionStatus.DRAFT

            await svc.create_experiment(
                session, actor=_actor(state), candidate_version_id=version.id,
                subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                purpose=ReadinessArea.STRUCTURAL_VISUALIZATION,
                title="Particle size", code="EXP-LOCK-1")
            return version

        version = run_with_session(factory, work)
        assert version.status is VersionStatus.LOCKED
        assert version.locked_at is not None
        assert "experiment" in version.lock_reason

    def test_recording_measurements_locks_the_candidate_version(self, harness):
        from nanobio_studio.app.science.statuses import ReadinessArea
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-MEAS")
            _experiment, experiment_version = await svc.create_experiment(
                session, actor=_actor(state), candidate_version_id=version.id,
                subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                purpose=ReadinessArea.STRUCTURAL_VISUALIZATION,
                title="Particle size", code="EXP-LOCK-2")

            # Unlock so this test observes measurement's own lock rather than
            # the one create_experiment already applied.
            version.status = VersionStatus.DRAFT
            version.locked_at = None
            version.lock_reason = None
            await session.flush()

            await svc.add_measurements(
                session, actor=_actor(state),
                version_id=experiment_version.id,
                rows=[{"endpoint_name": "hydrodynamic diameter",
                      "replicate_id": "1", "result_numeric": 92.4,
                      "result_unit": "nm"}])
            return version

        version = run_with_session(factory, work)
        assert version.status is VersionStatus.LOCKED
        assert "measurement" in version.lock_reason

    def test_submitting_for_review_locks_the_candidate_version(self, harness):
        from nanobio_studio.app.science.statuses import ReadinessArea
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-SUBMIT")
            _experiment, experiment_version = await svc.create_experiment(
                session, actor=_actor(state), candidate_version_id=version.id,
                subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                purpose=ReadinessArea.STRUCTURAL_VISUALIZATION,
                title="Particle size", code="EXP-LOCK-3")

            version.status = VersionStatus.DRAFT
            version.locked_at = None
            version.lock_reason = None
            await session.flush()

            try:
                await svc.submit_version(
                    session, actor=_actor(state),
                    version_id=experiment_version.id)
            except svc.ValidationError:
                # The submission may be refused for scientific reasons that
                # have nothing to do with locking. The lock is applied before
                # those checks, which is what this asserts.
                pass
            return version

        version = run_with_session(factory, work)
        assert version.status is VersionStatus.LOCKED, (
            "submitting for review did not lock the formulation it submits")

    def test_the_first_reason_is_kept_not_the_most_recent(self, harness):
        """Reliance is monotonic, and the first reason is the informative one.

        "An experiment was created against it" explains why a formulation froze
        far better than "a report was generated" three months later.
        """
        from nanobio_studio.app.science.statuses import ReadinessArea
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-FIRST")
            _experiment, experiment_version = await svc.create_experiment(
                session, actor=_actor(state), candidate_version_id=version.id,
                subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                purpose=ReadinessArea.STRUCTURAL_VISUALIZATION,
                title="Particle size", code="EXP-LOCK-4")
            first_reason = version.lock_reason

            await svc.add_measurements(
                session, actor=_actor(state),
                version_id=experiment_version.id,
                rows=[{"endpoint_name": "polydispersity index",
                      "replicate_id": "1", "result_numeric": 0.12}])
            return first_reason, version.lock_reason

        first_reason, later_reason = run_with_session(factory, work)
        assert "experiment" in first_reason
        assert later_reason == first_reason, (
            "a later dependency overwrote the reason the version first froze")


# ===========================================================================
# 3. What a lock actually prevents
# ===========================================================================

class TestWhatALockPrevents:

    def test_a_locked_version_refuses_in_place_scientific_change(self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-REFUSE")
            await cvs.lock_version(session, version=version,
                                   reason="a simulation ran against it",
                                   actor_id=state["author_id"])
            return version.is_editable()

        assert run_with_session(factory, work) is False

    def test_an_unused_draft_is_still_editable(self, harness):
        """Positive control.

        A system that locked everything would pass every assertion above while
        making the product unusable.
        """
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-DRAFT-OK")
            return version.is_editable()

        assert run_with_session(factory, work) is True

    def test_identity_metadata_stays_correctable_on_a_locked_version(self,
                                                                     harness):
        """Fixing a typo in a label changes no science.

        Refusing it would push people to create a revision for a spelling
        correction, which fills the lineage with noise and makes the genuine
        revisions harder to find.
        """
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-IDENTITY")
            await cvs.lock_version(session, version=version, reason="report",
                                   actor_id=state["author_id"])

            consequence = cvs.consequence_of_change({"name", "description"})
            return consequence

        consequence = run_with_session(factory, work)
        assert consequence["identity_only"] is True
        assert consequence["requires"] == "none"
        assert consequence["approval_may_carry_forward"] is True

    def test_a_scientific_change_on_a_locked_version_demands_a_revision(
            self, harness):
        _app, factory, state = harness

        async def work(session):
            version = await _fresh_version(session, state, "LOCK-SCI")
            await cvs.lock_version(session, version=version, reason="review",
                                   actor_id=state["author_id"])

            consequence = cvs.consequence_of_change({"dose_mg_kg"})
            revised, created = await cvs.create_revision(
                session, predecessor=version,
                design_inputs={**DESIGN, "dose_mg_kg": 8.0},
                reason="Dose escalation", actor_id=state["author_id"])
            return consequence, revised, created, version

        consequence, revised, created, version = run_with_session(factory, work)
        assert consequence["approval_may_carry_forward"] is False
        assert created is True
        assert revised.status is VersionStatus.DRAFT
        assert revised.predecessor_version_id == version.id
        assert version.status is VersionStatus.LOCKED, (
            "revising altered the predecessor")


# ===========================================================================
# 4. The lock and the dependent record share a transaction
# ===========================================================================

class TestTransactionalIntegrity:

    def test_a_failed_dependent_write_leaves_the_version_unlocked(self,
                                                                  harness):
        """The half that is easy to get wrong.

        If locking committed separately, a dependent write that failed would
        leave a formulation frozen for a reason that never happened — and
        nobody could edit it or explain why.
        """
        from nanobio_studio.app.science.statuses import ReadinessArea
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

        _app, factory, state = harness

        async def create_version(session):
            return (await _fresh_version(session, state, "LOCK-ROLLBACK")).id

        version_id = run_with_session(factory, create_version)

        async def failing_attempt():
            async with factory() as session:
                version = await session.get(CandidateVersion, version_id)
                try:
                    await svc.create_experiment(
                        session, actor=_actor(state),
                        candidate_version_id=version.id,
                        subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                        purpose=ReadinessArea.STRUCTURAL_VISUALIZATION,
                        title="Will fail",
                        # Deliberately collides with the code used above, so
                        # the dependent insert fails after the lock is applied.
                        code="EXP-LOCK-1")
                    raise RuntimeError("the experiment write was expected to "
                                       "fail and did not")
                except Exception:
                    await session.rollback()

        run_async(failing_attempt())

        async def read():
            async with factory() as session:
                return await session.get(CandidateVersion, version_id)

        version = run_async(read())
        assert version.status is VersionStatus.DRAFT, (
            "the version stayed locked after the dependent write was rolled "
            "back, so the lock committed on its own")
        assert version.locked_at is None
        assert version.lock_reason is None

    def test_a_successful_operation_commits_both(self, harness):
        """Positive control for the rollback test.

        A locking call that never worked at all would also leave the version
        unlocked after a rollback.
        """
        from nanobio_studio.app.science.statuses import ReadinessArea
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype

        _app, factory, state = harness

        async def create_version(session):
            return (await _fresh_version(session, state, "LOCK-COMMIT")).id

        version_id = run_with_session(factory, create_version)

        async def succeed():
            async with factory() as session:
                version = await session.get(CandidateVersion, version_id)
                await svc.create_experiment(
                    session, actor=_actor(state),
                    candidate_version_id=version.id,
                    subtype=ExperimentSubtype.PARTICLE_SIZE_PDI,
                    purpose=ReadinessArea.STRUCTURAL_VISUALIZATION,
                    title="Will succeed", code="EXP-LOCK-COMMIT")
                await session.commit()

        run_async(succeed())

        async def read():
            async with factory() as session:
                return await session.get(CandidateVersion, version_id)

        version = run_async(read())
        assert version.status is VersionStatus.LOCKED
        assert version.locked_at is not None

    def test_the_helper_never_commits_on_its_own(self):
        """Read from the source, because this is the property a future edit is
        most likely to break by adding a convenient `await session.commit()`."""
        import inspect

        source = inspect.getsource(svc._rely_on_candidate_version)
        assert "commit()" not in source, (
            "the locking helper commits, which breaks the transactional "
            "guarantee it exists to provide")


# ===========================================================================
# 5. A speculative question does not freeze a formulation
# ===========================================================================

class TestSpeculativeEvaluationDoesNotLock:

    def test_asking_whether_something_would_be_eligible_locks_nothing(self):
        """`evaluate_version` answers "would this be eligible if approved?".

        The approval path calls it before deciding, so locking there would
        freeze a formulation because somebody looked at it rather than because
        anything relied on it. The approval itself locks, which is the act that
        creates reliance.
        """
        import inspect

        source = inspect.getsource(svc.evaluate_version)
        assert "_rely_on_candidate_version" not in source
        assert "_rely_via_experiment_version" not in source
