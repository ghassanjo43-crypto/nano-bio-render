# Security Containment — 2026-07-30

**Scope:** Minimal, urgent containment applied alongside Phase 2 Step 0.
**Explicitly NOT in scope:** redesigning authentication. Token generation, password
hashing, rate limiting and password-reset flows are deferred to the Phase 4
migration, per instruction.

**Verification after all changes:** `authenticate('admin','admin')` →
`(True, 'admin')`; `authenticate('admin','wrongpass')` → `(False, None)`;
`python Login.py` exits 0; `/healthz` returns 200; **397/397 tests pass**.

---

## 1. Changes applied

### 1.1 Removed default credentials from the login page

`Login.py:126-130` printed the live admin username and password to **every**
visitor, before authentication:

```python
st.markdown("### Demo Account")
st.info("""
**Username:** admin
**Password:** admin
""")
```

Replaced with a research-use-only disclaimer (which also serves safety rules 10–11).

### 1.2 Removed the import-time `_reset_admin_session()` call

`auth.py:171` called `_reset_admin_session()` at module scope. Its own docstring
said *"Remove in production."* Every `import auth` rewrote the admin account's
`session_start` and `last_activity`, which (a) defeated the 30-minute inactivity
timeout for that account and (b) corrupted the audit trail with writes nobody
initiated.

The function is left **defined but uncalled**, so any developer workflow that
genuinely needs it can call it explicitly.

Verified: `session_start`/`last_activity` are byte-identical before and after
`import auth`. Pinned by the `RESOLVED.import_side_effect::…` golden vector, so
re-adding the call now fails the test suite.

### 1.3 Stopped transporting session tokens in URLs

This was the largest change. Tokens were both **written to** and **read from**
`st.query_params`, i.e. a bearer credential in the URL — leaking through browser
history, proxy and server logs, and `Referer` headers. Because tokens are
predictable (`token_{username}_{unix_seconds}` with `user_id=username`), the **read**
sites were the more serious half: anyone could authenticate as `admin` by supplying
`?session_token=token_admin_<timestamp>` and guessing a second-resolution timestamp.

| File | Site | Change |
|---|---|---|
| `Login.py:170` | write on login redirect | removed |
| `Login.py:73-81` | URL restore accepted a token | removed; stale values cleared |
| `components/sidebar_navigation.py:19` | write on Home | removed |
| `components/sidebar_navigation.py:61` | write on ML page nav | removed |
| `streamlit_auth.py:427-429` | `switch_page_with_token` wrote the token | removed |
| `streamlit_auth.py:334-338` | `require_login_with_persistence` read the token | removed |
| `pages/0_Disease_Selection.py:33-36` | URL restore | removed |
| `pages/1_Design_Parameters.py:113-116` | URL restore | removed |
| `pages/2_Run_Simulation.py:48-51` | URL restore | removed |

Verified: **0** URL writes and **0** URL reads of `session_token` remain in the root
application. Each former site now clears a stale `session_token` parameter rather
than honouring it.

`switch_page_with_token()` keeps its name so all existing call sites work unchanged;
it now simply calls `st.switch_page()`.

#### Accepted functional trade-off (please note)

`st.session_state` carries the token across `st.switch_page` **within** a browser
session, so **in-app navigation is unaffected**. What is lost is silent
re-authentication after a **hard browser refresh** or pasting a deep link: that now
correctly requires logging in again. This was the only thing the URL token bought,
and it bought it by putting a forgeable credential in the address bar.

Side effect: `restore_session_from_persistent()` is now imported but never called,
so `sessions.json` has **no consumer** — the stored tokens are inert. The unused
imports were left in place to keep this change small; they are harmless.

### 1.4 `.gitignore` — credential and user-data files

Added: `sessions.json`, `users.json`, `users.db`, `*.session.json`, `.venv_new/`,
`**/.venv_new/`.

`sessions.json` and `users.json` matched **no** previous pattern. `.venv_new/`
matched none either (only `.venv/`, `venv/`, `env/`, `ENV/` were listed), and two
such directories exist. `*.db` was already covered; `users.db` is now also named
explicitly per safety rule 7.

---

## 2. Rotation assessment (requested)

**Finding: this directory is not a git repository at all** — no `.git`, and
`git rev-parse` fails. Nothing has ever been committed, so there is **no
git-history exposure** of any credential or token. The `.gitignore` additions are
**preventive**, taking effect when you initialise a repository.

| Asset | Exposure | Rotation needed? |
|---|---|---|
| **`admin` / `admin` password** | Displayed on the login page to every visitor until today; still seeded by `db_init.py:49` | **YES — highest priority.** See §3.1 |
| **`sessions.json` — 21 tokens** | All 21 are for `admin` with role `admin`; all match the predictable pattern; were carried in URLs, so they may persist in browser history and any proxy logs | **YES, recommended** — but they are now *inert* (no consumer). See §3.2 |
| **`<redacted — see ARCHIVE_NOTES.md>`** in `create_admin.py:31`, `set_admin_password.py:7` | Hard-coded in source. Not committed (no repo), but present in plaintext on disk | **YES if that password is used anywhere real** |
| `users.json` (220 bytes, one `admin` entry) | On disk, now git-ignored | Review contents; rotate if it holds a credential |
| External API keys | **None exist** — no integration requires a key | N/A |
| `users.db` | Contains one bcrypt hash (`admin`) | Covered by the password rotation above |

Because the application has only ever run on `localhost` and holds a single account,
realistic exposure is low. The rotation recommendation is driven by the credential
being a *published default*, not by evidence of compromise.

---

## 3. Remaining risks NOT fixed — and why

These need your decision; I did not act unilaterally.

### 3.1 `db_init.py` still seeds `admin` / `admin` — top remaining risk

`db_init.py:49-59` creates an `admin` account with password `admin` on any database
without one, in **both** `users.db` and `biotech-lab-main/users.db`.

I did **not** remove this, because `admin` is currently the **only** account
(verified: 1 row in `users`). Removing the seed without first creating a replacement
administrator would lock you out. This is exactly the "do not perform destructive
account migration automatically" case.

**Recommended sequence, in your control:**

```powershell
# 1. Set a real password on the existing admin account.
python -c "import sys; sys.path.insert(0,'.'); from auth import reset_password; print(reset_password('admin', 'REPLACE-WITH-A-STRONG-PASSWORD'))"

# 2. Confirm the new password works and the old one does not.
python -c "import sys; sys.path.insert(0,'.'); from auth import authenticate; print('new:', authenticate('admin','REPLACE-WITH-A-STRONG-PASSWORD')); print('old:', authenticate('admin','admin'))"
```

Note the current policy accepts a 6-character password with one letter and one
digit (`auth.py:17-18`) — weak, and raised in Phase 4.

Only after step 1 succeeds should the `db_init.py` seeding be removed; say the word
and I will do it as a separate, reviewable change.

### 3.2 Purging the 21 inert session tokens

`sessions.json` no longer has a consumer, so these tokens cannot authenticate
anyone. Purging is still recommended hygiene, and it is **your** call because it is
data deletion:

```powershell
# Optional: keep a copy outside the repository first.
Move-Item sessions.json "$env:USERPROFILE\nanobio_sessions_backup_20260730.json"
# Or discard outright:
Remove-Item sessions.json
```

The file is recreated empty on next login. Effect: nothing, since the restore path
is already removed.

### 3.3 Predictable token generation — deliberately deferred

`streamlit_auth.py:73` still builds `token_{username}_{unix_seconds}`. The one-line
fix is `secrets.token_urlsafe(32)` (and `secrets` is *already imported* in
`auth.py`). I did not apply it because:

1. Removing URL transport already **neutralised the attack** — there is no longer any
   path that accepts an externally supplied token.
2. Changing the format invalidates existing sessions (a forced re-login), which is a
   rotation action for you to schedule.
3. You instructed no authentication redesign before the relevant migration phase.

Recommended for Phase 4, not now.

### 3.4 Still outstanding (unchanged, previously reported)

* **No rate limiting or lockout** on `authenticate()` — unlimited password attempts.
* **`auth.py` calls `init_db()` twice at module scope** (lines 88 and 1420) —
  DEFECT-D11; a newly found second call.
* **`design_persistence.py:568`** writes a 36 KB `nano_bio.db` on bare import —
  DEFECT-D11. This actually leaked into the repository root during Step 0 harness
  development; the artefact was inspected (0 rows) and removed.
* **`package-lock.json` is still git-ignored** (`.gitignore:73`). Harmful for the
  Phase 5 React frontend — lockfiles must be committed for reproducible Render
  builds. Left alone as it is outside containment scope; flagging for Phase 5.
* **`bcrypt` hash column type conflict** between `db_init.py` (`BLOB`) and `auth.py`
  (`TEXT`) — if the `TEXT` variant ever wins, `bcrypt.checkpw` raises and the error
  is swallowed, silently failing **all** logins. Phase 4.

---

## 4. Files changed

| File | Change |
|---|---|
| `Login.py` | Removed credential display; removed URL token write; removed URL token restore |
| `auth.py` | Removed import-time `_reset_admin_session()` call (function retained) |
| `streamlit_auth.py` | `switch_page_with_token` no longer writes to the URL; `require_login_with_persistence` no longer reads from it |
| `components/sidebar_navigation.py` | Removed 2 URL token writes |
| `pages/0_Disease_Selection.py` | Removed URL token restore |
| `pages/1_Design_Parameters.py` | Removed URL token restore |
| `pages/2_Run_Simulation.py` | Removed URL token restore |
| `.gitignore` | Added `sessions.json`, `users.json`, `users.db`, `*.session.json`, `.venv_new/` |

No file was deleted. No account or database was migrated. The legacy Streamlit
application remains fully available.
