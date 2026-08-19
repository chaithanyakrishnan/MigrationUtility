"""
app/api/routes/etl.py
ETL Generation endpoints — Screen 7.

POST /engagements/{id}/etl/generate     → run codegen, return artefact list
GET  /engagements/{id}/etl/artefacts    → list generated artefacts
GET  /engagements/{id}/etl/artefacts/{aid}          → download artefact content
GET  /engagements/{id}/etl/artefacts/{aid}/download → stream as file
DELETE /engagements/{id}/etl/artefacts  → clear artefacts (re-generate)
"""
from __future__ import annotations
import hashlib
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Engagement, ETLArtefact, MappingEntry, AuditEvent
from app.schemas.schemas import ETLArtefactOut, ETLGenerateRequest

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements/{engagement_id}/etl")

# In-memory generation state (replace with Redis/DB in production)
_gen_state: dict = {}


@router.post("/generate", status_code=202)
async def generate_etl(
    engagement_id: str = Path(...),
    payload: ETLGenerateRequest = ETLGenerateRequest(),
    ai_enhanced: bool = Query(True, description="Use Claude to improve generated scripts"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger ETL script generation for an engagement (P3.1).

    Reads all confirmed/auto_approved mappings and generates:
    - Per-domain Python extract scripts
    - Fixed-length format spec (if output_format=fixed)
    - Master run script with correct Frp load order
    - Mapping summary JSON

    Generation is async — the scripts are available via /etl/artefacts
    once complete (typically 10–30 seconds for a full engagement).
    """
    await _get_engagement(db, engagement_id)

    # Count approved mappings first
    result = await db.execute(
        select(MappingEntry).where(
            MappingEntry.engagement_id == engagement_id,
            MappingEntry.status.in_(["confirmed", "auto_approved"]),
        )
    )
    mappings = result.scalars().all()
    if not mappings:
        raise HTTPException(
            400,
            "No confirmed mappings found. Complete the AI Field Mapping step first."
        )

    _gen_state[engagement_id] = {
        "status": "running",
        "progress": 0,
        "message": f"Generating ETL scripts for {len(mappings)} mappings…",
        "artefact_count": 0,
    }

    background_tasks.add_task(
        _run_codegen,
        engagement_id=engagement_id,
        mapping_ids=[m.id for m in mappings],
        payload=payload,
        ai_enhanced=ai_enhanced,
    )

    return {
        "status": "running",
        "engagement_id": engagement_id,
        "mapping_count": len(mappings),
        "message": "ETL generation started — poll /etl/artefacts for results",
    }


@router.get("/generate/status")
async def get_generation_status(engagement_id: str = Path(...)):
    """Poll ETL generation progress."""
    state = _gen_state.get(engagement_id, {"status": "idle", "message": "No generation run"})
    return {"engagement_id": engagement_id, **state}


@router.get("/artefacts", response_model=list[ETLArtefactOut])
async def list_artefacts(
    engagement_id: str = Path(...),
    artefact_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all generated ETL artefacts for an engagement."""
    q = (
        select(ETLArtefact)
        .where(ETLArtefact.engagement_id == engagement_id)
        .order_by(ETLArtefact.generated_at)
    )
    if artefact_type:
        q = q.where(ETLArtefact.artefact_type == artefact_type)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/artefacts/{artefact_id}")
async def get_artefact_content(
    engagement_id: str = Path(...),
    artefact_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Get full content of a generated artefact (for in-browser display)."""
    artefact = await _get_artefact(db, engagement_id, artefact_id)
    # Content stored inline in DB for small artefacts; S3 for large ones
    if artefact.s3_key:
        # TODO: stream from S3
        return {"filename": artefact.filename, "content": "[stored in S3 — download via /download]"}
    return {
        "id": artefact.id,
        "filename": artefact.filename,
        "artefact_type": artefact.artefact_type,
        "generated_at": artefact.generated_at,
        "content": (artefact.generation_config or {}).get("content", ""),
    }


@router.get("/artefacts/{artefact_id}/download")
async def download_artefact(
    engagement_id: str = Path(...),
    artefact_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Stream a generated artefact as a downloadable file."""
    artefact = await _get_artefact(db, engagement_id, artefact_id)
    content = (artefact.generation_config or {}).get("content", "")
    return PlainTextResponse(
        content=content,
        headers={
            "Content-Disposition": f'attachment; filename="{artefact.filename}"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


@router.delete("/artefacts", status_code=204)
async def clear_artefacts(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Delete all artefacts for an engagement (before re-generating)."""
    await db.execute(
        delete(ETLArtefact).where(ETLArtefact.engagement_id == engagement_id)
    )
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="etl.artefacts_cleared",
        actor_type="sme",
        actor_id="dev@fis.com",
        summary="ETL artefacts cleared — ready for re-generation",
    ))
    await db.commit()


# ── Background generation ─────────────────────────────────────
async def _run_codegen(
    engagement_id: str,
    mapping_ids: list[str],
    payload: ETLGenerateRequest,
    ai_enhanced: bool,
) -> None:
    from app.db.session import get_session_factory
    from app.services.pipeline.codegen import etl_codegen, ETLGenerateConfig

    async with get_session_factory()() as db:
        try:
            state = _gen_state[engagement_id]

            # Load mappings
            state.update(progress=10, message="Loading approved mappings…")
            result = await db.execute(
                select(MappingEntry).where(MappingEntry.id.in_(mapping_ids))
            )
            mappings = result.scalars().all()

            # Build config
            config = ETLGenerateConfig(
                output_format=payload.output_format,
                extraction_mode=payload.extraction_mode,
                encoding=payload.encoding,
                null_indicator=payload.null_indicator,
                date_format=payload.date_format,
            )

            state.update(progress=20, message="Running ETL codegen (P3.1)…")

            # Generate artefacts
            artefacts = await etl_codegen.generate(
                engagement_id=engagement_id,
                mappings=mappings,
                config=config,
                ai_enhanced=ai_enhanced,
            )

            if not artefacts:
                state.update(status="failed", message="No artefacts generated — check mappings")
                return

            # Persist artefacts to DB
            state.update(progress=85, message=f"Saving {len(artefacts)} artefacts…")

            # Clear existing artefacts first
            await db.execute(
                delete(ETLArtefact).where(ETLArtefact.engagement_id == engagement_id)
            )

            for art in artefacts:
                db_art = ETLArtefact(
                    engagement_id=engagement_id,
                    artefact_type=art.artefact_type,
                    filename=art.filename,
                    content_hash=art.content_hash,
                    generated_by="dev@fis.com",
                    # Store content inline (use S3 in production for large scripts)
                    generation_config={
                        "content": art.content,
                        "output_format": payload.output_format,
                        "encoding": payload.encoding,
                        "extraction_mode": payload.extraction_mode,
                        "ai_enhanced": ai_enhanced,
                    },
                )
                db.add(db_art)

            db.add(AuditEvent(
                engagement_id=engagement_id,
                event_type="etl.generated",
                actor_type="ai" if ai_enhanced else "system",
                actor_id="system",
                summary=f"ETL scripts generated: {len(artefacts)} artefacts",
                detail={
                    "artefact_count": len(artefacts),
                    "filenames": [a.filename for a in artefacts],
                    "format": payload.output_format,
                    "ai_enhanced": ai_enhanced,
                },
            ))
            await db.commit()

            state.update(
                status="complete",
                progress=100,
                message=f"Done — {len(artefacts)} artefacts ready",
                artefact_count=len(artefacts),
            )
            logger.info("etl.codegen.complete",
                        engagement=engagement_id, artefacts=len(artefacts))

        except Exception as exc:
            logger.error("etl.codegen.error", engagement=engagement_id, error=str(exc))
            _gen_state.get(engagement_id, {}).update(
                status="failed", message=str(exc)
            )


async def _get_engagement(db: AsyncSession, eid: str) -> Engagement:
    r = await db.execute(select(Engagement).where(Engagement.id == eid))
    e = r.scalar_one_or_none()
    if not e:
        raise HTTPException(404, f"Engagement {eid} not found")
    return e


async def _get_artefact(
    db: AsyncSession, engagement_id: str, artefact_id: str
) -> ETLArtefact:
    r = await db.execute(
        select(ETLArtefact).where(
            ETLArtefact.id == artefact_id,
            ETLArtefact.engagement_id == engagement_id,
        )
    )
    art = r.scalar_one_or_none()
    if not art:
        raise HTTPException(404, "Artefact not found")
    return art
