"""Candidate revision, locking and supersession.

Replaces the inventory probe that recorded these gaps as defects. Each class
below now asserts the invariant the probe said was missing, so the file reads
as the specification rather than as a list of complaints.

The property everything here serves: **a scientific decision made about a
formulation stays attributable to the formulation it was made about.** Editing
inputs in place after something depends on them does not lose data — it does
something worse, which is to leave a stored result describing a material that
no longer exists, with nothing in the record saying so.

Time is injected everywhere it matters. Nothing sleeps.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.validation_models import (  # noqa: E402
    Candidate, CandidateVersion, ResultsState, SupersessionState, VersionStatus,
)
from nanobio_studio.app.services import candidate_versioning as cv  # noqa: E402

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402


# ---------------------------------------------------------------------------
# An injectable clock
# ---------------------------------------------------------------------------

class Clock:
    """Deterministic time. A test that sleeps for a lock window is a test
    nobody runs."""

    def __init__(self, start: datetime | None = None):
        self.now = start or datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


@pytest.fixture
def clock():
    return Clock()


DESIGN_V1 = {"size_nm": 90.0, "charge_mv": -10.0, "coating": "PEG",
             "dose_mg_kg": 2.0, "name": "First formulation"}


# ---------------------------------------------------------------------------
# Database harness
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    from nanobio_studio.app.db.organization_models import Organization
    from nanobio_studio.app.db.workspace_models import StoredRun
    from nanobio_studio.app.db.auth_models import UserRole
    from nanobio_studio.app.organizations.vocabulary import OrganizationStatus
    from nanobio_studio.app.services.auth_service import create_user

    tmp_dir = tmp_path_factory.mktemp("candidate_versioning")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    async def seed():
        async with factory() as session:
            author = await create_user(
                session, username="cv_author", password="a-long-passphrase-x",
                role=UserRole.RESEARCHER, email="cv_author@versions.test")
            other = await create_user(
                session, username="cv_other", password="a-long-passphrase-y",
                role=UserRole.RESEARCHER, email="cv_other@versions.test")
            await session.flush()

            org = Organization(slug="cv-org", name="Versioning Org",
                               status=OrganizationStatus.ACTIVE)
            second = Organization(slug="cv-other", name="Other Org",
                                  status=OrganizationStatus.ACTIVE)
            session.add_all([org, second])
            await session.flush()

            run = StoredRun(organization_id=org.id, owner_id=author.id,
                            name="versioning study")
            session.add(run)
            await session.flush()

            state.update(org_id=org.id, other_org_id=second.id,
                         study_id=run.id, author_id=author.id,
                         other_id=other.id)
            await session.commit()

    with client:
        run_async(seed())
        yield app, factory, state
    app.dependency_overrides.clear()


async def _new_candidate(session, state, code: str) -> Candidate:
    candidate = Candidate(
        organization_id=state["org_id"], study_id=state["study_id"],
        owner_id=state["author_id"], code=code, name=f"candidate {code}")
    session.add(candidate)
    await session.flush()
    return candidate


async def _first_version(session, candidate, design=None,
                         clock=None) -> CandidateVersion:
    snapshot = cv.canonical_snapshot(design or DESIGN_V1)
    version = CandidateVersion(
        organization_id=candidate.organization_id,
        candidate_id=candidate.id, version_number=1, revision_label="v1",
        design_snapshot_json=snapshot,
        snapshot_checksum=cv.snapshot_checksum(snapshot),
        status=VersionStatus.DRAFT, results_state=ResultsState.NONE,
        created_by=candidate.owner_id,
        created_at=clock() if clock else None)
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
# 1. The model holds what a lineage needs
# ===========================================================================

class TestTheModelRecordsLineage:

    def test_a_version_records_its_predecessor(self):
        columns = set(CandidateVersion.__table__.columns.keys())
        assert "predecessor_version_id" in columns

    def test_a_version_records_workflow_and_supersession_state(self):
        columns = set(CandidateVersion.__table__.columns.keys())
        for expected in ("status", "supersession_state", "superseded_at",
                         "superseded_by_version_id"):
            assert expected in columns

    def test_a_version_records_the_rules_its_numbers_came_from(self):
        """Without these a score can be re-run but not reproduced.

        Re-running gives today's answer under today's rules, which is a
        different number wearing the same name.
        """
        columns = set(CandidateVersion.__table__.columns.keys())
        for expected in ("model_version", "ruleset_version",
                         "reference_data_version", "algorithm_selection"):
            assert expected in columns

    def test_a_version_can_say_its_results_are_stale(self):
        columns = set(CandidateVersion.__table__.columns.keys())
        assert "results_state" in columns
        assert "results_inherited_from_id" in columns

    def test_the_database_protects_lineage_not_just_the_service(self):
        """Constraints, because they hold for every writer that will ever
        exist — including a migration and a repair script run at 2am."""
        names = {c.name for c in CandidateVersion.__table__.constraints
                 if c.name}
        for expected in ("ck_candidate_version_not_own_predecessor",
                         "ck_candidate_version_not_own_successor",
                         "ck_candidate_version_number_positive",
                         "ck_candidate_version_supersession_complete",
                         "ck_candidate_version_locked_has_timestamp",
                         "uq_candidate_version"):
            assert expected in names, f"missing constraint {expected}"

    def test_the_five_statuses_are_distinguishable(self):
        assert [s.value for s in VersionStatus] == [
            "draft", "locked", "approved", "superseded", "withdrawn"]

    def test_latest_is_not_one_of_them(self):
        """"Latest" is ambiguous between newest draft and current approved.

        A screen that says it has told the reader nothing, so it must not be
        expressible as a status.
        """
        assert "latest" not in {s.value for s in VersionStatus}
        assert "current" not in {s.value for s in VersionStatus}


# ===========================================================================
# 2. What a change demands
# ===========================================================================

class TestConsequenceOfChange:

    def test_a_label_change_alone_carries_approval_forward(self):
        """Administrative correction: fixing a typo changes no science."""
        result = cv.consequence_of_change({"name", "description"})
        assert result["requires"] == "none"
        assert result["identity_only"] is True
        assert result["approval_may_carry_forward"] is True

    @pytest.mark.parametrize("field", [
        "size_nm", "charge_mv", "coating", "material", "targeting_ligand",
        "payload", "dose_mg_kg", "administration_route", "sequence",
        "biological_target", "pk_model", "model_version", "ruleset_version",
        "decision_threshold",
    ])
    def test_no_scientific_change_carries_approval_forward(self, field):
        """The brief's minimum list, one field at a time.

        Parametrised so a failure names the field rather than reporting that
        "a set" behaved wrongly.
        """
        result = cv.consequence_of_change({field})
        assert result["approval_may_carry_forward"] is False, field
        assert result["requires"] != "none", field

    def test_dose_and_route_demand_a_safety_opinion(self):
        """The two that most directly decide harm."""
        for field in ("dose_mg_kg", "administration_route", "payload",
                      "targeting_ligand", "material"):
            assert cv.consequence_of_change({field})["requires"] == \
                "safety_review", field

    def test_the_strongest_demand_wins_in_a_mixed_change(self):
        result = cv.consequence_of_change({"size_nm", "dose_mg_kg"})
        assert result["requires"] == "safety_review"

    def test_an_unclassified_field_is_not_treated_as_harmless(self):
        """Default-deny for fields nobody has classified.

        Treating an unrecognised input as harmless because it is not on a list
        is how a newly added field silently inherits an approval it was never
        assessed under.
        """
        result = cv.consequence_of_change({"some_field_added_next_year"})
        assert result["requires"] == "recalculation"
        assert result["approval_may_carry_forward"] is False

    def test_the_explanation_names_the_fields(self):
        result = cv.consequence_of_change({"dose_mg_kg"})
        assert "dose_mg_kg" in result["explanation"]
        assert result["explanation"].strip() != ""


# ===========================================================================
# 3. Structured comparison
# ===========================================================================

class TestStructuredComparison:

    def test_changes_are_reported_field_by_field(self):
        before = cv.canonical_snapshot({"size_nm": 90.0, "coating": "PEG"})
        after = cv.canonical_snapshot({"size_nm": 120.0, "coating": "PEG"})

        changes = cv.compare_snapshots(before, after)
        assert len(changes) == 1
        assert changes[0].field == "size_nm"
        assert changes[0].before == 90.0
        assert changes[0].after == 120.0
        assert changes[0].kind == "changed"
        assert changes[0].is_scientific is True

    def test_additions_and_removals_are_distinguished(self):
        before = cv.canonical_snapshot({"size_nm": 90.0, "old_field": 1})
        after = cv.canonical_snapshot({"size_nm": 90.0, "new_field": 2})

        kinds = {c.field: c.kind for c in cv.compare_snapshots(before, after)}
        assert kinds == {"old_field": "removed", "new_field": "added"}

    def test_identity_fields_are_marked_as_non_scientific(self):
        before = cv.canonical_snapshot({"name": "old", "size_nm": 90.0})
        after = cv.canonical_snapshot({"name": "new", "size_nm": 90.0})

        changes = cv.compare_snapshots(before, after)
        assert len(changes) == 1
        assert changes[0].is_scientific is False

    def test_an_unchanged_snapshot_reports_nothing(self):
        snapshot = cv.canonical_snapshot(DESIGN_V1)
        assert cv.compare_snapshots(snapshot, snapshot) == []

    def test_equal_formulations_share_a_checksum_whatever_the_key_order(self):
        one = cv.canonical_snapshot({"a": 1, "b": 2})
        two = cv.canonical_snapshot({"b": 2, "a": 1})
        assert cv.snapshot_checksum(one) == cv.snapshot_checksum(two)


# ===========================================================================
# 4. Revision
# ===========================================================================

class TestRevision:

    def test_a_revision_requires_a_reason(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-REASON")
            first = await _first_version(session, candidate, clock=clock)
            with pytest.raises(cv.RevisionRefused) as caught:
                await cv.create_revision(
                    session, predecessor=first, design_inputs=None,
                    reason="   ", actor_id=state["author_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "reason_required"

    def test_a_revision_records_its_predecessor_and_reason(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-LINK")
            first = await _first_version(session, candidate, clock=clock)
            clock.advance(hours=2)
            second, created = await cv.create_revision(
                session, predecessor=first,
                design_inputs={**DESIGN_V1, "size_nm": 130.0},
                reason="Particle size increased after milling change",
                actor_id=state["author_id"], now=clock)
            return first, second, created

        first, second, created = run_with_session(factory, work)
        assert created is True
        assert second.predecessor_version_id == first.id
        assert second.version_number == first.version_number + 1
        assert second.revision_label == "v2"
        assert "milling" in second.revision_reason

    def test_a_revision_starts_as_a_draft_and_never_inherits_approval(
            self, harness, clock):
        """The single most important assertion in this file.

        If an approved version could be revised into another approved version,
        the entire review process could be bypassed by editing.
        """
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-APPROVAL")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first,
                design_inputs={**DESIGN_V1, "dose_mg_kg": 8.0},
                reason="Dose escalation for the next cohort",
                actor_id=state["author_id"], now=clock)
            return first, second

        first, second = run_with_session(factory, work)
        assert first.status is VersionStatus.APPROVED, (
            "the predecessor's approval must be untouched")
        assert second.status is VersionStatus.DRAFT, (
            "a revision inherited an approval — every review gate is "
            "bypassable by editing")

    def test_copied_results_are_marked_stale_not_current(self, harness, clock):
        """Presenting a predecessor's numbers as the revision's own would be
        the most misleading thing this feature could do."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-STALE")
            first = await _first_version(session, candidate, clock=clock)
            first.results_state = ResultsState.CURRENT
            first.model_version = "scoring-2.1"
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first,
                design_inputs={**DESIGN_V1, "size_nm": 150.0},
                reason="Larger particle variant",
                actor_id=state["author_id"], now=clock)
            return first, second

        first, second = run_with_session(factory, work)
        assert second.results_state is ResultsState.STALE
        assert second.results_inherited_from_id == first.id, (
            "the interface must be able to say WHOSE numbers these were")
        assert first.results_state is ResultsState.CURRENT, (
            "the predecessor's results were altered")

    def test_the_predecessor_is_not_superseded_by_the_act_of_revising(
            self, harness, clock):
        """A draft revision is somebody's work in progress.

        Auto-superseding would let any author retire an approved formulation
        simply by starting to edit it.
        """
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-NOSUPER")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Exploring an alternative coating",
                actor_id=state["author_id"], now=clock)
            return first

        first = run_with_session(factory, work)
        assert first.status is VersionStatus.APPROVED
        assert first.superseded_by_version_id is None
        assert first.supersession_state is SupersessionState.NONE

    def test_a_retried_request_is_idempotent(self, harness, clock):
        """Two identical submissions must not fork the lineage."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-IDEMPOTENT")
            first = await _first_version(session, candidate, clock=clock)

            one, created_one = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Retry probe", actor_id=state["author_id"],
                idempotency_key="request-abc", now=clock)
            two, created_two = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Retry probe", actor_id=state["author_id"],
                idempotency_key="request-abc", now=clock)
            return one, created_one, two, created_two

        one, created_one, two, created_two = run_with_session(factory, work)
        assert created_one is True
        assert created_two is False, "the retry created a second version"
        assert one.id == two.id

    def test_a_different_key_does_create_a_second_revision(self, harness, clock):
        """Positive control: idempotency must not collapse distinct requests."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-DISTINCT")
            first = await _first_version(session, candidate, clock=clock)

            one, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="First branch", actor_id=state["author_id"],
                idempotency_key="key-one", now=clock)
            two, created = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Second branch", actor_id=state["author_id"],
                idempotency_key="key-two", now=clock)
            return one, two, created

        one, two, created = run_with_session(factory, work)
        assert created is True
        assert one.id != two.id
        assert one.version_number != two.version_number

    def test_version_numbers_are_allocated_without_collision(self, harness,
                                                             clock):
        """Ten revisions in sequence produce ten distinct numbers.

        `COUNT(*) + 1` gave the wrong answer as soon as a row was ever removed;
        `MAX + 1` is what makes the sequence hold.
        """
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-NUMBERS")
            current = await _first_version(session, candidate, clock=clock)
            numbers = [current.version_number]
            for index in range(9):
                current, _ = await cv.create_revision(
                    session, predecessor=current, design_inputs=None,
                    reason=f"Revision {index}", actor_id=state["author_id"],
                    now=clock)
                numbers.append(current.version_number)
            return numbers

        numbers = run_with_session(factory, work)
        assert numbers == list(range(1, 11)), numbers
        assert len(set(numbers)) == len(numbers)

    def test_a_lineage_is_walkable_to_its_root(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "REV-LINEAGE")
            current = await _first_version(session, candidate, clock=clock)
            for index in range(4):
                current, _ = await cv.create_revision(
                    session, predecessor=current, design_inputs=None,
                    reason=f"Step {index}", actor_id=state["author_id"],
                    now=clock)
            chain = await cv.lineage_of(session, current)
            return [v.version_number for v in chain]

        assert run_with_session(factory, work) == [1, 2, 3, 4, 5]


# ===========================================================================
# 5. Supersession
# ===========================================================================

class TestSupersession:

    def test_a_draft_cannot_take_over_from_a_reviewed_version(self, harness,
                                                              clock):
        """The gate that stops review being bypassed by supersession."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-DRAFT")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Proposed replacement", actor_id=state["author_id"],
                now=clock)

            with pytest.raises(cv.VersioningError) as caught:
                await cv.accept_supersession(
                    session, predecessor=first, successor=second,
                    actor_id=state["other_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "successor_is_draft"

    def test_supersession_records_who_when_and_why(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-RECORD")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Improved stability", actor_id=state["author_id"],
                now=clock)
            second.status = VersionStatus.APPROVED
            second.locked_at = clock()
            await session.flush()

            clock.advance(days=1)
            await cv.accept_supersession(
                session, predecessor=first, successor=second,
                actor_id=state["other_id"], decision_id=4242,
                reason="v2 approved and adopted", now=clock)
            return first, second

        first, second = run_with_session(factory, work)
        assert first.status is VersionStatus.SUPERSEDED
        assert first.supersession_state is SupersessionState.ACCEPTED
        assert first.superseded_by_version_id == second.id
        assert first.superseded_by_user_id == state["other_id"]
        assert first.superseded_at is not None
        assert first.supersession_decision_id == 4242
        assert "adopted" in first.supersession_reason

    def test_superseding_does_not_erase_what_happened(self, harness, clock):
        """Supersession says what to use next. It does not unsay the past."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-KEEP")
            first = await _first_version(session, candidate, clock=clock)
            original_snapshot = first.design_snapshot_json
            original_checksum = first.snapshot_checksum
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first,
                design_inputs={**DESIGN_V1, "size_nm": 200.0},
                reason="Bigger", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.APPROVED
            second.locked_at = clock()
            await session.flush()

            await cv.accept_supersession(
                session, predecessor=first, successor=second,
                actor_id=state["other_id"], reason="adopted", now=clock)
            return first, original_snapshot, original_checksum

        first, snapshot, checksum = run_with_session(factory, work)
        assert first.design_snapshot_json == snapshot, (
            "the superseded version's inputs were altered")
        assert first.snapshot_checksum == checksum
        assert first.id is not None, "the row was removed"

    def test_a_version_cannot_supersede_itself(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-SELF")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.LOCKED
            first.locked_at = clock()
            await session.flush()

            with pytest.raises(cv.VersioningError) as caught:
                await cv.accept_supersession(
                    session, predecessor=first, successor=first,
                    actor_id=state["author_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "self_supersession"

    def test_supersession_across_candidates_is_refused(self, harness, clock):
        """One formulation does not supersede a different formulation."""
        _app, factory, state = harness

        async def work(session):
            one = await _new_candidate(session, state, "SUP-X1")
            two = await _new_candidate(session, state, "SUP-X2")
            first = await _first_version(session, one, clock=clock)
            other = await _first_version(session, two, clock=clock)
            for version in (first, other):
                version.status = VersionStatus.LOCKED
                version.locked_at = clock()
            await session.flush()

            with pytest.raises(cv.VersioningError) as caught:
                await cv.accept_supersession(
                    session, predecessor=first, successor=other,
                    actor_id=state["author_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "cross_candidate_supersession"

    def test_an_earlier_version_cannot_supersede_a_later_one(self, harness,
                                                             clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-ORDER")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.LOCKED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="later", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.LOCKED
            second.locked_at = clock()
            await session.flush()

            with pytest.raises(cv.VersioningError) as caught:
                await cv.accept_supersession(
                    session, predecessor=second, successor=first,
                    actor_id=state["author_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "successor_not_later"

    def test_a_draft_predecessor_cannot_be_superseded(self, harness, clock):
        """Nothing has relied on a draft, so it should be edited or discarded
        rather than formally replaced."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-DRAFTPRED")
            first = await _first_version(session, candidate, clock=clock)
            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="next", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.LOCKED
            second.locked_at = clock()
            await session.flush()

            with pytest.raises(cv.VersioningError) as caught:
                await cv.accept_supersession(
                    session, predecessor=first, successor=second,
                    actor_id=state["author_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "not_supersedable"

    def test_a_second_supersession_attempt_is_refused(self, harness, clock):
        """Whoever acts second is told, not silently ignored.

        In one session the status guard catches this before the conditional
        UPDATE does, which is the better error to give: "that version has
        already been superseded" is more useful than "the record moved". The
        conditional UPDATE is what covers the case the status guard cannot see
        — two sessions holding independently-loaded copies — and that is
        tested separately below.
        """
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-SECOND")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="a", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.APPROVED
            second.locked_at = clock()
            await session.flush()

            await cv.accept_supersession(
                session, predecessor=first, successor=second,
                actor_id=state["other_id"], reason="first writer", now=clock)

            with pytest.raises(cv.VersioningError) as caught:
                await cv.accept_supersession(
                    session, predecessor=first, successor=second,
                    actor_id=state["author_id"], reason="second writer",
                    now=clock)
            return first, caught.value.code

        first, code = run_with_session(factory, work)
        assert code == "not_supersedable"
        assert first.supersession_reason == "first writer", (
            "the second writer overwrote the first decision")

    def test_two_sessions_racing_resolve_to_one_supersession(self, harness,
                                                             clock):
        """The conditional UPDATE, exercised the way it is actually needed.

        Two sessions each load the version while it is still APPROVED — so
        neither one's status guard can see the other — and both try to
        supersede. The `revision` predicate is what makes exactly one of them
        win. Without it both UPDATEs would succeed and the second would
        silently overwrite the first decision about which version is current,
        including who made it and why.
        """
        _app, factory, state = harness

        async def build(session):
            candidate = await _new_candidate(session, state, "SUP-TWOSESSION")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="a", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.APPROVED
            second.locked_at = clock()
            await session.flush()
            return first.id, second.id, first.revision

        first_id, second_id, revision_at_read = run_with_session(factory, build)

        async def race():
            outcomes = []
            # Two sessions, each holding its own copy loaded at the same
            # revision — which is what "at the same time" means here.
            async with factory() as session_a, factory() as session_b:
                first_a = await session_a.get(CandidateVersion, first_id)
                second_a = await session_a.get(CandidateVersion, second_id)
                first_b = await session_b.get(CandidateVersion, first_id)
                second_b = await session_b.get(CandidateVersion, second_id)

                try:
                    await cv.accept_supersession(
                        session_a, predecessor=first_a, successor=second_a,
                        actor_id=state["other_id"], reason="writer A",
                        expected_revision=revision_at_read, now=clock)
                    await session_a.commit()
                    outcomes.append("A")
                except cv.VersioningError as exc:
                    outcomes.append(f"A:{exc.code}")

                try:
                    await cv.accept_supersession(
                        session_b, predecessor=first_b, successor=second_b,
                        actor_id=state["author_id"], reason="writer B",
                        expected_revision=revision_at_read, now=clock)
                    await session_b.commit()
                    outcomes.append("B")
                except cv.VersioningError as exc:
                    outcomes.append(f"B:{exc.code}")
            return outcomes

        outcomes = run_async(race())

        winners = [o for o in outcomes if ":" not in o]
        losers = [o for o in outcomes if ":" in o]
        assert len(winners) == 1, (
            f"expected exactly one supersession to succeed, got {outcomes}")
        assert len(losers) == 1
        assert "supersession_conflict" in losers[0], (
            f"the loser was refused for the wrong reason: {losers[0]}")

        async def read():
            async with factory() as session:
                return await session.get(CandidateVersion, first_id)

        final = run_async(read())
        assert final.supersession_state is SupersessionState.ACCEPTED
        assert final.supersession_reason == "writer A", (
            "the losing writer's reason was recorded, so its UPDATE landed")

    def test_a_proposal_is_not_a_supersession(self, harness, clock):
        """Proposing and accepting are separated so they can require
        different authority."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-PROPOSE")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="b", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.LOCKED
            second.locked_at = clock()
            await session.flush()

            await cv.propose_supersession(
                session, predecessor=first, successor=second,
                reason="Please adopt v2", actor_id=state["author_id"])
            return first

        first = run_with_session(factory, work)
        assert first.supersession_state is SupersessionState.PROPOSED
        assert first.status is VersionStatus.APPROVED, (
            "proposing changed the version's status")
        assert first.superseded_by_version_id is None

    def test_a_refused_proposal_leaves_the_predecessor_untouched(self, harness,
                                                                 clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "SUP-REFUSE")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="c", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.LOCKED
            second.locked_at = clock()
            await session.flush()

            await cv.propose_supersession(
                session, predecessor=first, successor=second,
                reason="adopt", actor_id=state["author_id"])
            await cv.refuse_supersession(
                session, predecessor=first,
                reason="Stability data does not support the change",
                actor_id=state["other_id"])
            return first

        first = run_with_session(factory, work)
        assert first.supersession_state is SupersessionState.REFUSED
        assert first.status is VersionStatus.APPROVED
        assert first.superseded_by_version_id is None


# ===========================================================================
# 6. Which version is "current"
# ===========================================================================

class TestWhichVersionIsCurrent:

    def test_a_new_draft_does_not_become_the_effective_version(self, harness,
                                                               clock):
        """"Latest" would make an unreviewed draft effective the moment
        somebody started typing."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "CUR-DRAFT")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.APPROVED
            first.locked_at = clock()
            await session.flush()

            draft, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="wip", actor_id=state["author_id"], now=clock)
            effective = await cv.current_effective_version(
                session, candidate.id)
            newest_draft = await cv.latest_draft_version(session, candidate.id)
            return first.id, draft.id, effective.id, newest_draft.id

        first_id, draft_id, effective_id, newest_draft_id = \
            run_with_session(factory, work)
        assert effective_id == first_id, (
            "an unreviewed draft became the effective version")
        assert newest_draft_id == draft_id

    def test_with_no_approval_the_newest_locked_version_is_effective(
            self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "CUR-LOCKED")
            first = await _first_version(session, candidate, clock=clock)
            first.status = VersionStatus.LOCKED
            first.locked_at = clock()
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="d", actor_id=state["author_id"], now=clock)
            second.status = VersionStatus.LOCKED
            second.locked_at = clock()
            await session.flush()

            effective = await cv.current_effective_version(
                session, candidate.id)
            return second.id, effective.id

        second_id, effective_id = run_with_session(factory, work)
        assert effective_id == second_id


# ===========================================================================
# 7. Locking and withdrawal
# ===========================================================================

class TestLockingAndWithdrawal:

    def test_locking_is_idempotent(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "LOCK-IDEM")
            first = await _first_version(session, candidate, clock=clock)
            one = await cv.lock_version(
                session, version=first, reason="simulation run",
                actor_id=state["author_id"], now=clock)
            two = await cv.lock_version(
                session, version=first, reason="review started",
                actor_id=state["author_id"], now=clock)
            return one, two, first

        one, two, first = run_with_session(factory, work)
        assert one is True
        assert two is False, "locking twice reported a second change"
        assert first.lock_reason == "simulation run", (
            "the second lock overwrote the reason for the first")

    def test_a_locked_version_reports_itself_uneditable(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "LOCK-EDIT")
            first = await _first_version(session, candidate, clock=clock)
            editable_before = first.is_editable()
            await cv.lock_version(session, version=first, reason="report",
                                  actor_id=state["author_id"], now=clock)
            return editable_before, first.is_editable(), first.locked_at

        before, after, locked_at = run_with_session(factory, work)
        assert before is True
        assert after is False
        assert locked_at is not None

    def test_withdrawal_requires_a_reason(self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "WITHDRAW-REASON")
            first = await _first_version(session, candidate, clock=clock)
            with pytest.raises(cv.VersioningError) as caught:
                await cv.withdraw_version(
                    session, version=first, reason="",
                    actor_id=state["author_id"], now=clock)
            return caught.value.code

        assert run_with_session(factory, work) == "reason_required"

    def test_withdrawal_is_distinct_from_supersession(self, harness, clock):
        """"We replaced this" and "we no longer stand behind this" are
        different claims to a regulator."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "WITHDRAW-DISTINCT")
            first = await _first_version(session, candidate, clock=clock)
            await cv.withdraw_version(
                session, version=first, reason="Contaminated batch",
                actor_id=state["author_id"], now=clock)
            return first

        first = run_with_session(factory, work)
        assert first.status is VersionStatus.WITHDRAWN
        assert first.superseded_by_version_id is None
        assert first.supersession_state is SupersessionState.NONE

    def test_a_withdrawn_version_can_still_be_revised(self, harness, clock):
        """Revising a withdrawn version to correct what was wrong with it is
        the normal recovery; blocking it would push people to start again with
        no lineage."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "WITHDRAW-REVISE")
            first = await _first_version(session, candidate, clock=clock)
            await cv.withdraw_version(
                session, version=first, reason="Wrong excipient",
                actor_id=state["author_id"], now=clock)
            second, created = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="Corrected excipient", actor_id=state["author_id"],
                now=clock)
            return created, second.predecessor_version_id, first.id

        created, predecessor_id, first_id = run_with_session(factory, work)
        assert created is True
        assert predecessor_id == first_id


# ===========================================================================
# 8. Recalculation and provenance
# ===========================================================================

class TestRecalculationAndProvenance:

    def test_recalculation_records_the_rules_that_produced_the_result(
            self, harness, clock):
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "RECALC")
            first = await _first_version(session, candidate, clock=clock)
            await cv.mark_results_stale(session, version=first)
            stale = first.results_state

            await cv.request_recalculation(session, version=first)
            requested = first.results_state

            await cv.record_recalculation(
                session, version=first, model_version="scoring-3.0",
                ruleset_version="rules-2026-08",
                reference_data_version="refdata-11")
            return stale, requested, first

        stale, requested, first = run_with_session(factory, work)
        assert stale is ResultsState.STALE
        assert requested is ResultsState.RECALCULATING
        assert first.results_state is ResultsState.CURRENT
        assert first.model_version == "scoring-3.0"
        assert first.ruleset_version == "rules-2026-08"
        assert first.reference_data_version == "refdata-11"

    def test_recalculation_clears_the_inherited_marker(self, harness, clock):
        """Once recalculated the numbers are this version's own."""
        _app, factory, state = harness

        async def work(session):
            candidate = await _new_candidate(session, state, "RECALC-CLEAR")
            first = await _first_version(session, candidate, clock=clock)
            first.results_state = ResultsState.CURRENT
            await session.flush()

            second, _ = await cv.create_revision(
                session, predecessor=first, design_inputs=None,
                reason="e", actor_id=state["author_id"], now=clock)
            inherited_before = second.results_inherited_from_id

            await cv.record_recalculation(session, version=second,
                                          model_version="scoring-3.0")
            return inherited_before, second

        inherited_before, second = run_with_session(factory, work)
        assert inherited_before is not None
        assert second.results_inherited_from_id is None
        assert second.results_state is ResultsState.CURRENT
