"""
Core configuration for NanoBio Studio backend.
Loads environment variables and provides application settings.
"""
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+psycopg://nanobio:nanobio@localhost:5432/nanobio_studio"

    # API
    api_title: str = "NanoBio Studio Backend API"
    api_version: str = "0.1.0"
    debug: bool = True
    log_level: str = "INFO"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"

    # Application
    app_name: str = "nanobio_studio"
    environment: str = "development"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8501", "*"]

    # --- Vertical slice (Phase 2) ------------------------------------------
    # Explicit CORS allow-list. Kept separate from `cors_origins` above, which
    # contains a "*" wildcard that is unsafe and is also ignored by browsers
    # when credentials are enabled.
    #
    # This is INERT in the intended deployment. The React dev server proxies
    # /api, /health and /ready to this backend (frontend/vite.config.ts), and
    # production serves the built SPA from this same app (`serve_frontend`
    # below), so in both cases the browser makes same-origin requests and CORS
    # never comes into play. The list exists only for a deployment that
    # deliberately splits the SPA and the API across origins -- which would also
    # require the session cookie to become `SameSite=None; Secure` over HTTPS.
    #
    # Override per-environment, e.g.
    #   $env:SLICE_CORS_ORIGINS = '["https://app.example.com"]'
    slice_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Same-origin frontend serving ---------------------------------------
    # When enabled, the built SPA is served from this application so that the
    # interface and the API share one origin.
    #
    # This is a correctness setting, not a packaging convenience. The session
    # cookie is `SameSite=Lax`: if the SPA is served from a different site than
    # the API, the browser accepts the cookie on the login response and then
    # refuses to send it on every subsequent request, signing the user out the
    # instant they sign in. Serving both from one origin removes the cross-site
    # request entirely and keeps the stronger `Lax` CSRF posture.
    #
    # Off by default so API-only development and the test suite are untouched.
    #   $env:SERVE_FRONTEND = "true"
    serve_frontend: bool = False

    #: Location of the Vite build output. Relative paths resolve against the
    #: repository root. Must be built first (`npm run build`).
    frontend_dist_path: str = "frontend/dist"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
