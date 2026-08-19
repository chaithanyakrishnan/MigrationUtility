"""
app/db/session.py
SQLAlchemy async session factory and DB initialisation.
Compatible with Python 3.9+.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_engine         = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url_async,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def _try_create_extension(ext_name: str) -> None:
    """
    Try to create a PostgreSQL extension in its own AUTOCOMMIT connection.
    A failure never poisons surrounding transactions.
    """
    try:
        async with get_engine().connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext_name}"))
    except Exception as exc:
        logger.warning("db.extension.skip name=%s reason=%s", ext_name, exc)


async def init_db() -> None:
    """
    Called once at startup (lifespan).

    1. Tries to enable pgvector and pg_trgm (isolated — failure is non-fatal).
    2. In development, calls create_all as a safety net so the app works
       even if the developer forgot to run 'alembic upgrade head'.
       In staging/production, migrations MUST be run explicitly.
    """
    await _try_create_extension("vector")
    await _try_create_extension("pg_trgm")

    settings = get_settings()
    if settings.app_env == "development":
        # Safety net: create any missing tables without touching existing ones.
        # This is idempotent — safe to run even after alembic migrations.
        try:
            from app.models.models import Base
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("db.create_all.ok")
        except Exception as exc:
            # Log but don't crash — tables may already exist from alembic
            logger.warning("db.create_all.skip reason=%s", exc)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
