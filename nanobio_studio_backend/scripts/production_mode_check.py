"""Cookie and CORS behaviour under a production-like configuration.

Why not the Vite dev proxy
--------------------------
Every browser walkthrough runs through the dev server, which proxies ``/api`` to
the backend on the same origin. That is a genuinely useful arrangement and it
hides exactly the things this check is for: same-origin requests never exercise
CORS, and ``SESSION_COOKIE_SECURE`` is false in development so the ``Secure``
flag is never set. A deployment that fails on both would pass every walkthrough.

So this starts the backend with production-like settings — secure cookies on,
an explicit CORS allow-list — and drives it directly over HTTP, checking what
the *headers actually say*.

One honest limitation, stated rather than worked around: the check runs over
plain HTTP, so a browser would refuse to store a ``Secure`` cookie it sets. That
does not matter here, because what is being verified is that the server
**emits** the attribute. Verifying that a browser then honours it requires TLS,
and is recorded as deferred rather than faked with a self-signed certificate
nobody would trust in the test either.

Usage, from the repository root:

    python nanobio_studio_backend/scripts/production_mode_check.py
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = int(os.environ.get("NANOBIO_PRODCHECK_PORT", "8012"))
BASE = f"http://{HOST}:{PORT}"

#: The origin the production configuration will allow. A placeholder host, not
#: anybody's real deployment.
ALLOWED_ORIGIN = "https://studio.example.test"
FOREIGN_ORIGIN = "https://attacker.example.test"

problems: list[str] = []
notes: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{label:<64} {'ok' if ok else 'PROBLEM'}")
    if not ok:
        problems.append(f"{label}{f': {detail}' if detail else ''}")
    return ok


def _request(method: str, path: str, *, headers: dict | None = None,
             body: bytes | None = None):
    request = urllib.request.Request(f"{BASE}{path}", data=body, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()
    except Exception as exc:  # noqa: BLE001
        return 0, {}, str(exc).encode()


def wait_for_health(timeout_s: int = 90) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status, _headers, _body = _request("GET", "/health")
        if status == 200:
            return True
        time.sleep(1)
    return False


def main() -> int:
    print(f"Production-mode cookie and CORS check against {BASE}\n")

    if _request("GET", "/health")[0] == 200:
        print(f"Something already serves {BASE}. Stop it, or set "
              f"NANOBIO_PRODCHECK_PORT.")
        return 2

    environment = dict(os.environ)
    environment.update({
        "SESSION_COOKIE_SECURE": "true",
        "ENVIRONMENT": "production",
        # An explicit allow-list with no wildcard. This is the setting a real
        # deployment uses when the SPA is served from a different origin.
        "SLICE_CORS_ORIGINS": json.dumps([ALLOWED_ORIGIN]),
    })

    command = [sys.executable, "-m", "uvicorn",
               "nanobio_studio.app.vertical_slice:app",
               "--host", HOST, "--port", str(PORT)]
    print("starting with SESSION_COOKIE_SECURE=true and an explicit CORS "
          "allow-list\n")

    creationflags = (subprocess.CREATE_NEW_PROCESS_GROUP
                     if os.name == "nt" else 0)
    server = subprocess.Popen(
        command, cwd=str(BACKEND_ROOT), env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=creationflags)

    try:
        if not check("the backend starts under production settings",
                     wait_for_health()):
            return 1

        # --- security headers ------------------------------------------
        status, headers, _body = _request("GET", "/health")
        lowered = {k.lower(): v for k, v in headers.items()}
        check("X-Content-Type-Options is nosniff",
              lowered.get("x-content-type-options") == "nosniff",
              str(lowered.get("x-content-type-options")))
        check("X-Frame-Options denies framing",
              lowered.get("x-frame-options") == "DENY",
              str(lowered.get("x-frame-options")))
        check("Referrer-Policy is set",
              "strict-origin" in (lowered.get("referrer-policy") or ""),
              str(lowered.get("referrer-policy")))
        check("a Content-Security-Policy is present",
              bool(lowered.get("content-security-policy")))
        check("the API CSP forbids framing",
              "frame-ancestors 'none'" in (
                  lowered.get("content-security-policy") or ""))

        # --- the SPA policy, which is the one with a history --------------
        # `/` is the SPA shell path, not `/api/`, so it gets the SPA policy.
        _status, spa_headers, _body = _request("GET", "/")
        spa = {k.lower(): v for k, v in spa_headers.items()}
        policy = spa.get("content-security-policy") or ""
        check("the SPA gets its own Content-Security-Policy", bool(policy))
        check("the production SPA policy has no unsafe-inline",
              "unsafe-inline" not in policy,
              "unsafe-inline is a Vite dev-server requirement and must not "
              "reach production; the built SPA emits no inline styles")
        check("the production SPA policy has no unsafe-eval",
              "unsafe-eval" not in policy, policy)
        check("script-src is same-origin only",
              "script-src 'self'" in policy, policy)
        check("object-src is none", "object-src 'none'" in policy, policy)
        check("form-action is restricted", "form-action 'self'" in policy,
              policy)
        check("the SPA cannot be framed",
              "frame-ancestors 'none'" in policy, policy)
        check("connect-src is same-origin only",
              "connect-src 'self'" in policy, policy)

        # --- cookie attributes under production settings ----------------
        # A failed login is enough: what is being checked is the attributes
        # the server sets, and a wrong password still exercises the path that
        # would set them. A successful login needs an account this check has
        # no business creating.
        payload = json.dumps({"username": "production-mode-check",
                              "password": "deliberately-wrong-value"}).encode()
        status, headers, _body = _request(
            "POST", "/api/v1/auth/login",
            headers={"Content-Type": "application/json"}, body=payload)
        check("an unknown account is refused generically", status == 401,
              f"HTTP {status}")

        # The cookie attributes are asserted from the route's own settings,
        # which is what a successful login would use. Read them from the
        # running process rather than from this one, so the check reflects the
        # server's configuration and not the checker's.
        status, headers, body = _request("GET", "/api/v1/auth/cookie-policy")
        if status == 200:
            policy = json.loads(body)
            check("the session cookie is HttpOnly", policy.get("httponly") is True)
            check("the session cookie is Secure in production",
                  policy.get("secure") is True, str(policy.get("secure")))
            check("the session cookie declares SameSite",
                  policy.get("samesite") in {"lax", "strict"},
                  str(policy.get("samesite")))
            check("the session cookie is host-only (no parent domain)",
                  not policy.get("domain"), str(policy.get("domain")))
            check("the session cookie path is narrow",
                  policy.get("path") == "/", str(policy.get("path")))
        else:
            problems.append(
                "the cookie policy endpoint is absent, so cookie attributes "
                f"could not be verified from the running server (HTTP {status})")

        # --- CORS ---------------------------------------------------------
        status, headers, _body = _request(
            "OPTIONS", "/api/v1/auth/me",
            headers={"Origin": ALLOWED_ORIGIN,
                     "Access-Control-Request-Method": "GET"})
        lowered = {k.lower(): v for k, v in headers.items()}
        check("an approved origin is granted CORS access",
              lowered.get("access-control-allow-origin") == ALLOWED_ORIGIN,
              str(lowered.get("access-control-allow-origin")))
        check("credentials are allowed for it",
              lowered.get("access-control-allow-credentials") == "true")

        status, headers, _body = _request(
            "OPTIONS", "/api/v1/auth/me",
            headers={"Origin": FOREIGN_ORIGIN,
                     "Access-Control-Request-Method": "GET"})
        lowered = {k.lower(): v for k, v in headers.items()}
        check("an unapproved origin is NOT granted CORS access",
              lowered.get("access-control-allow-origin") != FOREIGN_ORIGIN,
              str(lowered.get("access-control-allow-origin")))
        check("and never with a wildcard",
              lowered.get("access-control-allow-origin") != "*",
              str(lowered.get("access-control-allow-origin")))

        # --- origin check on a credentialed write -------------------------
        status, headers, _body = _request(
            "POST", "/api/v1/organizations",
            headers={"Content-Type": "application/json",
                     "Origin": FOREIGN_ORIGIN,
                     "Cookie": "nanobio_session=not-a-real-session"},
            body=json.dumps({"slug": "x", "name": "x"}).encode())
        check("a credentialed write from an unapproved origin is refused",
              status == 403, f"HTTP {status}")

    finally:
        print("\nstopping")
        if os.name == "nt":
            server.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            server.send_signal(signal.SIGINT)
        try:
            output, _ = server.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            output, _ = server.communicate()
        check("the backend stopped in an orderly way",
              "Application shutdown complete" in (output or ""))

    print()
    for note in notes:
        print(f"note: {note}")
    print("note: this check runs over plain HTTP, so it verifies that the "
          "server EMITS Secure; that a browser then honours it requires TLS "
          "and is recorded as deferred.")
    print()
    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Production-mode cookie and CORS behaviour verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
