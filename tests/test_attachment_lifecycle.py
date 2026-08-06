"""The attachment lifecycle, over HTTP, with the storage layer failing on cue.

What breaks in production, and is unreachable in a happy-path test
------------------------------------------------------------------
The database and the object store are two systems. Almost every attachment bug
worth having lives in the seam between them:

* the object is written and the row never finalises — bytes nobody references;
* the row commits and the object was never written — a download that 500s;
* an object vanishes under a lifecycle rule — the same, discovered a month late;
* a delete reports success while the bytes remain — the one deletion outcome
  that must never happen quietly;
* a retried upload overwrites a finalised object.

Each has a state in ``AttachmentState`` and a test here, driven through the
real HTTP routes against a store that can be told to fail.

Authorization is re-asserted, not assumed
-----------------------------------------
The storage layer is new, so every access rule the registry already had is
re-tested *through it*: foreign organization, guessed identifier, revoked and
suspended and expired membership, and the CRO attachment restriction. A new
layer between the route and the bytes is exactly where an authorization check
gets skipped, and "it was checked before we added storage" is not evidence
about the code that exists now.

Every denial has a positive control against a real stored object.
"""

from __future__ import annotations

import hashlib
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.api.deps_organization import (  # noqa: E402
    ORGANIZATION_HEADER,
)
from nanobio_studio.app.db.auth_models import UserRole  # noqa: E402
from nanobio_studio.app.db.validation_models import (  # noqa: E402
    AttachmentState,
)
from nanobio_studio.app.organizations.vocabulary import (  # noqa: E402
    AccessScope, MembershipStatus, OrganizationRole, OrganizationStatus,
    StudyRole,
)
from nanobio_studio.app.storage.memory import InMemoryObjectStore  # noqa: E402

from tests.conftest import make_isolated_auth_client, run_async  # noqa: E402

VALIDATION = "/api/v1/validation"
PASSWORD = "Fixture-Only-Passphrase-9f3a2b"

CSV = b"time_s,signal\n0,1.00\n1,0.52\n2,0.27\n"
CSV_DIGEST = hashlib.sha256(CSV).hexdigest()


@pytest.fixture(scope="module")
def registry(tmp_path_factory):
    """Two organizations, a draft experiment in each, and a full cast."""
    from sqlalchemy import select

    from nanobio_studio.app.db.organization_models import (
        Organization, OrganizationMembership, StudyAssignment,
    )
    from nanobio_studio.app.db.validation_models import (
        Candidate, CandidateVersion, ExperimentVersion, ValidationExperiment,
    )
    from nanobio_studio.app.db.workspace_models import (
        Project, RecordOrigin, RunStatus, StoredRun,
    )
    from nanobio_studio.app.services.auth_service import create_user
    from nanobio_studio.app.science.statuses import ReadinessArea
    from nanobio_studio.app.validation.vocabulary import (
        ExperimentStatus, ExperimentSubtype,
    )

    tmp_dir = tmp_path_factory.mktemp("attachment_lifecycle")
    app, client, factory = make_isolated_auth_client(tmp_dir)
    state: dict = {}

    CAST = {
        "att_researcher": (OrganizationRole.RESEARCHER,
                           AccessScope.ORGANIZATION, {}),
        "att_owner": (OrganizationRole.OWNER, AccessScope.ORGANIZATION, {}),
        "att_cro": (OrganizationRole.LAB_CONTRIBUTOR,
                    AccessScope.ASSIGNED_STUDIES,
                    {"external_organization": "Contract Labs Ltd",
                     "may_download_attachments": False}),
        "att_suspended": (OrganizationRole.RESEARCHER,
                          AccessScope.ORGANIZATION,
                          {"status": MembershipStatus.SUSPENDED}),
        "att_revoked": (OrganizationRole.RESEARCHER,
                        AccessScope.ORGANIZATION,
                        {"status": MembershipStatus.REVOKED}),
        "att_expired": (OrganizationRole.RESEARCHER,
                        AccessScope.ORGANIZATION,
                        {"expires_at": datetime.now(timezone.utc)
                         - timedelta(days=1)}),
    }

    async def seed():
        async with factory() as session:
            users = {}
            for name in (*CAST, "other_researcher", "unaffiliated"):
                users[name] = await create_user(
                    session, username=name, password=PASSWORD,
                    role=UserRole.RESEARCHER, email=f"{name}@lifecycle.test")
            await session.flush()

            alpha = Organization(slug="att-alpha", name="Attachment Alpha",
                                 status=OrganizationStatus.ACTIVE)
            beta = Organization(slug="att-beta", name="Attachment Beta",
                                status=OrganizationStatus.ACTIVE)
            session.add_all([alpha, beta])
            await session.flush()

            for name, (role, scope, extra) in CAST.items():
                session.add(OrganizationMembership(
                    organization_id=alpha.id, user_id=users[name].id,
                    role=role, scope=scope,
                    status=extra.get("status", MembershipStatus.ACTIVE),
                    expires_at=extra.get("expires_at"),
                    external_organization=extra.get("external_organization"),
                    may_download_attachments=extra.get(
                        "may_download_attachments", True)))
            session.add(OrganizationMembership(
                organization_id=beta.id, user_id=users["other_researcher"].id,
                role=OrganizationRole.RESEARCHER,
                scope=AccessScope.ORGANIZATION,
                status=MembershipStatus.ACTIVE))
            await session.flush()

            for label, organization, who in (("alpha", alpha, "att_researcher"),
                                             ("beta", beta,
                                              "other_researcher")):
                project = Project(name=f"{label} project",
                                  owner_id=users[who].id,
                                  organization_id=organization.id)
                session.add(project)
                await session.flush()
                study = StoredRun(
                    name=f"{label} study", project_id=project.id,
                    owner_id=users[who].id, origin=RecordOrigin.USER,
                    status=RunStatus.COMPLETE,
                    organization_id=organization.id)
                session.add(study)
                await session.flush()
                session.add(StudyAssignment(
                    organization_id=organization.id, study_id=study.id,
                    user_id=users[who].id, role=StudyRole.CONTRIBUTOR,
                    status=MembershipStatus.ACTIVE))

                candidate = Candidate(
                    organization_id=organization.id, study_id=study.id,
                    project_id=project.id, owner_id=users[who].id,
                    code=f"{label.upper()}-1", name=f"{label} candidate")
                session.add(candidate)
                await session.flush()
                candidate_version = CandidateVersion(
                    organization_id=organization.id, candidate_id=candidate.id,
                    version_number=1, design_snapshot_json="{}",
                    snapshot_checksum="0" * 64, created_by=users[who].id)
                session.add(candidate_version)
                await session.flush()
                experiment = ValidationExperiment(
                    organization_id=organization.id, code=f"{label.upper()}-EXP",
                    candidate_id=candidate.id, study_id=study.id,
                    project_id=project.id, owner_id=users[who].id,
                    subtype=ExperimentSubtype.CYTOTOXICITY,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT, title=f"{label} experiment")
                session.add(experiment)
                await session.flush()
                version = ExperimentVersion(
                    organization_id=organization.id,
                    experiment_id=experiment.id, version_number=1,
                    candidate_version_id=candidate_version.id,
                    status=ExperimentStatus.DRAFT)
                session.add(version)
                await session.flush()

                state[f"{label}_organization_id"] = organization.id
                state[f"{label}_version_id"] = version.id

            state["users"] = {k: v.id for k, v in users.items()}
            await session.commit()

    with client:
        run_async(seed())
        yield app, client, state
    app.dependency_overrides.clear()


@pytest.fixture
def store(registry):
    """A fresh S3-compatible store per test, installed as the default."""
    from nanobio_studio.app.validation import storage as storage_module

    fresh = InMemoryObjectStore(bucket="lifecycle-bucket", driver="s3")
    adapter = storage_module.ObjectBackedAttachmentStore(fresh)
    storage_module.set_default_store(adapter)
    try:
        yield fresh
    finally:
        storage_module.set_default_store(None)


def _login(client, username: str) -> None:
    response = client.post("/api/v1/auth/login",
                           json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text


def _upload(client, state, content: bytes = CSV, filename: str = "run.csv",
            mime: str = "text/csv", version_id: int | None = None):
    version = version_id or state["alpha_version_id"]
    return client.post(
        f"{VALIDATION}/versions/{version}/attachments?category=raw_data",
        files={"file": (filename, io.BytesIO(content), mime)},
        headers={ORGANIZATION_HEADER: str(state["alpha_organization_id"])})


def _attachment_row(app, attachment_id: int):
    from sqlalchemy import select

    from nanobio_studio.app.db.auth_session import get_auth_session
    from nanobio_studio.app.db.validation_models import ExperimentAttachment

    async def read():
        generator = app.dependency_overrides[get_auth_session]()
        session = await generator.__anext__()
        try:
            return (await session.execute(
                select(ExperimentAttachment).where(
                    ExperimentAttachment.id == attachment_id)
            )).scalars().first()
        finally:
            await generator.aclose()

    return run_async(read())


# ===========================================================================
# 1. The happy path, and what it leaves behind
# ===========================================================================

class TestUploadAndDownload:

    def test_an_authorized_researcher_can_upload_and_download(
            self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")

        created = _upload(client, state)
        assert created.status_code == 200, created.text
        attachment_id = created.json()["id"]

        downloaded = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.content == CSV

    def test_the_row_records_where_the_object_went(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        row = _attachment_row(_app, attachment_id)
        assert row.state is AttachmentState.AVAILABLE
        assert row.storage_backend == "s3"
        assert row.storage_bucket == "lifecycle-bucket"
        assert row.storage_key.startswith(
            f"att/{state['alpha_organization_id']}/{attachment_id}/")

    def test_the_object_key_carries_nothing_from_the_filename(
            self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(
            client, state, filename="patient-jane-doe-carcinoma.csv"
        ).json()["id"]

        row = _attachment_row(_app, attachment_id)
        for leak in ("patient", "jane", "doe", "carcinoma", "csv"):
            assert leak not in row.storage_key.lower()

    def test_the_download_never_renders_inline(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in response.headers["content-security-policy"]
        # So a deleted attachment cannot come back from a cache, and so
        # switching organization cannot resurrect the previous one's file.
        assert "no-store" in response.headers["cache-control"]

    def test_the_response_never_exposes_the_storage_key(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        created = _upload(client, state)
        assert "storage_key" not in created.text
        assert "lifecycle-bucket" not in created.text

    def test_a_large_file_within_the_limit_round_trips(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        payload = b"a,b\n" + b"1,2\n" * 200_000       # ~1.2 MB
        created = _upload(client, state, content=payload)
        assert created.status_code == 200, created.text

        downloaded = client.get(
            f"{VALIDATION}/attachments/{created.json()['id']}")
        assert downloaded.content == payload


# ===========================================================================
# 2. Refused uploads leave nothing
# ===========================================================================

class TestUploadSafety:

    @pytest.mark.parametrize("content,filename,mime,code", [
        (b"", "empty.csv", "text/csv", "empty_file"),
        (b"MZ\x90\x00executable", "run.csv", "text/csv", "executable_content"),
        (b"#!/bin/sh\necho hi", "run.csv", "text/csv", "executable_content"),
        (b"a,b\n1,2\n", "run.exe", "application/x-msdownload",
         "unsupported_type"),
        (b"a,b\n1,2\n", "run.txt", "text/csv", "type_extension_mismatch"),
    ])
    def test_a_refused_upload_stores_no_object(self, registry, store,
                                               content, filename, mime, code):
        _app, client, state = registry
        _login(client, "att_researcher")
        before = len(list(store.list_keys()))

        response = _upload(client, state, content=content, filename=filename,
                           mime=mime)
        assert response.status_code == 400, response.text
        assert response.json()["error"] == code
        assert len(list(store.list_keys())) == before, (
            "a refused upload must leave no bytes behind")

    def test_an_oversized_file_is_refused(self, registry, store):
        from nanobio_studio.app.validation.storage import MAX_ATTACHMENT_BYTES

        _app, client, state = registry
        _login(client, "att_researcher")
        payload = b"x" * (MAX_ATTACHMENT_BYTES + 1)
        response = _upload(client, state, content=payload)
        assert response.status_code == 400
        assert response.json()["error"] == "file_too_large"
        assert not list(store.list_keys())

    def test_the_filename_is_normalised_before_it_is_stored(
            self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        created = _upload(client, state,
                          filename="../../../etc/passwd\x00.csv")
        assert created.status_code == 200, created.text
        stored = created.json()["original_filename"]
        assert "/" not in stored and "\\" not in stored
        assert "\x00" not in stored
        assert ".." not in stored


# ===========================================================================
# 3. The seam between the two systems
# ===========================================================================

class TestDatabaseAndObjectConsistency:

    def test_a_storage_failure_after_the_row_leaves_it_unavailable(
            self, registry, store):
        """Not AVAILABLE, and therefore not downloadable."""
        _app, client, state = registry
        _login(client, "att_researcher")
        store.fail_next_put = "storage_unavailable"

        response = _upload(client, state)
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "attachment_storage_failed"

        # The row survives in PENDING_UPLOAD, which is what makes the orphan
        # findable — an object with no row would be invisible forever.
        row = _attachment_row(_app, _latest_attachment_id(_app))
        assert row.state is AttachmentState.PENDING_UPLOAD
        assert row.last_error_code == "storage_unavailable"

    def test_an_incomplete_upload_cannot_be_downloaded(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        store.fail_next_put = "storage_unavailable"
        _upload(client, state)

        attachment_id = _latest_attachment_id(_app)
        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "attachment_incomplete"

    def test_a_vanished_object_marks_the_row_missing(self, registry, store):
        """A lifecycle rule ate it. The next reader gets an honest error."""
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]
        row = _attachment_row(_app, attachment_id)
        store.vanish(row.storage_key)

        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "attachment_missing"

        assert _attachment_row(_app, attachment_id).state is (
            AttachmentState.MISSING)

    def test_a_storage_outage_does_not_mark_anything_missing(
            self, registry, store):
        """An outage is not a lost object, and must not be recorded as one.

        Marking every attachment MISSING during a ten-minute incident would
        turn it into a data-integrity alarm, and somebody would then have to
        prove afterwards that nothing was actually lost.
        """
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        store.fail_next_get = "storage_unavailable"
        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 400
        assert response.json()["error"] == "attachment_unavailable"

        assert _attachment_row(_app, attachment_id).state is (
            AttachmentState.AVAILABLE)

        # Positive control: it downloads once the store is back.
        assert client.get(
            f"{VALIDATION}/attachments/{attachment_id}").status_code == 200

    def test_corrupted_bytes_are_refused_rather_than_served(
            self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]
        row = _attachment_row(_app, attachment_id)
        store.corrupt(row.storage_key)

        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "attachment_corrupt"

    def test_a_failed_delete_leaves_a_retryable_tombstone(
            self, registry, store):
        """Never "deleted" while the bytes are still there."""
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]
        store.fail_next_delete = "storage_delete_failed"

        response = client.delete(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "attachment_delete_failed"

        row = _attachment_row(_app, attachment_id)
        assert row.state is AttachmentState.DELETE_PENDING
        assert row.delete_attempts == 1
        assert row.last_error_code == "storage_delete_failed"

        # Retrying succeeds, and only then is it deleted.
        retried = client.delete(f"{VALIDATION}/attachments/{attachment_id}")
        assert retried.status_code == 200, retried.text
        assert _attachment_row(_app, attachment_id).state is (
            AttachmentState.DELETED)

    def test_a_deleted_attachment_cannot_be_downloaded(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]
        assert client.delete(
            f"{VALIDATION}/attachments/{attachment_id}").status_code == 200

        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 400, response.text
        assert response.json()["error"] == "attachment_deleted"

    def test_deletion_keeps_the_metadata_and_the_audit_trail(
            self, registry, store):
        """An experiment run against a file is still an experiment that ran."""
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]
        client.delete(f"{VALIDATION}/attachments/{attachment_id}")

        row = _attachment_row(_app, attachment_id)
        assert row is not None, "the row must survive the bytes"
        assert row.original_filename == "run.csv"
        assert row.checksum_sha256 == CSV_DIGEST
        assert row.content_removed_at is not None

    def test_two_uploads_of_the_same_file_do_not_share_an_object(
            self, registry, store):
        """What makes a retried upload safe rather than an overwrite."""
        _app, client, state = registry
        _login(client, "att_researcher")
        first = _upload(client, state).json()["id"]
        second = _upload(client, state).json()["id"]

        first_key = _attachment_row(_app, first).storage_key
        second_key = _attachment_row(_app, second).storage_key
        assert first_key != second_key

        # Deleting one leaves the other downloadable.
        client.delete(f"{VALIDATION}/attachments/{first}")
        assert client.get(
            f"{VALIDATION}/attachments/{second}").status_code == 200


def _latest_attachment_id(app) -> int:
    from sqlalchemy import select

    from nanobio_studio.app.db.auth_session import get_auth_session
    from nanobio_studio.app.db.validation_models import ExperimentAttachment

    async def read():
        generator = app.dependency_overrides[get_auth_session]()
        session = await generator.__anext__()
        try:
            return (await session.execute(
                select(ExperimentAttachment.id)
                .order_by(ExperimentAttachment.id.desc()).limit(1)
            )).scalars().first()
        finally:
            await generator.aclose()

    return run_async(read())


# ===========================================================================
# 4. Authorization, re-asserted through the new layer
# ===========================================================================

class TestAuthorizationThroughStorage:

    def test_a_foreign_organization_gets_the_same_404_as_an_absent_record(
            self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        _login(client, "other_researcher")
        foreign = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        absent = client.get(f"{VALIDATION}/attachments/99999999")
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()

    def test_walking_the_identifier_space_finds_nothing(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        _upload(client, state)

        _login(client, "unaffiliated")
        for attachment_id in range(1, 30):
            response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
            assert response.status_code == 404, attachment_id
            assert b"time_s" not in response.content

    def test_possessing_the_object_key_grants_nothing(self, registry, store):
        """The key is not a credential, and this is what says so.

        A caller who somehow learns a key — from a log, a bucket listing, a
        screenshot — still has to go through the API, and the API still asks
        the policy. There is no route anywhere that takes a key.
        """
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]
        key = _attachment_row(_app, attachment_id).storage_key
        assert store.exists(key), "the object genuinely exists"

        _login(client, "other_researcher")
        for path in (f"{VALIDATION}/attachments/{key}",
                     f"{VALIDATION}/attachments/{attachment_id}"):
            response = client.get(path)
            assert response.status_code in (404, 422), path
            assert b"time_s" not in response.content

    def test_a_cro_with_downloads_withheld_is_refused_over_http(
            self, registry, store):
        """The defect the attachment walkthrough found, pinned.

        An external contract laboratory whose membership carries
        ``may_download_attachments = false`` was served the file with HTTP 200,
        because the registry's own capability model predates organizations and
        nothing on the download path had ever asked the organization policy.

        This asserts the refusal **over HTTP**, against a real stored object,
        with an authorized colleague downloading the same object first. The
        service-level check that follows is kept as well: the two together say
        that the rule holds and that the route actually applies it.
        """
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        # Positive control first, so the refusal below is about the
        # restriction rather than about a broken attachment.
        authorized = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert authorized.status_code == 200, authorized.text
        assert authorized.content == CSV

        _login(client, "att_cro")
        refused = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert refused.status_code in (403, 404), refused.text
        assert b"time_s" not in refused.content, (
            "not one byte of the file may reach a collaborator whose "
            "agreement withholds downloads")

    def test_the_download_restriction_holds_at_the_policy_too(
            self, registry, store):
        """Defence in depth: the rule, independent of the route."""
        from nanobio_studio.app.organizations.policy import (
            Action, RecordFacts, may, resolve_context,
        )
        from sqlalchemy import select

        from nanobio_studio.app.db.auth_models import User
        from nanobio_studio.app.db.auth_session import get_auth_session

        _app, client, state = registry

        async def decide(username: str):
            generator = _app.dependency_overrides[get_auth_session]()
            session = await generator.__anext__()
            try:
                user = (await session.execute(
                    select(User).where(User.username == username)
                )).scalar_one()
                ctx = await resolve_context(session, user)
                return may(ctx, Action.DOWNLOAD_ATTACHMENT, RecordFacts(
                    organization_id=state["alpha_organization_id"]))
            finally:
                await generator.aclose()

        allowed, _reason = run_async(decide("att_researcher"))
        assert allowed is True, "positive control"

        refused, reason = run_async(decide("att_cro"))
        assert refused is False
        assert "downloading attachments" in reason

    def test_assigned_studies_scope_does_not_reach_every_attachment(
            self, registry, store):
        """The second half of the same finding.

        Attachment reachability was organization-wide: any member of the
        organization could resolve any attachment by identifier, whatever their
        scope. A member restricted to assigned studies now reaches attachments
        on those studies and no others — the same ``visible_study_ids``
        predicate the rest of the application uses.

        404 rather than 403, because an attachment on a study they cannot see
        is one whose existence they are not entitled to learn.
        """
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        assert client.get(
            f"{VALIDATION}/attachments/{attachment_id}").status_code == 200, (
            "positive control: an organization-wide member can reach it")

        # The CRO holds assigned-studies scope and no assignment on this study.
        _login(client, "att_cro")
        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 404, response.text
        assert b"time_s" not in response.content

    @pytest.mark.parametrize("who", ["att_suspended", "att_revoked",
                                     "att_expired"])
    def test_ended_access_cannot_download(self, registry, store, who):
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        _login(client, who)
        response = client.get(f"{VALIDATION}/attachments/{attachment_id}")
        assert response.status_code == 404, response.text
        assert b"time_s" not in response.content

    @pytest.mark.parametrize("who", ["att_suspended", "att_revoked",
                                     "att_expired", "unaffiliated"])
    def test_ended_access_cannot_upload(self, registry, store, who):
        _app, client, state = registry
        _login(client, who)
        response = _upload(client, state)
        assert response.status_code in (403, 404), response.text

    def test_a_foreign_version_cannot_receive_an_upload(self, registry, store):
        _app, client, state = registry
        _login(client, "att_researcher")
        response = _upload(client, state,
                           version_id=state["beta_version_id"])
        assert response.status_code == 404, response.text
        assert not [k for k in store.list_keys()
                    if f"/{state['beta_version_id']}/" in k]

    def test_a_stale_organization_header_hides_the_attachment(
            self, registry, store):
        """Selection narrows. It can never widen."""
        _app, client, state = registry
        _login(client, "att_researcher")
        attachment_id = _upload(client, state).json()["id"]

        response = client.get(
            f"{VALIDATION}/attachments/{attachment_id}",
            headers={ORGANIZATION_HEADER: str(state["beta_organization_id"])})
        assert response.status_code == 404, response.text
        assert b"time_s" not in response.content
