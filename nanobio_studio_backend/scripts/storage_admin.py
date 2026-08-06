"""Operator commands for attachment object storage.

Four subcommands, and the split between them is deliberate:

    python scripts/storage_admin.py status
    python scripts/storage_admin.py reconcile [--deep] [--mark-missing]
    python scripts/storage_admin.py migrate --local-root PATH [--apply]
                                            [--verify-only] [--manifest FILE]
    python scripts/storage_admin.py cleanup-local --local-root PATH
                                                  --manifest FILE --confirm

``reconcile`` and ``migrate`` report by default and change nothing. Every
destructive action needs an explicit flag *and* an explicit path, because the
two ways this tooling could ruin a deployment are deleting objects it did not
write and deleting local originals before the destination was verified — and
both are one careless default away.

Nothing here prints a filename, a clinical value or a credential. The manifest
carries identifiers, sizes, checksums and outcomes, which is what an operator
needs and all they need.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from nanobio_studio.app.core.config import settings  # noqa: E402
from nanobio_studio.app.storage import (  # noqa: E402
    describe_storage, object_store, storage_health,
)
from nanobio_studio.app.storage.migrate import (  # noqa: E402
    cleanup_local_originals, migrate_attachments,
)
from nanobio_studio.app.storage.reconcile import reconcile  # noqa: E402


async def _session():
    from nanobio_studio.app.db.auth_session import AuthSessionLocal, init_auth_db
    await init_auth_db()
    return AuthSessionLocal()


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


async def cmd_status(_args) -> int:
    health = storage_health()
    _print({
        "configuration": describe_storage(),
        "health": {"healthy": health.healthy, "driver": health.driver,
                   "bucket": health.bucket, "detail": health.detail,
                   "latency_ms": health.latency_ms},
    })
    return 0 if health.healthy else 1


async def cmd_reconcile(args) -> int:
    store = object_store()
    async with await _session() as session:
        report = await reconcile(session, store=store, deep=args.deep,
                                 mark_missing=args.mark_missing)
        if args.mark_missing:
            await session.commit()
    _print(report.to_dict())
    print(f"\n{report.summary()}")
    if not report.object_scan_available:
        print("note: objects-without-rows could not be checked against this "
              "store; that is an absence of evidence, not evidence of "
              "absence.")
    return 0 if report.healthy else 1


async def cmd_migrate(args) -> int:
    store = object_store()
    async with await _session() as session:
        report = await migrate_attachments(
            session, destination=store, local_root=args.local_root,
            dry_run=not args.apply, verify_only=args.verify_only,
            limit=args.limit)
        if args.apply and not args.verify_only:
            await session.commit()

    if args.manifest:
        written = report.write(args.manifest)
        print(f"manifest: {written}")
    _print(report.to_dict())
    print(f"\n{report.summary()}")
    if not args.apply and not args.verify_only:
        print("\nThis was a dry run. Re-run with --apply to migrate. Local "
              "originals are never deleted by this command.")
    return 0 if report.ok else 1


async def cmd_cleanup_local(args) -> int:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if not manifest.get("ok"):
        print("Refusing: the manifest records failures or checksum "
              "mismatches. Resolve them before removing any original.")
        return 2
    if manifest.get("dry_run") or manifest.get("verify_only"):
        print("Refusing: that manifest is from a dry run or a verification "
              "pass, so nothing was actually migrated.")
        return 2

    # Only entries the manifest says were migrated and verified.
    keys = [str(e.get("previous_key") or "")
            for e in manifest.get("entries", [])
            if e.get("outcome") == "migrated"]
    keys = [k for k in keys if k]
    if not keys:
        # The manifest deliberately does not carry the old keys, so this
        # command needs them supplied. Reported rather than guessed.
        print("The manifest records no previous keys to remove. Supply them "
              "explicitly with --key, after checking the destination.")
        for key in args.key or []:
            keys.append(key)
    if not keys:
        return 2

    result = cleanup_local_originals(local_root=args.local_root, keys=keys,
                                     confirm=args.confirm)
    _print(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show the storage configuration and health")

    reconcile_parser = sub.add_parser(
        "reconcile", help="Compare attachment rows against stored objects")
    reconcile_parser.add_argument(
        "--deep", action="store_true",
        help="Re-download every object and recompute its checksum")
    reconcile_parser.add_argument(
        "--mark-missing", action="store_true",
        help="Move AVAILABLE rows whose object is absent to MISSING. Never "
             "deletes anything.")

    migrate_parser = sub.add_parser(
        "migrate", help="Copy local attachment files into object storage")
    migrate_parser.add_argument("--local-root", required=True)
    migrate_parser.add_argument(
        "--apply", action="store_true",
        help="Actually migrate. Without this the command reports only.")
    migrate_parser.add_argument("--verify-only", action="store_true")
    migrate_parser.add_argument("--limit", type=int, default=None)
    migrate_parser.add_argument("--manifest", default=None)

    cleanup_parser = sub.add_parser(
        "cleanup-local",
        help="Delete local originals AFTER a verified migration")
    cleanup_parser.add_argument("--local-root", required=True)
    cleanup_parser.add_argument("--manifest", required=True)
    cleanup_parser.add_argument("--key", action="append", default=[])
    cleanup_parser.add_argument("--confirm", action="store_true")

    args = parser.parse_args()
    handlers = {
        "status": cmd_status,
        "reconcile": cmd_reconcile,
        "migrate": cmd_migrate,
        "cleanup-local": cmd_cleanup_local,
    }
    return asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    raise SystemExit(main())
