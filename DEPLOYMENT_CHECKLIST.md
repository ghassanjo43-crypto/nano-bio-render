# Deployment checklist

- Build `frontend/` successfully.
- Launch `nanobio_studio.app.vertical_slice:app` with an ASGI server.
- Serve the generated React SPA through FastAPI on the same origin.
- Configure the production authentication database and required storage.
- Run readiness, authentication, organization-isolation, candidate-version,
  and legacy-boundary tests.
- Confirm no command, container, or hosting configuration exposes port 8501.
- Confirm no deployment command starts Streamlit or an archival source tree.

Legacy SQLite files and `sessions.json` are archives, not production inputs.
