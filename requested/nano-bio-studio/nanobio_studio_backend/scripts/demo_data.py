"""Install, refresh or reset demonstration data.

Usage (Windows PowerShell, from the repository root)::

    # install or refresh the scenario templates -- safe to run repeatedly
    python nanobio_studio_backend\\scripts\\demo_data.py seed

    # show exactly what a reset WOULD remove, without deleting anything
    python nanobio_studio_backend\\scripts\\demo_data.py reset

    # actually delete demo-generated runs and projects
    python nanobio_studio_backend\\scripts\\demo_data.py reset --confirm

    # also drop the seeded templates (they can be re-seeded at any time)
    python nanobio_studio_backend\\scripts\\demo_data.py reset --confirm --include-templates

    # list the scenarios in the fixture set without touching the database
    python nanobio_studio_backend\\scripts\\demo_data.py list

Safety
------
``seed`` is idempotent: it keys on scenario slug, so a second run updates in
place and never duplicates.

``reset`` refuses to delete without ``--confirm``. Without it, the command prints
the exact scope -- how many demo records would go, and how many genuine user
records exist and will be untouched -- and exits. Every delete it issues is
filtered on ``origin = 'demo'``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "nanobio_studio_backend"
for _p in (str(_REPO_ROOT), str(_BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.db.auth_session import (  # noqa: E402
    AuthSessionLocal,
    close_auth_db,
    init_auth_db,
)
from nanobio_studio.app.demo.scenarios import (  # noqa: E402
    DEMO_FIXTURE_VERSION,
    SCENARIOS,
)
from nanobio_studio.app.demo.seeding import (  # noqa: E402
    reset_demo_data,
    seed_demo_templates,
)


def _print_scenarios() -> None:
    print(f"Fixture set: {DEMO_FIXTURE_VERSION}")
    print(f"{len(SCENARIOS)} scenarios\n")
    for s in SCENARIOS:
        kind = "technical" if s.technical else "indication"
        print(f"  {s.slug}")
        print(f"      {s.name}   [{kind}]")
        print(f"      {s.disease} / {s.subtype} / {s.drug}")
        print(f"      score runnable: {s.is_score_runnable}   "
              f"PK runnable: {s.is_pk_runnable}")
        print()


async def _seed() -> int:
    await init_auth_db()
    try:
        async with AuthSessionLocal() as session:
            report = await seed_demo_templates(session)
            await session.commit()
    finally:
        await close_auth_db()

    print(f"Fixture set: {report.fixture_version}")
    print(f"  created   : {len(report.created)}"
          + (f"  {report.created}" if report.created else ""))
    print(f"  updated   : {len(report.updated)}"
          + (f"  {report.updated}" if report.updated else ""))
    print(f"  unchanged : {len(report.unchanged)}")
    print(f"  total     : {report.total} templates installed")
    return 0


async def _reset(confirm: bool, include_templates: bool) -> int:
    await init_auth_db()
    try:
        async with AuthSessionLocal() as session:
            scope = await reset_demo_data(
                session, confirm=confirm, include_templates=include_templates)
            await session.commit()
    finally:
        await close_auth_db()

    verb = "DELETED" if scope.confirmed else "would delete"
    print(f"Scope of reset ({verb}):")
    print(f"  demo runs          : {scope.demo_runs}")
    print(f"  demo projects      : {scope.demo_projects}")
    print(f"  demo templates     : {scope.demo_templates}"
          + ("" if include_templates else "   (not included; pass "
                                          "--include-templates)"))
    print()
    print("Genuine user data (never touched by this command):")
    print(f"  user runs preserved     : {scope.user_runs_preserved}")
    print(f"  user projects preserved : {scope.user_projects_preserved}")

    if not scope.confirmed:
        print()
        print("Nothing was deleted. Re-run with --confirm to proceed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="demo_data",
        description="Install, refresh or reset NanoBio Studio demonstration data.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="install or refresh scenario templates "
                                "(idempotent)")
    sub.add_parser("list", help="list the fixture set without touching the "
                                "database")

    reset = sub.add_parser("reset", help="remove demo-generated records only")
    reset.add_argument("--confirm", action="store_true",
                       help="actually delete; without this only the scope is "
                            "reported")
    reset.add_argument("--include-templates", action="store_true",
                       help="also drop the seeded scenario templates")

    args = parser.parse_args(argv)

    if args.command == "list":
        _print_scenarios()
        return 0
    if args.command == "seed":
        return asyncio.run(_seed())
    return asyncio.run(_reset(args.confirm, args.include_templates))


if __name__ == "__main__":
    raise SystemExit(main())
