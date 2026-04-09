"""Application configuration loaded from environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/hiresense",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-change-me-in-production")
    UPLOAD_DIR: Path = PROJECT_ROOT / os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    ENV: str = os.getenv("APP_ENV", "development")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
