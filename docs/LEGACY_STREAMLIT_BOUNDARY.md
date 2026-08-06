# Legacy Streamlit boundary

## Canonical platform

Production is `nanobio_studio.app.vertical_slice:app` serving the built React
frontend and FastAPI API on port 8000. Streamlit and port 8501 are prohibited.

## Preserved archives

Legacy source, `users.db`, `sessions.json`, trial registries, saved designs,
and design-version tables remain on disk. They are not migrated or deleted.
Routed legacy files stop at an archival notice before importing authentication
or persistence code. All legacy and snapshot launchers fail closed.

## Limitations

There is no verified mapping from legacy usernames to production users or
organizations, from legacy trials to studies, or from username/design-name
versions to immutable candidates. Consequently legacy sign-in, simulation,
trial deletion, design restoration, and design mutation are unavailable.

Recovery or migration requires a separately reviewed, read-only extractor,
explicit identity and organization mapping, checksums, provenance, and import
through production services. Direct SQLite writes are never an acceptable
migration path.
