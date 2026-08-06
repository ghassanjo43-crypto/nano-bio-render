#!/usr/bin/env sh
set -eu
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

command -v npm >/dev/null 2>&1 || { echo "ERROR: npm is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required." >&2; exit 1; }

echo "Building the canonical React frontend..."
(cd "$ROOT_DIR/frontend" && npm run build)

echo "Starting the canonical FastAPI/React platform on http://127.0.0.1:8000"
export SERVE_FRONTEND=true
cd "$ROOT_DIR/nanobio_studio_backend"
exec python3 -m uvicorn nanobio_studio.app.vertical_slice:app --host 0.0.0.0 --port 8000
