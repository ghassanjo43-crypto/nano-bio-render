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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
