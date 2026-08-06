# Authentication boundary

Production authentication is provided only by the FastAPI `/api/v1/auth/*`
session-cookie endpoints backed by the configured `AUTH_DATABASE_URL`.
Organization and study authorization are resolved by production policy code.

The preserved Streamlit `users.db`, `sessions.json`, query/session state, and
legacy RBAC helpers are not accepted by production services. They must not be
mounted, copied, or configured as the production authentication database.

See `docs/LEGACY_STREAMLIT_BOUNDARY.md` for archival limitations.
