"""Create the first administrator account, safely.

Design rules
------------
* The password is **never** hard-coded, never a command-line argument (argv is
  visible in process listings and shell history), and never printed.
* It is read from an interactive prompt with echo disabled, or from the
  ``NANOBIO_ADMIN_PASSWORD`` environment variable for automated provisioning.
* The script refuses weak passwords and refuses to overwrite an existing user
  unless ``--force-password-reset`` is given explicitly.
* It creates a user only in the **new** auth database. The legacy ``users.db``
  is never opened, read, or modified.

Usage (Windows PowerShell), from the repository root:

    cd D:\\Nano_bio_Studio_30-7-2026\\nanobio_studio_backend
    python scripts\\create_admin.py --username admin --email admin@example.org

    # non-interactive (CI / provisioning)
    $env:NANOBIO_ADMIN_PASSWORD = "<a long unique password>"
    python scripts\\create_admin.py --username admin --no-prompt
    Remove-Item Env:\\NANOBIO_ADMIN_PASSWORD
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from nanobio_studio.app.core.security import hash_password  # noqa: E402
from nanobio_studio.app.db.auth_models import AuthEvent, UserRole  # noqa: E402
from nanobio_studio.app.db.auth_session import (  # noqa: E402
    AuthSessionLocal,
    get_auth_database_url,
    init_auth_db,
)
from nanobio_studio.app.services.auth_service import (  # noqa: E402
    create_user,
    get_user_by_username,
    record_audit,
)

MIN_PASSWORD_LENGTH = 12


def _read_password(no_prompt: bool) -> str:
    env_password = os.environ.get("NANOBIO_ADMIN_PASSWORD")
    if env_password:
        return env_password
    if no_prompt:
        raise SystemExit(
            "ERROR: --no-prompt requires the NANOBIO_ADMIN_PASSWORD environment "
            "variable to be set."
        )
    first = getpass.getpass("New administrator password (input hidden): ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise SystemExit("ERROR: passwords did not match.")
    return first


def _validate(password: str) -> None:
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if password.lower() in {"password", "admin", "administrator", "nanobio",
                            "changeme", "admin1234", "password123"}:
        problems.append("must not be a common default")
    if password.strip() != password:
        problems.append("must not start or end with whitespace")
    if problems:
        raise SystemExit("ERROR: password rejected -- " + "; ".join(problems))


async def _run(args: argparse.Namespace) -> int:
    password = _read_password(args.no_prompt)
    _validate(password)

    await init_auth_db()

    async with AuthSessionLocal() as session:
        existing = await get_user_by_username(session, args.username)

        if existing and not args.force_password_reset:
            print(
                f"User {args.username!r} already exists (role="
                f"{existing.role.value}). No change made.\n"
                "Re-run with --force-password-reset to set a new password."
            )
            return 1

        if existing:
            existing.password_hash = hash_password(password)
            existing.role = UserRole.ADMIN
            existing.is_active = True
            await record_audit(session, AuthEvent.ADMIN_CREATED,
                               user_id=existing.id,
                               username_attempted=existing.username,
                               detail="password reset via create_admin script")
            await session.commit()
            print(f"Password reset for existing administrator {args.username!r}.")
            return 0

        user = await create_user(
            session,
            username=args.username,
            password=password,
            role=UserRole.ADMIN,
            email=args.email,
            full_name=args.full_name,
        )
        await record_audit(session, AuthEvent.ADMIN_CREATED, user_id=user.id,
                           username_attempted=user.username,
                           detail="initial administrator created")
        await session.commit()

    print(f"Administrator {args.username!r} created.")
    print(f"Database: {get_auth_database_url()}")
    print("The password was not printed and is not stored in plaintext anywhere.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or reset the first NanoBio Studio administrator.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", default=None)
    parser.add_argument("--full-name", default=None)
    parser.add_argument("--no-prompt", action="store_true",
                        help="Read the password from NANOBIO_ADMIN_PASSWORD.")
    parser.add_argument("--force-password-reset", action="store_true",
                        help="Reset the password if the user already exists.")
    # Deliberately NO --password flag: argv is visible to other processes.
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
