# Application Shell, Authentication and Navigation

**Created:** 2026-07-30
**Slice:** Phase 2 — application shell around the verified scoring page.
**Status:** Implemented and verified end-to-end in a real browser.

> **Scientific positioning.** Every result the platform produces is a
> computational research-planning output: not experimentally validated, not
> clinically validated, not a regulatory approval prediction, not a diagnosis or
> treatment recommendation, and not a substitute for wet-lab testing.

---

## 1. Authentication architecture

```
Browser                    FastAPI                        Database
───────                    ───────                        ────────
POST /auth/login  ───────▶ authenticate()          ─────▶ auth_users (bcrypt hash)
                           • rate-limit check
                           • verify bcrypt
                           • create session       ─────▶ auth_sessions (SHA-256 of token)
                           • audit                ─────▶ auth_audit_log
       ◀─────────  Set-Cookie: nanobio_session=… ; HttpOnly; SameSite=Lax; Path=/

GET  /auth/me     ───────▶ resolve_session()      ─────▶ lookup by SHA-256(token)
                           • absolute expiry
                           • idle timeout
                           • slide last_activity
POST /auth/logout ───────▶ delete session row + clear cookie
```

| Control | Implementation |
|---|---|
| Password hashing | **bcrypt**, cost 12, stored as TEXT. Plaintext never stored, logged or returned. |
| Session transport | **HttpOnly** cookie, `SameSite=Lax`, `Path=/`, `Secure` via `SESSION_COOKIE_SECURE`. |
| Token format | `secrets.token_urlsafe(32)` — opaque and random. Only its **SHA-256 hash** is stored. |
| Tokens in URLs | **None.** Never in a query string, response body, `localStorage` or a JS-readable cookie. |
| Generic failures | Unknown username and wrong password return the identical message and status. |
| Timing | A dummy bcrypt verification runs for unknown usernames so timing does not reveal account existence. |
| Rate limiting | 5 failures per (username, IP) in 15 min → 15 min lockout, `429` + `Retry-After`. |
| Session expiry | 8 h absolute **and** 30 min idle; expired sessions are deleted and audited. |
| Audit logging | `login_success`, `login_failure`, `logout`, `session_expired`, `rate_limited`, `admin_created`. |
| Revocation | Server-side — logout deletes the row, so the cookie is instantly useless. |

### How this differs from the legacy scheme

| Legacy | Now |
|---|---|
| `token_{username}_{unix_seconds}` — forgeable | 256-bit random, unguessable |
| Token in the URL query string | HttpOnly cookie only |
| Plaintext tokens in `sessions.json` | SHA-256 hashes in the database |
| No rate limiting at all | Per-username + per-IP lockout |
| Audit keyed on `username` (renames orphan history) | Keyed on `user_id` |
| `password_hash` BLOB in one module, TEXT in another | Consistently TEXT |
| `admin`/`admin` printed on the login page | No credentials displayed anywhere |

---

## 2. Session design

* **Server-controlled.** The client holds an opaque token; all state lives in
  `auth_sessions`. Logout is genuine revocation, not just a cleared cookie.
* **Sliding window inside a hard cap.** `last_activity_at` refreshes on each
  authenticated request, but `expires_at` is fixed at login + 8 h.
* **Refresh survives.** The React app calls `GET /auth/me` on mount; the browser
  sends the cookie, so an ordinary refresh keeps the user signed in without any
  token being visible to JavaScript.
* **Expiry is handled, not ignored.** An expired or idle session returns `401`,
  the row is deleted, an audit entry is written, and the UI lands on `/login`.
* **`remember_me`** is accepted by the schema but **deliberately has no effect**.
  Extending session lifetime is a policy decision that needs review, so the field
  is documented as reserved rather than silently implemented.

---

## 3. Role permissions

| Role | Intended capability | Enforced today |
|---|---|---|
| `admin` | Platform administration and user management | Sees and can open `/admin`; `require_admin` dependency |
| `researcher` | Create designs, run simulations, save results, generate reports | Full access to operational modules |
| `viewer` | Read-only access to authorised projects and results | Same routes today; read-only distinctions arrive with persistence |

`researcher` is **new**. Legacy `student` accounts are **not** auto-converted —
that mapping is an explicit migration decision, not a silent rename.

Enforcement is layered: the backend `require_role` dependency is authoritative
(`403` on mismatch); the frontend `RoleRoute` and menu filtering are convenience,
not security.

---

## 4. Application routes

| Route | Access | Status |
|---|---|---|
| `/login` | Public; authenticated users are redirected to `/dashboard` | **Working** |
| `/dashboard` | Authenticated | **Working** |
| `/design` | Authenticated | **Working — real calculation** |
| `/simulation` | Authenticated | Placeholder |
| `/results` | Authenticated | Placeholder |
| `/compare` | Authenticated | Placeholder |
| `/assessments` | Authenticated | Placeholder |
| `/projects` | Authenticated | Placeholder |
| `/history` | Authenticated | Placeholder |
| `/reports` | Authenticated | Placeholder |
| `/ai-co-designer` | Authenticated | **Not operational** (deliberate) |
| `/admin` | **Admin only** | Placeholder |
| `/settings` | Authenticated | Placeholder |
| `/unauthorized` | Authenticated | **Working** |
| `*` | Authenticated | **Working** (not-found) |

Unauthenticated access to any protected route redirects to `/login` and
remembers the intended destination, so sign-in returns the user there.

### API routes

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health`, `GET /ready` | Public | Liveness |
| `POST /api/v1/auth/login` | Public | Sign in |
| `POST /api/v1/auth/logout` | Public (idempotent) | Sign out |
| `GET /api/v1/auth/me` | **Required** | Profile |
| `POST /api/v1/design/score` | **Required** | Design impact score |

---

## 5. Menu and module status

| Menu item | Status | What it will provide |
|---|---|---|
| Dashboard | **Available** | Platform status and quick actions |
| Nanoparticle Design | **Available** | Design impact score from the canonical engine |
| Run Simulation | Migration in progress | Two-compartment PK simulation |
| Results | Migration in progress | Detailed results with traceability |
| Compare Designs | Migration in progress | Side-by-side candidate comparison |
| Scientific Assessments | Migration in progress | Six assessment engines |
| Projects | Migration in progress | Grouping of designs and reports |
| Simulation History | Migration in progress | Reproducible run records |
| Reports | Migration in progress | PDF/CSV/JSON report generation |
| AI Co-Designer | **Not operational** | Multi-objective optimisation with traceable provenance |
| Administration *(admin)* | Migration in progress | Users, roles, audit review |
| Settings | Migration in progress | Preferences and configuration |

`shell/navigation.ts` is the single source of truth. The dashboard derives its
availability lists from it, so the two can never disagree.

**Placeholders show no data.** No scores, charts, tables, projects, activity or
AI output. The AI Co-Designer additionally explains why it is unavailable and
states that the removed placeholder candidates will not return.

---

## 6. Creating the first administrator

The password is never hard-coded, never passed on the command line (argv is
visible in process listings), and never printed. There is deliberately **no
`--password` flag**.

```powershell
cd D:\Nano_bio_Studio_30-7-2026\nanobio_studio_backend
python scripts\create_admin.py --username admin --email admin@example.org --full-name "Platform Administrator"
# prompts twice with hidden input
```

Non-interactive provisioning:

```powershell
$env:NANOBIO_ADMIN_PASSWORD = "<a long unique password>"
python scripts\create_admin.py --username admin --no-prompt
Remove-Item Env:\NANOBIO_ADMIN_PASSWORD
```

Reset an existing account's password:

```powershell
python scripts\create_admin.py --username admin --force-password-reset
```

Rejected automatically: anything under 12 characters, and common defaults such
as `admin`, `password`, `changeme`.

---

## 7. Local PowerShell startup

```powershell
# 1. Backend dependencies
cd D:\Nano_bio_Studio_30-7-2026
python -m pip install fastapi "uvicorn[standard]" pydantic pydantic-settings httpx pytest sqlalchemy aiosqlite bcrypt

# 2. First administrator (once)
cd D:\Nano_bio_Studio_30-7-2026\nanobio_studio_backend
python scripts\create_admin.py --username admin --email admin@example.org

# 3. Start FastAPI
python -m uvicorn nanobio_studio.app.vertical_slice:app --host 127.0.0.1 --port 8000 --reload

# 4. Frontend dependencies (new terminal)
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm install
Copy-Item .env.example .env

# 5. Start React
npm run dev

# 6. Backend tests
cd D:\Nano_bio_Studio_30-7-2026
python -m pytest tests -q
python -m pytest tests\test_auth_api.py -q
python -m pytest tests -q -m "not known_defect"

# 7. Frontend checks
cd D:\Nano_bio_Studio_30-7-2026\frontend
npm run typecheck
npm test
npm run build
```

Open **http://127.0.0.1:5173**. Use `127.0.0.1`, not `localhost`: on Windows,
browsers resolve `localhost` to IPv6 `::1` first while both servers bind IPv4.

---

## 8. Test results

| Suite | Command | Result |
|---|---|---|
| Complete backend | `pytest tests -q` | **613 passed** |
| Authentication | `pytest tests\test_auth_api.py -q` | **34 passed** |
| Scoring API (now authenticated) | `pytest tests\test_vertical_slice_api.py -q` | **75 passed** |
| Golden vectors (scientific contract) | `pytest tests\golden_vectors -q` | **440 passed** |
| Frontend | `npm test` | **46 passed** |
| Frontend typecheck | `npm run typecheck` | **clean** |
| Frontend build | `npm run build` | **succeeded** — 196 kB JS / 62 kB gzip |

Backend auth coverage: login, generic failure messages, cookie flags, rate
limiting (including that a correct password is still blocked while locked out),
logout revocation, forged-cookie rejection, session expiry, role enforcement,
audit logging, password hashing/salting, and legacy-database isolation.

Frontend coverage: unauthenticated redirection, session restoration, expired
sessions, login success/failure/rate-limit/API-down states, logout, menu
visibility by role, admin route protection, navigation to the real scoring page,
the scoring workflow after login, absence of fabricated dashboard and AI data,
and absence of any `localStorage`/`sessionStorage` use.

### Verified in a real browser (Playwright)

```
login page shows admin / <redacted>:     false
rendered delivery score:          87.52     (canonical value)
AI page contains 94.2:            false
session survived hard refresh:    true
localStorage entries:             0
sessionStorage entries:           0
document.cookie (JS-readable):    ""        ← HttpOnly confirmed
logout returned to login:         true
```

---

## 9. Temporary components

| Item | Why temporary | Removed when |
|---|---|---|
| **SQLite auth database** | PostgreSQL is the target. A server is listening locally on 5432 but no usable development credentials were available, so the local default is SQLite **through the same SQLAlchemy async abstraction**. Only `AUTH_DATABASE_URL` changes. | PostgreSQL credentials are provisioned |
| `Base.metadata.create_all` at startup | Bootstrap convenience | Alembic migrations are wired up |
| Separate `vertical_slice.py` app | The existing `main.py` needs PostgreSQL and `loguru` at import | Backend skeleton consolidation |
| In-memory rate limiter | Per-process only | Redis or a database-backed counter |
| `sys.path` bootstrap in `design_scoring.py` | Scientific core still lives in the repo root | Step 3 ports the scientific core |
| Hand-written TypeScript types | No OpenAPI codegen yet | A later slice |

```powershell
# Point the auth database at PostgreSQL — no code changes required
$env:AUTH_DATABASE_URL = "postgresql+asyncpg://user:password@host:5432/nanobio_studio"
```

---

## 10. Security limitations to resolve before production

1. **`SESSION_COOKIE_SECURE` defaults to false** for local http. Must be `true`
   behind HTTPS, otherwise the cookie can travel in clear text.
2. **No CSRF token.** `SameSite=Lax` blocks cross-site POSTs, which is meaningful
   protection, but a defence-in-depth CSRF token should be added for
   state-changing routes.
3. **Rate limiting is per-process** — ineffective across multiple workers or
   instances.
4. **`X-Forwarded-For` is deliberately not trusted**, so behind a proxy every
   client appears to share one IP and per-IP limiting degrades. Wire a validated
   forwarded header at deployment.
5. **No account lockout persisted in the database** — a restart clears lockouts.
6. **No password-reset flow.** The UI states "coming soon"; an administrator must
   reset via the CLI.
7. **No multi-factor authentication.**
8. **No session listing or remote revocation** for users.
9. **SQLite is not suitable for production** — concurrency and durability.
10. **Alembic migrations are not yet wired**; schema changes are unmanaged.
11. **Legacy `users.db` accounts are not migrated.** Deliberate: an explicit,
     reviewed migration with a preview of every affected account is required.
12. **The development administrator password used during this slice is known to
     the build process and must be rotated** before any shared use.

---

## Appendix — files created

**Backend:** `app/core/security.py`, `app/db/auth_models.py`,
`app/db/auth_session.py`, `app/services/auth_service.py`, `app/api/deps_auth.py`,
`app/api/routes/auth.py`, `scripts/create_admin.py`
**Frontend:** `src/auth/{AuthContext.tsx,guards.tsx}`, `src/api/auth.ts`,
`src/shell/{AppShell.tsx,AppShell.css,navigation.ts}`,
`src/pages/{LoginPage.tsx,LoginPage.css,DashboardPage.tsx,DesignPage.tsx,ModulePlaceholder.tsx,NotFoundPage.tsx,UnauthorizedPage.tsx}`
**Tests:** `tests/test_auth_api.py`, `src/shell/AppShell.test.tsx`
**Docs:** this file, `docs/screenshots/`

**Materially changed:** `app/api/routes/design.py` (now authenticated),
`app/vertical_slice.py` (auth router, lifespan, credentialed CORS),
`app/core/config.py` (`slice_cors_origins`), `src/App.tsx` (routing),
`src/main.tsx` (router + provider), `src/api/client.ts` (`credentials: 'include'`),
`tests/conftest.py` (isolated auth fixture), `tests/test_vertical_slice_api.py`
(authenticated client).
