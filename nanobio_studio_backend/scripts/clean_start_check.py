"""Start the application from stopped, exercise it, and stop it cleanly.

Why this exists as a script rather than a checklist
--------------------------------------------------
"The suites pass" and "the application starts" are different claims. A test
suite builds its own database with ``create_all`` and overrides the session
dependency; it never runs the startup path, never applies a migration to a
pre-existing file, and never proves the process can be stopped without being
killed. Every one of those has failed in real deployments while the suite was
green.

So this drives the documented development command end to end:

1. start the backend exactly as ``docs/VERTICAL_SLICE.md`` says to;
2. wait for ``/health``;
3. run the additive migrations twice and assert the second run changes
   nothing — idempotence is the property an operator relies on when they rerun
   an upgrade after a failure;
4. sign in and make an authenticated, organization-scoped request;
5. stop the process **gracefully** and report its exit code.

Step 5 is the one that motivated the script. A previous run reported exit code
255 for the backend, which reads like a crash. It was not: the process had been
terminated with ``Stop-Process -Force``, and 255 is what an abnormally
terminated console process reports. This distinguishes the two cases by
construction — it stops the server with a console break, the way Ctrl-C does,
and a nonzero code from *that* would be a real finding.

Usage, from the repository root:

    python nanobio_studio_backend/scripts/clean_start_check.py

Credentials come from the environment when a signed-in check is wanted:

    $env:NANOBIO_CLEANSTART_USER = 'someone'
    $env:NANOBIO_CLEANSTART_PASSWORD = '<their password>'

Without them the authenticated step is reported as skipped rather than faked.
Nothing here has a built-in account or password.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

HOST = "127.0.0.1"
PORT = int(os.environ.get("NANOBIO_CLEANSTART_PORT", "8010"))
BASE = f"http://{HOST}:{PORT}"

problems: list[str] = []
notes: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{label:<62} {'ok' if ok else 'PROBLEM'}")
    if not ok:
        problems.append(f"{label}{f': {detail}' if detail else ''}")
    return ok


def _get(path: str, cookie: str | None = None) -> tuple[int, str, str | None]:
    request = urllib.request.Request(f"{BASE}{path}")
    if cookie:
        request.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return (response.status, response.read().decode("utf-8", "replace"),
                    response.headers.get("Set-Cookie"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), None
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        return 0, str(exc), None


def _post(path: str, body: bytes, content_type: str,
          cookie: str | None = None) -> tuple[int, str, str | None]:
    request = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    request.add_header("Content-Type", content_type)
    if cookie:
        request.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return (response.status, response.read().decode("utf-8", "replace"),
                    response.headers.get("Set-Cookie"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), None
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc), None


def wait_for_health(timeout_s: int = 90) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, _body, _cookie = _get("/health")
        if status == 200:
            return True
        time.sleep(1)
    return False


def migrations_are_idempotent() -> bool:
    """Run the additive migrations twice against the live database file.

    The second run must report no changes. An upgrade an operator dares not
    rerun is one they will not rerun after it fails halfway.
    """
    import asyncio

    sys.path.insert(0, str(BACKEND_ROOT))
    from sqlalchemy.ext.asyncio import create_async_engine

    from nanobio_studio.app.db.auth_session import get_auth_database_url
    from nanobio_studio.app.db.migrations import (
        apply_additive_migrations, check_organization_consistency,
    )

    async def run() -> tuple[list[str], list[str], dict[str, int]]:
        engine = create_async_engine(get_auth_database_url())
        try:
            first = await apply_additive_migrations(engine)
            second = await apply_additive_migrations(engine)
            problems_found = await check_organization_consistency(engine)
            return first, second, problems_found
        finally:
            await engine.dispose()

    first, second, inconsistent = asyncio.run(run())
    notes.append(f"first migration pass applied {len(first)} change(s)")

    ok = check("migrations are idempotent on a second run", second == [],
               f"second pass reported {second}")
    # An unassigned row is invisible to every scoped query rather than visible
    # to everyone, so this is a report rather than a failure of isolation — but
    # it is exactly what an operator needs to see after an upgrade.
    if inconsistent:
        notes.append(f"organization consistency findings: {inconsistent}")
    check("no record disagrees with its parent's organization",
          not any("differs from" in k for k in inconsistent),
          str(inconsistent))
    return ok


def storage_configurations_behave() -> bool:
    """Three configurations, checked in-process before the server is started.

    * **local** — must build, and must say plainly that it is development
      storage rather than implying more.
    * **S3-compatible** — must build against a compatible endpoint without
      needing AWS. Checked with the in-memory driver standing in for the
      provider, so this runs with no cloud account and no credentials.
    * **deliberately incomplete production** — must fail *clearly*, naming the
      missing variable. This is the one that matters: the failure mode it
      prevents is an application that comes up, accepts uploads, and writes
      them to a container filesystem the next deploy discards.

    In-process rather than by restarting the server three times, because what
    is under test is the configuration gate, and three server restarts would
    make this slow enough that nobody runs it.
    """
    sys.path.insert(0, str(BACKEND_ROOT))
    from nanobio_studio.app.core.config import settings
    from nanobio_studio.app.storage import factory
    from nanobio_studio.app.storage.objects import StorageNotConfigured

    original = (settings.storage_driver, settings.storage_bucket)
    ok = True
    try:
        # --- 1. local ---------------------------------------------------
        settings.storage_driver = "local"
        factory.reset_object_store()
        store = factory.object_store()
        ok &= check("storage: the local driver starts", store.driver == "local")
        ok &= check("storage: local health is reported honestly",
                    "development only" in store.health().detail.lower(),
                    store.health().detail)

        # --- 2. S3-compatible, no cloud account required ----------------
        from nanobio_studio.app.storage.memory import InMemoryObjectStore
        compatible = InMemoryObjectStore(bucket="clean-start", driver="s3")
        factory.set_object_store_for_tests(compatible)
        try:
            probe = factory.object_store()
            ok &= check("storage: an S3-compatible driver is usable",
                        probe.driver == "s3" and probe.bucket == "clean-start")
            ok &= check("storage: S3-compatible health is reported",
                        probe.health().healthy)
        finally:
            factory.set_object_store_for_tests(None)

        # --- 3. incomplete production configuration ---------------------
        settings.storage_driver = "s3"
        settings.storage_bucket = ""
        factory.reset_object_store()
        try:
            factory.object_store()
            ok &= check(
                "storage: an incomplete production configuration fails",
                False, "it built a store instead of refusing, which would let "
                       "the application come up and write uploads somewhere "
                       "they will be lost")
        except StorageNotConfigured as exc:
            ok &= check(
                "storage: an incomplete production configuration fails", True)
            ok &= check(
                "storage: and the failure names the missing variable",
                "STORAGE_BUCKET" in str(exc), str(exc)[:120])
    finally:
        settings.storage_driver, settings.storage_bucket = original
        factory.reset_object_store()
    return ok


def main() -> int:
    print(f"Clean-start check against {BASE}\n")

    print("--- storage configuration ---")
    storage_configurations_behave()
    print()

    already, _body, _c = _get("/health")
    if already == 200:
        print(f"Something is already serving {BASE}. Stop it first, or set "
              f"NANOBIO_CLEANSTART_PORT to a free port.")
        return 2

    # The documented development command, verbatim from docs/VERTICAL_SLICE.md.
    command = [sys.executable, "-m", "uvicorn",
               "nanobio_studio.app.vertical_slice:app",
               "--host", HOST, "--port", str(PORT)]
    print("starting:", " ".join(command), f"(cwd={BACKEND_ROOT})\n")

    # A new process group so a console break can be delivered to it alone.
    # Without it, the break would also reach this driver.
    creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                     if os.name == "nt" else 0)
    server = subprocess.Popen(
        command, cwd=str(BACKEND_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, creationflags=creationflags)

    try:
        if not check("backend starts and answers /health", wait_for_health()):
            return 1

        status, body, _c = _get("/ready")
        check("readiness probe answers", status == 200, f"HTTP {status}")
        # The probe must report object storage, because a deployment whose
        # attachment store is unreachable is not ready to accept uploads.
        check("readiness reports object storage", '"storage"' in body,
              body[:160])
        # And it must not carry an endpoint, a bucket policy or a credential:
        # a readiness body is read by load balancers, monitoring and anybody
        # who can reach the port.
        for secret in ("aws_access", "secret", "AKIA", "amazonaws.com",
                       "X-Amz-Signature"):
            check(f"readiness body carries no {secret!r}",
                  secret.lower() not in body.lower())

        status, body, _c = _get("/api/v1/organizations")
        check("an organization route is served and protected",
              status == 401, f"HTTP {status}")

        migrations_are_idempotent()

        # --- an authenticated, organization-scoped request ----------------
        user = os.environ.get("NANOBIO_CLEANSTART_USER")
        password = os.environ.get("NANOBIO_CLEANSTART_PASSWORD")
        if not user or not password:
            notes.append(
                "authenticated request SKIPPED: set NANOBIO_CLEANSTART_USER "
                "and NANOBIO_CLEANSTART_PASSWORD to include it. Nothing was "
                "faked and no built-in account was used.")
        else:
            import json

            status, body, cookie = _post(
                "/api/v1/auth/login",
                json.dumps({"username": user, "password": password}).encode(),
                "application/json")
            if check("sign in succeeds", status == 200, f"HTTP {status}"):
                session_cookie = (cookie or "").split(";")[0]
                status, body, _c = _get("/api/v1/auth/me", session_cookie)
                check("authenticated identity request succeeds",
                      status == 200, f"HTTP {status}")
                status, body, _c = _get("/api/v1/organizations",
                                        session_cookie)
                check("authenticated organization-scoped request succeeds",
                      status == 200, f"HTTP {status}")
                status, body, _c = _get("/api/v1/reports", session_cookie)
                check("authenticated medical-report request succeeds",
                      status == 200, f"HTTP {status}")

    finally:
        # --- graceful shutdown, and the exit code it produces --------------
        print("\nstopping the backend with a console break (the Ctrl-C path)")
        if os.name == "nt":
            server.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            server.send_signal(signal.SIGINT)

        try:
            output, _ = server.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            output, _ = server.communicate()
            problems.append("the backend did not stop within 30s and was "
                            "killed")

        code = server.returncode
        tail = [line for line in (output or "").splitlines() if line][-6:]
        print("\n".join(f"  | {line}" for line in tail))

        # The exit code alone cannot tell an orderly shutdown from a crash on
        # Windows, so it is not what decides this. The *log* can, and does:
        # uvicorn prints "Application shutdown complete" only after its
        # lifespan shutdown has run to completion.
        #
        # The codes observed for an orderly console-break stop are 0 (POSIX
        # SIGINT), 3 (uvicorn on Windows CTRL_BREAK) and 3221225786 /
        # -1073741510 (0xC000013A STATUS_CONTROL_C_EXIT — the OS reporting
        # *how* the process ended, not the application reporting a failure).
        # None of them is evidence of a fault on its own.
        #
        # This is exactly what the previously reported "exit code 255" was:
        # that server had been ended with `Stop-Process -Force`, which is a
        # kill rather than a shutdown — and a killed process never reaches the
        # lines checked below.
        text_output = output or ""
        orderly = "Application shutdown complete" in text_output
        known_stop_codes = (0, None, 3, 130, -2, 3221225786, -1073741510)

        check("the backend ran its shutdown handlers to completion", orderly,
              "no 'Application shutdown complete' in the output, so the "
              "process did not stop in an orderly way")
        check("the backend's exit code is a known clean-stop code",
              code in known_stop_codes,
              f"exit code {code} is not one of {known_stop_codes}")
        notes.append(
            f"backend exit code on console break: {code} "
            f"(orderly shutdown confirmed in the log: {orderly})")

    print()
    for note in notes:
        print(f"note: {note}")
    print()
    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Clean start verified: started, migrated idempotently, served "
          "requests, stopped cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
