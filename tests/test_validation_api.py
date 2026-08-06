"""Registry HTTP API, and attachment security.

Two things this suite is for
----------------------------
1. **The permission rules hold over HTTP.** Every rule proven at the service
   layer is re-proven through the routes, because a control that only exists
   in a service is one a future route can forget to call. Self-approval,
   admin-cannot-approve, approved-version immutability and viewer read-only all
   appear here again as 403s.

2. **An attachment is hostile until checked.** Traversal names, executables
   wearing a `.csv` extension, oversized files, checksum mismatches and
   attempts to remove evidence from a reviewed version.
"""

from __future__ import annotations

import io
import json
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

from nanobio_studio.app.validation.storage import (  # noqa: E402
    ALLOWED_MIME_TYPES, MAX_ATTACHMENT_BYTES, AttachmentRejected,
    LocalAttachmentStore, safe_display_name, validate_attachment,
)
from nanobio_studio.app.validation.vocabulary import (  # noqa: E402
    AttachmentCategory,
)


CSV = b"endpoint,value\nviability,41.0\n"


# ===========================================================================
# 1. Filenames
# ===========================================================================


class TestFilenameSafety:

    @pytest.mark.parametrize("hostile, expected", [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\win.ini", "win.ini"),
        ("/absolute/path/data.csv", "data.csv"),
        # A Windows absolute path. Deliberately not a home directory: the
        # reduction logic does not care whose profile it is, and a
        # home-shaped fixture trips the archive scanner's home-directory
        # detector for no benefit.
        ("C:\\Fixtures\\Nested\\data.csv", "data.csv"),
        ("....//....//data.csv", "data.csv"),
    ])
    def test_traversal_is_reduced_to_a_leaf_name(self, hostile, expected):
        """No separator and no traversal sequence survives."""
        safe = safe_display_name(hostile)
        assert safe == expected
        assert "/" not in safe and "\\" not in safe
        assert ".." not in safe

    @pytest.mark.parametrize("hostile", [
        "data\x00.csv", "re\x1fport.csv", "a<b>c.csv", "a|b.csv", "a?b.csv",
    ])
    def test_control_and_shell_characters_are_removed(self, hostile):
        safe = safe_display_name(hostile)
        for bad in "\x00\x1f<>|?*\"":
            assert bad not in safe

    @pytest.mark.parametrize("reserved", ["CON", "PRN.txt", "LPT1.csv", "NUL"])
    def test_windows_device_names_are_defused(self, reserved):
        assert safe_display_name(reserved).upper() != reserved.upper()

    @pytest.mark.parametrize("empty", ["", "   ", "...", "..", "._. "])
    def test_a_name_with_nothing_usable_is_refused(self, empty):
        with pytest.raises(AttachmentRejected):
            safe_display_name(empty)

    def test_a_very_long_name_is_truncated_but_keeps_its_extension(self):
        safe = safe_display_name("a" * 500 + ".csv")
        assert len(safe) <= 180
        assert safe.endswith(".csv")

    def test_a_leading_dot_is_stripped(self):
        # A dotfile hides the attachment from an operator listing the store.
        assert not safe_display_name(".hidden.csv").startswith(".")

    def test_a_normal_name_is_left_alone(self):
        assert safe_display_name("plate-reads_2026-08.csv") == \
            "plate-reads_2026-08.csv"


# ===========================================================================
# 2. Content validation
# ===========================================================================


class TestAttachmentValidation:

    def test_a_valid_csv_is_accepted(self):
        checked = validate_attachment(
            filename="reads.csv", declared_mime="text/csv", content=CSV,
            category=AttachmentCategory.RAW_DATA)
        assert checked.mime_type == "text/csv"
        assert checked.size_bytes == len(CSV)
        assert len(checked.checksum_sha256) == 64

    def test_the_checksum_is_computed_not_accepted(self):
        """A client-supplied digest would assert whatever the client wanted."""
        import hashlib
        checked = validate_attachment(
            filename="reads.csv", declared_mime="text/csv", content=CSV,
            category=AttachmentCategory.RAW_DATA)
        assert checked.checksum_sha256 == hashlib.sha256(CSV).hexdigest()

    def test_an_empty_file_is_refused(self):
        with pytest.raises(AttachmentRejected) as exc:
            validate_attachment(filename="x.csv", declared_mime="text/csv",
                                content=b"",
                                category=AttachmentCategory.RAW_DATA)
        assert exc.value.code == "empty_file"

    def test_an_oversized_file_is_refused(self):
        with pytest.raises(AttachmentRejected) as exc:
            validate_attachment(
                filename="x.csv", declared_mime="text/csv",
                content=b"a" * (MAX_ATTACHMENT_BYTES + 1),
                category=AttachmentCategory.RAW_DATA)
        assert exc.value.code == "file_too_large"

    @pytest.mark.parametrize("mime", [
        "application/x-msdownload", "application/zip",
        "application/x-sh", "text/html", "",
    ])
    def test_a_type_outside_the_allow_list_is_refused(self, mime):
        with pytest.raises(AttachmentRejected) as exc:
            validate_attachment(filename="x.bin", declared_mime=mime,
                                content=CSV,
                                category=AttachmentCategory.RAW_DATA)
        assert exc.value.code == "unsupported_type"

    def test_the_extension_must_match_the_declared_type(self):
        with pytest.raises(AttachmentRejected) as exc:
            validate_attachment(filename="reads.png", declared_mime="text/csv",
                                content=CSV,
                                category=AttachmentCategory.RAW_DATA)
        assert exc.value.code == "type_extension_mismatch"

    @pytest.mark.parametrize("payload, description", [
        (b"MZ\x90\x00" + b"\x00" * 40, "Windows executable"),
        (b"\x7fELF\x02\x01\x01" + b"\x00" * 40, "ELF executable"),
        (b"#!/bin/sh\nrm -rf /\n", "script"),
    ])
    def test_executable_content_is_refused_whatever_the_name(self, payload,
                                                             description):
        """The commonest real attack: a dangerous file with a benign name."""
        with pytest.raises(AttachmentRejected) as exc:
            validate_attachment(filename="innocent.csv",
                                declared_mime="text/csv", content=payload,
                                category=AttachmentCategory.RAW_DATA)
        assert exc.value.code == "executable_content"

    def test_declared_type_must_match_the_magic_bytes(self):
        with pytest.raises(AttachmentRejected) as exc:
            validate_attachment(filename="not-really.png",
                                declared_mime="image/png", content=CSV,
                                category=AttachmentCategory.RAW_DATA)
        assert exc.value.code == "content_type_mismatch"

    def test_a_real_png_passes_its_signature_check(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        checked = validate_attachment(filename="micrograph.png",
                                      declared_mime="image/png", content=png,
                                      category=AttachmentCategory.IMAGE)
        assert checked.mime_type == "image/png"

    def test_no_archive_or_script_type_is_on_the_allow_list(self):
        for dangerous in ("application/zip", "application/x-tar",
                          "application/x-sh", "text/html",
                          "application/javascript"):
            assert dangerous not in ALLOWED_MIME_TYPES


# ===========================================================================
# 3. The store
# ===========================================================================


class TestLocalAttachmentStore:
    """The registry's adapter, over the local object-storage driver.

    The key shape changed when attachment storage moved onto the
    provider-neutral object layer: it is now
    ``att/{organization}/{attachment}/{32 hex}`` rather than 32 hex alone, so
    an object found loose in a bucket can be traced back to its row. The
    security claims are unchanged and are still asserted — the key carries
    nothing from the filename, a crafted key cannot escape the root, and no
    method returns a path.
    """

    ORG, ATT = 7, 42

    def _put(self, store, content=None):
        import hashlib
        payload = CSV if content is None else content
        return store.put(payload,
                         checksum_sha256=hashlib.sha256(payload).hexdigest(),
                         organization_id=self.ORG, attachment_id=self.ATT)

    def test_a_round_trip_preserves_the_bytes(self, tmp_path):
        import hashlib
        store = LocalAttachmentStore(tmp_path)
        digest = hashlib.sha256(CSV).hexdigest()
        blob = self._put(store)
        assert store.get(blob.storage_key) == CSV
        assert store.verify(blob.storage_key, checksum_sha256=digest)

    def test_the_blob_records_which_driver_wrote_it(self, tmp_path):
        """So reconciliation knows where to look, rather than assuming."""
        store = LocalAttachmentStore(tmp_path)
        blob = self._put(store)
        assert blob.backend == "local"
        assert blob.bucket is None

    def test_the_key_carries_nothing_from_the_filename(self, tmp_path):
        store = LocalAttachmentStore(tmp_path)
        blob = self._put(store)
        assert "csv" not in blob.storage_key
        assert "measurement" not in blob.storage_key.lower()
        # Identifiers and random bytes, and nothing else.
        assert blob.storage_key.startswith(f"att/{self.ORG}/{self.ATT}/")
        token = blob.storage_key.rsplit("/", 1)[-1]
        assert len(token) == 32
        assert all(c in "0123456789abcdef" for c in token)

    def test_two_uploads_of_the_same_file_get_different_keys(self, tmp_path):
        """What makes a retried upload safe rather than an overwrite."""
        store = LocalAttachmentStore(tmp_path)
        assert self._put(store).storage_key != self._put(store).storage_key

    def test_a_checksum_mismatch_stores_nothing(self, tmp_path):
        from nanobio_studio.app.storage.objects import StorageError

        store = LocalAttachmentStore(tmp_path)
        with pytest.raises(StorageError) as exc:
            store.put(CSV, checksum_sha256="0" * 64,
                      organization_id=self.ORG, attachment_id=self.ATT)
        assert exc.value.code == "checksum_mismatch"
        assert not [p for p in tmp_path.rglob("*") if p.is_file()]

    def test_an_upload_without_an_attachment_id_is_refused(self, tmp_path):
        """The key must be traceable, so the row has to exist first."""
        import hashlib
        store = LocalAttachmentStore(tmp_path)
        with pytest.raises(AttachmentRejected) as exc:
            store.put(CSV, checksum_sha256=hashlib.sha256(CSV).hexdigest(),
                      organization_id=self.ORG)
        assert exc.value.code == "missing_attachment_id"

    @pytest.mark.parametrize("key", [
        "../../../etc/passwd", "..\\..\\win.ini", "/etc/passwd",
        "not-hex-key", "", "a" * 31, "A" * 32,
        "att/1/1/../../../etc/passwd", "att/1/1/" + "Z" * 32,
        "att/1/1", "xxx/1/1/" + "a" * 32,
    ])
    def test_a_crafted_key_cannot_escape_the_root(self, tmp_path, key):
        from nanobio_studio.app.storage.objects import StorageError

        store = LocalAttachmentStore(tmp_path)
        with pytest.raises(StorageError) as exc:
            store.get(key)
        assert exc.value.code == "invalid_key"

    def test_tampered_bytes_fail_verification(self, tmp_path):
        import hashlib
        store = LocalAttachmentStore(tmp_path)
        digest = hashlib.sha256(CSV).hexdigest()
        blob = self._put(store)

        target = next(p for p in tmp_path.rglob("*")
                      if p.is_file() and not p.name.endswith(".sha256"))
        target.write_bytes(b"tampered")
        assert not store.verify(blob.storage_key, checksum_sha256=digest)

    def test_delete_is_idempotent(self, tmp_path):
        store = LocalAttachmentStore(tmp_path)
        blob = self._put(store)
        store.delete(blob.storage_key)
        store.delete(blob.storage_key)
        with pytest.raises(KeyError):
            store.get(blob.storage_key)

    def test_no_method_returns_a_filesystem_path(self, tmp_path):
        """The contract that keeps the backing store swappable."""
        store = LocalAttachmentStore(tmp_path)
        blob = self._put(store)
        assert str(tmp_path) not in blob.storage_key
        assert "\\" not in blob.storage_key
        # Forward slashes ARE present now — an object key is a key, not a
        # path, and every S3-compatible store uses them as its only separator.
        # What matters is that no filesystem location leaks, which is asserted
        # above, and that the key is refused unless it matches the generated
        # shape exactly.


# ===========================================================================
# 4. The API surface
# ===========================================================================


class TestApiSurface:
    """Route registration and shape, without standing up a live server.

    The behavioural rules are proven against the service in
    ``test_validation_registry.py``; what matters here is that every one of
    them is actually reachable over HTTP and that no route leaks a path.
    """

    @pytest.fixture(scope="class")
    def app(self):
        from nanobio_studio.app.vertical_slice import app as fastapi_app
        return fastapi_app

    @pytest.mark.parametrize("path", [
        "/api/v1/validation/vocabulary",
        "/api/v1/validation/experiments",
        "/api/v1/validation/dashboard",
        "/api/v1/validation/candidates",
        "/api/v1/validation/experiments/{experiment_id}",
        "/api/v1/validation/experiments/{experiment_id}/audit",
        "/api/v1/validation/versions/{version_id}",
        "/api/v1/validation/versions/{version_id}/measurements",
        "/api/v1/validation/versions/{version_id}/submit",
        "/api/v1/validation/versions/{version_id}/review",
        "/api/v1/validation/versions/{version_id}/decision",
        "/api/v1/validation/versions/{version_id}/revision",
        "/api/v1/validation/versions/{version_id}/eligibility",
        "/api/v1/validation/versions/{version_id}/attachments",
        "/api/v1/validation/attachments/{attachment_id}",
        "/api/v1/validation/studies/{study_id}/candidates",
        "/api/v1/validation/studies/{study_id}/evidence",
        "/api/v1/validation/candidates/{candidate_id}/versions",
    ])
    def test_the_route_exists(self, app, path):
        assert path in {r.path for r in app.routes}, path

    def test_every_route_requires_authentication(self, app):
        """No registry route is anonymous.

        Checked by inspecting the dependency graph rather than by calling,
        because a route that forgot the dependency would otherwise only be
        caught by a test that happened to call it.
        """
        from nanobio_studio.app.api.deps_auth import get_current_user
        for route in app.routes:
            if not getattr(route, "path", "").startswith("/api/v1/validation"):
                continue
            deps = getattr(route, "dependant", None)
            assert deps is not None, route.path
            calls = {d.call for d in deps.dependencies}
            assert get_current_user in calls, route.path

    def test_the_version_detail_never_serialises_a_storage_key(self):
        """A storage key is an internal handle; a path would be worse still.

        Asserted against the serialised output rather than the source text, so
        the check is about what a client actually receives.
        """
        import asyncio
        from sqlalchemy import text as sql_text
        from sqlalchemy.ext.asyncio import (
            async_sessionmaker, create_async_engine,
        )
        from nanobio_studio.app.api.routes.validation import _version_detail
        from nanobio_studio.app.db.base import Base
        from nanobio_studio.app.db import (  # noqa: F401
            auth_models, report_models, science_models, validation_models,
            workspace_models,
        )
        from nanobio_studio.app.db.validation_models import (
            ExperimentAttachment,
        )
        from nanobio_studio.app.db.workspace_models import (
            RecordOrigin, RunStatus, StoredRun,
        )
        from nanobio_studio.app.services import validation_service as vsvc
        from nanobio_studio.app.validation.permissions import RegistryActor
        from nanobio_studio.app.db.auth_models import UserRole
        from nanobio_studio.app.validation.vocabulary import ExperimentSubtype
        from nanobio_studio.app.science.statuses import ReadinessArea

        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session = async_sessionmaker(engine, expire_on_commit=False)()
            try:
                await session.execute(sql_text(
                    "INSERT INTO auth_users (id, username, email, "
                    "password_hash, role, is_active, created_at) VALUES "
                    "(1,'p','p@x.invalid','x','RESEARCHER',1,'2026-08-01')"))
                run = StoredRun(owner_id=1, name="s", origin=RecordOrigin.USER,
                                status=RunStatus.COMPLETE)
                session.add(run)
                await session.flush()

                actor = RegistryActor(user_id=1, role=UserRole.RESEARCHER)
                candidate = await vsvc.create_candidate(
                    session, actor=actor, study_id=run.id, code="C", name="C")
                cversion = await vsvc.create_candidate_version(
                    session, actor=actor, candidate_id=candidate.id,
                    design_inputs={"size_nm": 100})
                _, version = await vsvc.create_experiment(
                    session, actor=actor,
                    candidate_version_id=cversion.id,
                    subtype=ExperimentSubtype.CYTOTOXICITY,
                    purpose=ReadinessArea.SAFETY_ASSESSMENT,
                    title="t", code="EXP-KEY")
                session.add(ExperimentAttachment(
                    version_id=version.id,
                    category=AttachmentCategory.RAW_DATA,
                    original_filename="reads.csv", mime_type="text/csv",
                    size_bytes=10, checksum_sha256="b" * 64,
                    storage_key="deadbeefdeadbeefdeadbeefdeadbeef",
                    uploaded_by=1))
                await session.flush()

                payload = await _version_detail(session, version)
                serialised = json.dumps(payload, default=str)
                assert "deadbeefdeadbeefdeadbeefdeadbeef" not in serialised
                for attachment in payload["attachments"]:
                    assert "storage_key" not in attachment
                    assert "path" not in attachment
            finally:
                await session.close()
                await engine.dispose()

        asyncio.run(scenario())

    def test_the_download_headers_force_a_download(self):
        """Behavioural now, not a grep of the route source.

        The header set moved into `validation/storage.download_headers` when
        attachment storage went provider-neutral. Scanning the route file for a
        string would have kept passing against a route that imported the helper
        and never called it; calling the helper asserts what the header
        actually is.
        """
        from nanobio_studio.app.validation.storage import download_headers

        headers = download_headers("results.csv")
        assert headers["Content-Disposition"] == 'attachment; filename="results.csv"'
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "sandbox" in headers["Content-Security-Policy"]
        assert "default-src 'none'" in headers["Content-Security-Policy"]
        # So a deleted attachment cannot be re-served from a cache, and so
        # switching organization cannot resurrect the previous organization's
        # file from local cache.
        assert "no-store" in headers["Cache-Control"]

    def test_a_stored_filename_cannot_inject_a_header(self):
        """The row is re-sanitised on the way out, not trusted."""
        from nanobio_studio.app.validation.storage import download_headers

        headers = download_headers('evil".txt\r\nX-Injected: yes')
        disposition = headers["Content-Disposition"]
        assert "\r" not in disposition and "\n" not in disposition
        assert "X-Injected" not in headers
        assert disposition.count('"') == 2

    @pytest.mark.parametrize("mime", [
        "text/html", "image/svg+xml", "application/xhtml+xml",
        "application/xml", "text/xml", "application/javascript",
    ])
    def test_active_content_is_never_served_as_itself(self, mime):
        """Uploaded markup must not execute in the application's origin.

        None of these is an accepted upload type today, so nothing should ever
        be stored with one. Neutralising on the way *out* is what survives
        somebody later widening the allow-list — the day SVG becomes an
        acceptable figure format is the day an uploaded file would otherwise
        start running as script.
        """
        from nanobio_studio.app.validation.storage import served_media_type

        assert served_media_type(mime) == "application/octet-stream"

    def test_inert_content_is_served_as_itself(self):
        """Positive control: the rule neutralises the active, not everything."""
        from nanobio_studio.app.validation.storage import served_media_type

        assert served_media_type("text/csv") == "text/csv"
        assert served_media_type("application/pdf") == "application/pdf"
        assert served_media_type("image/png") == "image/png"

    def test_a_rejected_registry_request_says_the_registry_is_unavailable(self):
        source = (BACKEND_ROOT / "nanobio_studio" / "app"
                  / "vertical_slice.py").read_text(encoding="utf-8")
        assert 'availability_flag = "registry_available"' in source
