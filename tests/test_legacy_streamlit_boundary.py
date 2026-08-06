"""Fail-closed guards for the archived Streamlit application boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import make_isolated_auth_client


ROOT = Path(__file__).resolve().parents[1]
MARKER = "LEGACY_STREAMLIT_ARCHIVE_BOUNDARY"
MUTATION_TOKENS = ("sqlite3.connect", "save_design_to_db", "delete_trial(",
                   "restore_design_version", "initialize_database")


def _routed_legacy_files() -> list[Path]:
    files = [ROOT / "Login.py", ROOT / "biotech-lab-main" / "app.py",
             ROOT / "biotech-lab-main" / "App.py"]
    files.extend((ROOT / "pages").rglob("*.py"))
    files.extend((ROOT / "biotech-lab-main" / "pages").rglob("*.py"))
    for archive in ROOT.glob("requested*"):
        files.extend(archive.rglob("Login.py"))
        files.extend(archive.rglob("app.py"))
        files.extend(archive.rglob("App.py"))
        files.extend(p for p in archive.rglob("*.py") if "pages" in p.parts)
    return [p for p in files if "__pycache__" not in p.parts
            and "import streamlit as st" in p.read_text(
                encoding="utf-8", errors="replace")]


def test_canonical_fastapi_import_does_not_load_streamlit():
    code = (
        "import sys; "
        f"sys.path.insert(0, {str(ROOT / 'nanobio_studio_backend')!r}); "
        "import nanobio_studio.app.vertical_slice; "
        "raise SystemExit(1 if 'streamlit' in sys.modules else 0)")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            check=False, timeout=30)
    assert result.returncode == 0


def test_no_launcher_starts_streamlit_or_exposes_port_8501():
    launchers = [p for pattern in ("*.bat", "*.sh", "*.ps1")
                 for p in ROOT.rglob(pattern)
                 if not any(part in {".venv_new", "node_modules"}
                            for part in p.parts)]
    offenders = []
    for path in launchers:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if "streamlit run" in text or "-m streamlit" in text or "8501" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
    assert "nanobio_studio.app.vertical_slice:app" in (
        ROOT / "start.bat").read_text(encoding="utf-8")
    assert "nanobio_studio.app.vertical_slice:app" in (
        ROOT / "start.sh").read_text(encoding="utf-8")


def test_every_routed_legacy_file_stops_before_mutation_or_auth_imports():
    for path in _routed_legacy_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        marker = text.find(MARKER)
        assert marker >= 0, path
        for token in MUTATION_TOKENS:
            location = text.find(token)
            assert location < 0 or marker < location, (path, token)


def test_legacy_entry_point_exits_before_database_initialization(tmp_path):
    fake = tmp_path / "streamlit.py"
    fake.write_text(
        "def error(*a, **k): pass\n"
        "def stop(): return None\n", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run([sys.executable, str(ROOT / "Login.py")],
                            cwd=tmp_path, env=env, check=False, timeout=15)
    assert result.returncode != 0
    assert not (tmp_path / "users.db").exists()
    assert not (tmp_path / "sessions.json").exists()


def test_production_rejects_legacy_session_tokens(tmp_path):
    app, client, _factory = make_isolated_auth_client(tmp_path)
    try:
        with client:
            response = client.get(
                "/api/v1/auth/me?session_token=token_admin_1785000000",
                cookies={"session_token": "token_admin_1785000000"})
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
