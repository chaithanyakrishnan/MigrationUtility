"""
app/api/routes/session.py
Session / review persistence endpoints.

Covers everything that needs to survive page reload:
  - Domain review notes (Screen 2 Relius, Screen 4 Frp)
  - UDF definitions (Screen 6)
  - Control file registration (Screen 6)
  - Engagement-scoped user preferences
"""
from __future__ import annotations
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile, File, Form
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import (
    DomainReview, Engagement, AuditEvent, ControlFile, MappingEntry
)
from app.schemas.schemas import DomainReviewCreate, DomainReviewOut

logger = structlog.get_logger(__name__)
router = APIRouter()

# ── Domain Reviews ─────────────────────────────────────────────
@router.post("/engagements/{engagement_id}/reviews", response_model=DomainReviewOut, status_code=201)
async def save_domain_review(
    engagement_id: str = Path(...),
    payload: DomainReviewCreate = ...,
    db: AsyncSession = Depends(get_db),
):
    """Save (upsert) a domain review for Relius (side=src) or Frp (side=tgt)."""
    await _get_engagement(db, engagement_id)

    # Upsert: delete existing then insert
    await db.execute(
        delete(DomainReview).where(
            DomainReview.engagement_id == engagement_id,
            DomainReview.domain_id == payload.domain_id,
            DomainReview.side == (payload.side or "src"),
        )
    )
    review = DomainReview(
        engagement_id=engagement_id,
        domain_id=payload.domain_id,
        side=payload.side or "src",
        approved=payload.approved,
        field_edits=payload.field_edits or [],
        include_fields=payload.include_fields or [],
        exclude_fields=payload.exclude_fields or [],
        reviewed_by="dev@fis.com",
    )
    from datetime import datetime
    if payload.approved:
        review.reviewed_at = datetime.utcnow()

    db.add(review)
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="domain_review.saved",
        actor_type="sme",
        actor_id="dev@fis.com",
        summary=f"Domain '{payload.domain_id}' ({payload.side}) {'approved' if payload.approved else 'saved'}",
        detail={"domain_id": payload.domain_id, "side": payload.side, "approved": payload.approved},
    ))
    await db.commit()
    await db.refresh(review)

    # Auto-merge SME corrections into the cross-engagement library (best-effort).
    from app.core.config import get_settings
    if get_settings().schema_library_enabled and payload.field_edits:
        try:
            from app.services.schema.library import schema_library
            await schema_library.merge_field_edits(
                engagement_id, payload.side or "src", payload.field_edits, db
            )
        except Exception:
            logger.warning("domain_review.library_merge_failed", domain_id=payload.domain_id)

    return review


@router.get("/engagements/{engagement_id}/reviews", response_model=list[DomainReviewOut])
async def list_domain_reviews(
    engagement_id: str = Path(...),
    side: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all domain reviews for an engagement."""
    q = select(DomainReview).where(DomainReview.engagement_id == engagement_id)
    if side:
        q = q.where(DomainReview.side == side)
    result = await db.execute(q)
    return result.scalars().all()


@router.delete("/engagements/{engagement_id}/reviews/{domain_id}", status_code=204)
async def delete_domain_review(
    engagement_id: str = Path(...),
    domain_id: str = Path(...),
    side: str = "src",
    db: AsyncSession = Depends(get_db),
):
    """Remove a domain review (reset to unreviewed)."""
    await db.execute(
        delete(DomainReview).where(
            DomainReview.engagement_id == engagement_id,
            DomainReview.domain_id == domain_id,
            DomainReview.side == side,
        )
    )
    await db.commit()


# ── UDF Mappings ───────────────────────────────────────────────
@router.post("/engagements/{engagement_id}/udfs", status_code=201)
async def save_udf(
    engagement_id: str = Path(...),
    src_table: str = Form(...),
    src_field: str = Form(...),
    tgt_table: str = Form(...),
    tgt_field: str = Form(...),
    description: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Save a user-defined field mapping (UDF)."""
    await _get_engagement(db, engagement_id)

    entry = MappingEntry(
        engagement_id=engagement_id,
        domain_id="udf",
        src_table=src_table.upper(),
        src_field=src_field.upper(),
        src_display=f"{src_table}.{src_field}",
        tgt_table=tgt_table.upper(),
        tgt_field=tgt_field.upper(),
        tgt_display=f"{tgt_table} {tgt_field}",
        confidence=50,
        mapping_type="direct",
        is_udf=True,
        note=description,
        status="confirmed",
    )
    db.add(entry)
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="udf.saved",
        actor_type="sme",
        actor_id="dev@fis.com",
        summary=f"UDF mapping: {src_table}.{src_field} → {tgt_table}.{tgt_field}",
    ))
    await db.commit()
    await db.refresh(entry)
    return {"id": entry.id, "src_display": entry.src_display, "tgt_display": entry.tgt_display}


@router.get("/engagements/{engagement_id}/udfs")
async def list_udfs(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """List all UDF mappings for an engagement."""
    result = await db.execute(
        select(MappingEntry).where(
            MappingEntry.engagement_id == engagement_id,
            MappingEntry.is_udf == True,
        )
    )
    return result.scalars().all()


# ── Control Files ──────────────────────────────────────────────
@router.post("/engagements/{engagement_id}/control-files", status_code=201)
async def upload_control_file(
    engagement_id: str = Path(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload and register an Frp control file (.txt)."""
    await _get_engagement(db, engagement_id)

    content = await file.read()
    raw_text = content.decode("utf-8", errors="replace")
    lines = [l for l in raw_text.splitlines() if l.strip()]

    # Parse key=value pairs (skip comment lines starting with *)
    kv: dict = {}
    env_flags: list = []
    ENV_KEYWORDS = ["EXIT", "FOLDER", "TEMPLATE", "OMNISCRIPT", "BILLING", "PATH"]
    for line in lines:
        if line.strip().startswith("*"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            kv[k.strip()] = v.strip()
            if any(kw in k.upper() for kw in ENV_KEYWORDS):
                env_flags.append(k.strip())

    cf = ControlFile(
        engagement_id=engagement_id,
        filename=file.filename or "control_file.txt",
        file_type=_infer_cf_type(file.filename or ""),
        line_count=len(lines),
        parsed_kv=kv,
        env_specific_flags=env_flags,
        uploaded_by="dev@fis.com",
    )
    db.add(cf)
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="control_file.uploaded",
        actor_type="sme",
        actor_id="dev@fis.com",
        summary=f"Control file '{file.filename}' uploaded — {len(lines)} lines, {len(kv)} key-value pairs",
        detail={"filename": file.filename, "lines": len(lines), "env_flags": env_flags},
    ))
    await db.commit()
    await db.refresh(cf)
    return {
        "id": cf.id,
        "filename": cf.filename,
        "file_type": cf.file_type,
        "line_count": cf.line_count,
        "kv_count": len(kv),
        "env_specific_flags": env_flags,
    }


@router.get("/engagements/{engagement_id}/control-files")
async def list_control_files(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """List all registered control files for an engagement."""
    result = await db.execute(
        select(ControlFile).where(ControlFile.engagement_id == engagement_id)
        .order_by(ControlFile.uploaded_at)
    )
    files = result.scalars().all()
    return [
        {
            "id": cf.id,
            "filename": cf.filename,
            "file_type": cf.file_type,
            "line_count": cf.line_count,
            "kv_count": len(cf.parsed_kv or {}),
            "env_specific_flags": cf.env_specific_flags or [],
            "uploaded_at": cf.uploaded_at,
        }
        for cf in files
    ]


@router.delete("/engagements/{engagement_id}/control-files/{file_id}", status_code=204)
async def delete_control_file(
    engagement_id: str = Path(...),
    file_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Remove a control file registration."""
    await db.execute(
        delete(ControlFile).where(
            ControlFile.id == file_id,
            ControlFile.engagement_id == engagement_id,
        )
    )
    await db.commit()


# ── Constants registry initialisation ────────────────────────
@router.post("/engagements/{engagement_id}/constants/seed", status_code=201)
async def seed_constants(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """
    P1.4 — Pre-populate the mapping registry with known Relius constants.
    These are always mapped at 100% confidence and never require SME review.
    Called automatically when AI mapping is triggered, also available manually.
    """
    from app.services.pipeline.constants import seed_constant_mappings
    count = await seed_constant_mappings(engagement_id, db)
    return {"seeded": count, "engagement_id": engagement_id}


# ── Helpers ────────────────────────────────────────────────────
def _infer_cf_type(filename: str) -> str:
    """Infer control file type from filename."""
    name = filename.lower()
    for t in ["vesting", "loan", "contribution", "deferral", "fee",
              "investment", "transfer", "auto_enroll", "auto_increase"]:
        if t in name:
            return f"Ct_{t.title()}"
    return "Ct_Unknown"


async def _get_engagement(db: AsyncSession, eid: str) -> Engagement:
    r = await db.execute(select(Engagement).where(Engagement.id == eid))
    e = r.scalar_one_or_none()
    if not e:
        raise HTTPException(404, f"Engagement {eid} not found")
    return e
