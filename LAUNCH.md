# NanoBio Studio launch

The only supported platform is React served by FastAPI.

## Production-shaped local launch

- Windows: `start.bat`
- macOS/Linux: `./start.sh`

Both build `frontend/` and start:

```text
python -m uvicorn nanobio_studio.app.vertical_slice:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`. FastAPI serves the built SPA and API on the
same origin.

## Development

Run FastAPI on port 8000 and `npm run dev` from `frontend/` on port 5173.
Vite proxies API and health requests to FastAPI.

## Legacy boundary

Port 8501 and Streamlit are not deployment surfaces. Legacy source and data
are preserved for audited offline recovery only. See
`docs/LEGACY_STREAMLIT_BOUNDARY.md`.
