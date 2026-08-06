# NanoBio Studio setup

Install the backend dependencies from `nanobio_studio_backend/pyproject.toml`
and frontend dependencies with `npm ci` in `frontend/`.

Use `start.bat` on Windows or `./start.sh` on macOS/Linux for the canonical
production-shaped FastAPI/React launch. Development details are in
`docs/VERTICAL_SLICE.md`.

Do not deploy `Login.py`, either `biotech-lab-main` application, anything in
`requested/`, or any `pages/` directory. Those are preserved legacy Streamlit
sources and are blocked from execution.
