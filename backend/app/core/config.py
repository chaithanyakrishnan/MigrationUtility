"""
app/core/config.py
Application settings — loaded once at startup from environment / .env file.
All components import from here; never read os.environ directly.

Compatible with Python 3.9+.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    # Default dev secret — MUST be overridden in production via .env
    app_secret_key: str = "dev-secret-change-this-in-production-32chars!!"
    app_cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Database ──────────────────────────────────────────────
    # Optional with a dev default so startup doesn't crash before .env is configured
    database_url: str = "postgresql://migrateiq:password@localhost:5432/migrateiq"
    redis_url: str = "redis://localhost:6379/0"

    # ── AI / LLM ──────────────────────────────────────────────
    # Empty default — AI features will be disabled until key is set
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 8192
    embedding_model: str = "all-mpnet-base-v2"

    # ── Schema understanding library ──────────────────────────
    # Persist + reuse parsed schema understanding across engagements.
    schema_library_enabled: bool = True

    # ── Auth ──────────────────────────────────────────────────
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    jwt_algorithm: str = "RS256"
    jwt_expiry_hours: int = 8

    # ── Storage ───────────────────────────────────────────────
    s3_bucket: str = "migrateiq-artefacts"
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # ── Git registry ──────────────────────────────────────────
    gitea_url: str = "http://localhost:3001"
    gitea_token: str = ""
    gitea_org: str = "migrateiq"

    # ── Airflow ───────────────────────────────────────────────
    airflow_api_url: str = "http://localhost:8080/api/v1"
    airflow_username: str = "admin"
    airflow_password: str = ""

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_url_async(self) -> str:
        """Return the database URL with asyncpg driver for SQLAlchemy async."""
        url = self.database_url
        url = url.replace("postgresql://", "postgresql+asyncpg://")
        url = url.replace("postgres://", "postgresql+asyncpg://")
        return url

    @property
    def ai_enabled(self) -> bool:
        """True only when an Anthropic API key is configured."""
        return bool(self.anthropic_api_key and self.anthropic_api_key.startswith("sk-"))


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Call once per process."""
    return Settings()
