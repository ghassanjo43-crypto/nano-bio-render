@echo off
setlocal
cd /d "%~dp0"

where npm.cmd >nul 2>&1 || (echo ERROR: npm is required.& exit /b 1)
where python >nul 2>&1 || (echo ERROR: Python is required.& exit /b 1)

echo Building the canonical React frontend...
pushd frontend
call npm.cmd run build || (popd & exit /b 1)
popd

echo Starting the canonical FastAPI/React platform on http://127.0.0.1:8000
set "SERVE_FRONTEND=true"
pushd nanobio_studio_backend
python -m uvicorn nanobio_studio.app.vertical_slice:app --host 0.0.0.0 --port 8000
set EXIT_CODE=%ERRORLEVEL%
popd
exit /b %EXIT_CODE%
