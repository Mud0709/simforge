"""Runtime configuration, read from environment variables prefixed ``SIMFORGE_``."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIMFORGE_", env_file=".env", extra="ignore")

    db_path: Path = _BACKEND_ROOT / "data" / "simforge.sqlite3"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
