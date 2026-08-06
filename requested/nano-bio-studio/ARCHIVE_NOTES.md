# Archive notes — what is here, what was removed, and why

A **sanitized copy** of the working repository. The working tree was not
modified to produce it: everything was copied to a staging directory first, and
every change below applies only to the copies.

## Sanitized sample database (included)

`nanobio_SAMPLE_DEV_DATABASE_DO_NOT_USE_IN_PRODUCTION.db`

Built from the application's own SQLAlchemy models, so its schema cannot drift
from the code. Contents:

| Table | Rows | Note |
|---|---|---|
| `auth_users` | 3 | Fictional. Emails use the reserved `.invalid` TLD |
| `workspace_runs` | 1 | Synthetic inputs, status `BLOCKED`, **no result** |
| `auth_sessions`, `auth_audit_log`, `report_*` | **0** | Deliberately empty — these hold token hashes, IPs and clinical documents in the real database |

Every account uses the documented demo password **`NanoBioSampleOnly-2026!`**.
That password is published on purpose: it is worthless, unlocking nothing but
this throwaway file.

Regenerate it any time:

```
cd nanobio_studio_backend
python scripts/seed_sample_database.py
```

The single seeded study is `BLOCKED` with no result on purpose. Seeding a
"complete" run would put a fabricated scientific result in the archive.

## Removed entirely

| Item | Reason |
|---|---|
| `users.db`, `nanobio_auth_dev.db`, `trial_registry.db`, `biotech-lab-main/users.db` | Real databases. Between them: bcrypt password hashes, **148 session token hashes**, 213 auth-audit rows with IP addresses and user agents, 16 medical-report assessment records. Schema in `docs/DATABASE_SCHEMA.sql`; working substitute above |
| `frontend/.env` | Environment file. `.env.example` is included |
| `.claude/` | Local tooling config; a permission rule embedded a credential string |
| `.venv_new/` (both copies) | Python virtual environments — 37 MB of dependency cache |
| `node_modules/`, `__pycache__/`, `dist/`, `.vite/`, `.pytest_cache/` | Dependency caches and build outputs |
| `.git/` | Version-control history |
| `*.log`, `*.pyc`, `*.tmp` | Logs and transient files |

## Sanitized in place

Two real passwords existed in plaintext in source. Both now read from the
environment:

| File | Change |
|---|---|
| `create_admin.py`, `set_admin_password.py` (+ `biotech-lab-main/` copies) | hard-coded administrator password -> `os.environ.get("NANOBIO_ADMIN_PASSWORD")` |
| `db_init.py` | hard-coded default password, seeded automatically -> same |
| six `frontend/*-walkthrough.mjs` | hard-coded test-account password -> `process.env.NANOBIO_TEST_PASSWORD` |

The literal was also redacted from two security-audit documents
(`docs/CURRENT_APPLICATION_AUDIT.md`, `docs/SECURITY_CONTAINMENT_2026-07-30.md`)
that record it as a finding. **The findings are intact**; only the usable string
is gone.

> Those scripts are legacy. They write to `users.db`, which the current FastAPI
> backend never opens. The supported way to create an administrator is
> `nanobio_studio_backend/scripts/create_admin.py`, which has never contained a
> hard-coded password and refuses a `--password` flag because argv is visible to
> other processes.

## Not present in the repository

`LICENSE` and `app.py` do not exist, and nothing was invented to fill them.
A **`LICENSE.md`** does exist and is included — it is a copyright notice, not an
OSI licence.

There is no **Scientific Readiness Dashboard**. The nearest implemented feature
is the **Evidence & Validation** page (`frontend/src/pages/EvidencePage.tsx`,
route `/evidence`), which reports each module's verified build status. `/ready`
is an infrastructure readiness probe, unrelated.

## Quick start

```
# Backend
python -m venv .venv && .venv\Scriptsctivate       # Windows
pip install -r requirements.txt
cd nanobio_studio_backend
python -m uvicorn nanobio_studio.app.vertical_slice:app --host 127.0.0.1 --port 8000
python scripts/create_admin.py --username admin --email you@example.org
python scripts/demo_data.py seed

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Tables are created at startup; no migration step is needed for a fresh database.
Additive column migrations run automatically for an existing one
(`nanobio_studio/app/db/migrations.py`).

## Tests

```
python -m pytest tests -q          # backend: 1082 tests
cd frontend && npm test            # frontend: 534 tests
cd frontend && npm run typecheck   # TypeScript, strict
cd frontend && npm run build       # production build
```

Browser walkthroughs (need both servers running and Playwright installed):

```
cd frontend
npx playwright install chromium
node internal-structure-walkthrough.mjs http://127.0.0.1:8100
```
