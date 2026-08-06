# Final production acceptance — 2026-08-06

## Decision

**NO-GO.** The canonical FastAPI/React application is suitable for continued
local and controlled acceptance work, but this workspace does not contain or
provide access to the production infrastructure needed to release it safely.

## Verified and passed

- Canonical entry point: `nanobio_studio.app.vertical_slice:app`.
- React production build and same-origin SPA serving.
- `/health`, `/openapi.json`, and SPA deep-link startup.
- 26 production-mode HTTP security, cookie, origin, and CORS assertions.
- Frontend suite: 790 tests in 193 suites.
- Browser acceptance after the shared-shell correction: 134 assertions at
  390 px and 153 assertions at 1500 px. No page-level horizontal overflow,
  clipped visible controls, or unnamed controls were reported.
- Disposable SQLite backup and restore: 33 tables, 26 rows, two candidate
  versions, `PRAGMA integrity_check=ok`, matching row/version inventories,
  byte-identical backup and restore, and two successful application restarts.
- Legacy Streamlit/authentication boundary group reached 175 passing tests;
  its one initial failure was caused by a pytest output tree being placed
  inside the source scanner's scope, not by a production route.
- The supported browser seeder refused a database whose name was not marked
  `candidate-browser`, as designed.

## Defects fixed during acceptance

1. Closed mobile/tablet navigation remained visible to accessibility and
   overflow inspection while translated off-screen. The shared sidebar now
   becomes invisible until the drawer is opened, and the toggle exposes
   `aria-expanded`.
2. The archive sanitation guard expected 12 walkthroughs although the three
   completed milestones raised the reviewed inventory to 15.
3. Root launchers built the SPA but did not set `SERVE_FRONTEND=true`.
4. Root `requirements.txt` installed the archival Streamlit application. It
   now installs the canonical backend and its additional vertical-slice
   runtime dependencies; it contains no Streamlit dependency.

## Conditionally accepted

- `loguru` is declared by the backend package because retained
  pre-consolidation backend modules import it. The canonical vertical-slice
  entry point does not import it. A canonical install from the root manifest
  will install it; the current host environment was not created from that
  manifest and does not contain it.
- Local filesystem attachment storage is development-only. Its authorization,
  key validation, size controls, and reconciliation have automated coverage,
  but it is not acceptable production storage.
- SQLite proved migration initialization, persistence, backup, and restore in
  the disposable acceptance environment. It does not qualify PostgreSQL.

## Not tested

- Managed PostgreSQL migration, point-in-time recovery, failover, connection
  pooling, or rollback under production load.
- S3-compatible external storage, server-side encryption, lifecycle policy,
  replication, malware scanning, or a restore of database plus object store.
- SMTP invitation/account email delivery.
- TLS termination and a real browser's handling of the emitted `Secure`
  cookie; the production HTTP check verified the server attribute only.
- Docker, Render, Compose, Kubernetes, or another deployment platform. No such
  canonical configuration is present in this workspace.
- Clean dependency installation from an empty environment; package download
  access was not available for this acceptance run.
- Physical-device and assistive-technology testing, localization, translated
  layout, and external identity/provider integration.

## Blocking defects

1. Production configuration is not centrally fail-closed. `ENVIRONMENT=production`
   can still start with development defaults such as `DEBUG=true`, local
   storage, an insecure cookie, and an implicit local SQLite authentication
   database. Operators must not deploy until startup validation rejects these
   combinations.
2. No production deployment definition or infrastructure configuration exists
   to validate build, health check, database, object storage, TLS, secrets, or
   rollback behavior.
3. The complete backend suite and focused migration aggregate did not finish
   on this Windows host. The valid run cannot be claimed as passed; an earlier
   invalid run showed 1,439 passes before 990 temp-directory setup errors.
4. Production PostgreSQL, external object storage, SMTP delivery, and a
   combined database/object restore were not available.
5. Release metadata remains `0.1.0` and Alpha, with no immutable commit or
   build identifier. This directory is not a Git worktree.

## Warnings and technical debt

- Vite reports two JavaScript chunks above 500 kB after minification.
- Pydantic class-based `Config` and per-request TestClient cookies produce
  deprecation warnings.
- `pip check` reports an unrelated installed `ncpp-sim`/Plotly version conflict
  on this host.
- The checked-in backend `.env.example` contains obsolete defaults and a
  legacy `CORS_ORIGINS` example including port 8501; it must not be used as a
  production environment file.

## Recovery procedure and limitations

For SQLite-only disposable/local recovery, stop all application processes,
use SQLite's online backup API (or an application-consistent filesystem
snapshot), verify `PRAGMA integrity_check`, restore to a different path, point
`AUTH_DATABASE_URL` at that path, and start the canonical app twice to verify
idempotent initialization. Compare table row counts and candidate-version
identities/checksums before directing traffic.

This is not a production recovery plan. A release requires a tested managed
PostgreSQL backup/PITR procedure and a coordinated versioned object-store
restore. Database rows without their referenced attachment objects are not a
complete restoration.
