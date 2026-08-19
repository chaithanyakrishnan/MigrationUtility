"""
app/api/routes/engagements.py
CRUD endpoints for migration engagements.
Each engagement is one Relius → Frp migration project.
"""
from __future__ import annotations
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Engagement, AuditEvent
from app.schemas.schemas import EngagementCreate, EngagementOut, EngagementStepUpdate

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements")

# TODO: replace with real auth dependency
def get_current_user() -> str:
    return "dev@fis.com"


@router.post("", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    payload: EngagementCreate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Create a new migration engagement (= New Project)."""
    engagement = Engagement(
        name=payload.name,
        client_name=payload.client_name,
        relius_version=payload.relius_version,
        frp_version=payload.frp_version,
        created_by=user,
    )
    db.add(engagement)
    await db.flush()

    # Audit
    db.add(AuditEvent(
        engagement_id=engagement.id,
        event_type="engagement.created",
        actor_type="sme",
        actor_id=user,
        summary=f"Engagement '{payload.name}' created for {payload.client_name}",
        detail={"name": payload.name, "client": payload.client_name},
    ))
    await db.commit()
    await db.refresh(engagement)

    logger.info("engagement.created", id=engagement.id, name=engagement.name)
    return engagement


@router.get("", response_model=list[EngagementOut])
async def list_engagements(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List engagements, optionally filtered by status."""
    q = select(Engagement).order_by(desc(Engagement.created_at)).limit(limit)
    if status:
        q = q.where(Engagement.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{engagement_id}", response_model=EngagementOut)
async def get_engagement(
    engagement_id: str,
    db: AsyncSession = Depends(get_db),
):
    engagement = await _get_or_404(db, engagement_id)
    return engagement


@router.patch("/{engagement_id}/step", response_model=EngagementOut)
async def update_step(
    engagement_id: str,
    payload: EngagementStepUpdate,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """
    Update the current step and max_unlocked for an engagement.
    Called by the frontend when the user clicks Continue.
    """
    engagement = await _get_or_404(db, engagement_id)

    old_step = engagement.current_step
    engagement.current_step = payload.current_step
    engagement.max_unlocked = max(engagement.max_unlocked, payload.max_unlocked)

    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="engagement.step_advanced",
        actor_type="sme",
        actor_id=user,
        summary=f"Advanced from step {old_step} to {payload.current_step}",
        detail={"from": old_step, "to": payload.current_step, "max_unlocked": engagement.max_unlocked},
    ))
    await db.commit()
    await db.refresh(engagement)
    return engagement


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_engagement(
    engagement_id: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Archive (soft-delete) an engagement."""
    engagement = await _get_or_404(db, engagement_id)
    engagement.status = "archived"
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="engagement.archived",
        actor_type="sme",
        actor_id=user,
        summary="Engagement archived",
    ))
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────
async def _get_or_404(db: AsyncSession, engagement_id: str) -> Engagement:
    result = await db.execute(
        select(Engagement).where(Engagement.id == engagement_id)
    )
    engagement = result.scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail=f"Engagement {engagement_id} not found")
    return engagement
