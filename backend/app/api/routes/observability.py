"""
app/api/routes/observability.py
Observability dashboard feed — recent audit events + headline counts.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import AuditEvent, Engagement, ProjectMapping

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/observability")


@router.get("")
async def observability(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    """Recent audit activity plus a few real headline counts for the dashboard."""
    events = (await db.execute(
        select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(limit)
    )).scalars().all()

    project_count = (await db.execute(
        select(func.count(Engagement.id)).where(Engagement.status == "active")
    )).scalar() or 0
    mapping_count = (await db.execute(select(func.count(ProjectMapping.id)))).scalar() or 0
    approved_count = (await db.execute(
        select(func.count(ProjectMapping.id)).where(ProjectMapping.approved.is_(True))
    )).scalar() or 0

    return {
        "counts": {
            "active_projects": project_count,
            "mappings": mapping_count,
            "mappings_approved": approved_count,
            "audit_events": len(events),
        },
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "summary": e.summary,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
