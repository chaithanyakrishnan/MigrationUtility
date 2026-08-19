"""
app/main.py
FastAPI application entry point for MigrateIQ backend.
"""
from __future__ import annotations
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import get_settings
from app.db.session import init_db
from app.api.routes import (
    debug,
    engagements,
    knowledge_base,
    project,
    observability,
    schema,
    mapping,
    session,
    health,
)
# Retired in the v5 KB architecture (recon/cutover + ETL codegen removed from the
# main flow). Modules kept on disk but no longer mounted:
#   from app.api.routes import etl, recon

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("migrateiq.startup", env=settings.app_env)
    await init_db()

    # One-time backfill: seed the schema library from already-parsed engagements
    # so understanding analysed before this feature shipped is remembered too.
    if settings.schema_library_enabled:
        try:
            from app.db.session import get_session_factory
            from app.services.schema.library import schema_library
            async with get_session_factory()() as db:
                await schema_library.backfill_from_existing(db)
        except Exception as exc:
            logger.warning("schema.library.backfill_skip reason=%s", exc)

    yield
    logger.info("migrateiq.shutdown")


app = FastAPI(
    title="MigrateIQ API",
    description="AI-first Relius → Frp pension data migration utility",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ── Middleware ────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(debug.router,       prefix=API_PREFIX, tags=["debug"])
app.include_router(health.router,       prefix=API_PREFIX, tags=["health"])
app.include_router(engagements.router,  prefix=API_PREFIX, tags=["engagements"])
app.include_router(knowledge_base.router, prefix=API_PREFIX, tags=["knowledge-bases"])
app.include_router(project.router,      prefix=API_PREFIX, tags=["project"])
app.include_router(observability.router, prefix=API_PREFIX, tags=["observability"])
app.include_router(schema.router,       prefix=API_PREFIX, tags=["schema"])
app.include_router(mapping.router,      prefix=API_PREFIX, tags=["mapping"])
app.include_router(session.router,      prefix=API_PREFIX, tags=["session"])
