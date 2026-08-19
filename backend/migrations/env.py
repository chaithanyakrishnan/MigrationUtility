"""
Alembic env.py — sync migrations using psycopg2.
Alembic does not need an async engine. The app uses asyncpg at runtime,
but migrations run synchronously via psycopg2-binary.
"""
from __future__ import annotations
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Ensure 'app' package is importable ───────────────────────
# alembic is run from backend/, so we add backend/ to sys.path
# so that `from app.models.models import Base` resolves correctly.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ── Alembic config object ─────────────────────────────────────
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import models so autogenerate can detect schema ───────────
from app.models.models import Base  # noqa: E402
target_metadata = Base.metadata

# ── Override DB URL from .env if present ─────────────────────
# Reads DATABASE_URL from backend/.env so you don't have to edit alembic.ini
def _get_url() -> str:
    # Try environment variable first (set in .env or shell)
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url:
        # Alembic needs sync driver — swap asyncpg for psycopg2
        url = env_url.replace("postgresql+asyncpg://", "postgresql://")
        url = url.replace("postgres://", "postgresql://")
        return url

    # Fall back to .env file
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                raw = raw.replace("postgresql+asyncpg://", "postgresql://")
                raw = raw.replace("postgres://", "postgresql://")
                return raw

    # Fall back to alembic.ini value
    return config.get_main_option("sqlalchemy.url") or \
           "postgresql://migrateiq:password@localhost:5432/migrateiq"


# ── Migration runners ─────────────────────────────────────────
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB (standard usage)."""
    url = _get_url()

    # Build a sync engine using psycopg2
    connectable = engine_from_config(
        {"sqlalchemy.url": url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
