"""
app/api/routes/mapping.py
AI Field Mapping endpoints — Screen 6.
"""
from __future__ import annotations
from typing import Optional
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Path, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Engagement, MappingEntry, SchemaFile, AuditEvent
from app.schemas.schemas import MappingEntryOut, MappingApproval, MappingRunRequest, MappingRunStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements/{engagement_id}/mapping")

_run_state: dict = {}


@router.post("/run", response_model=MappingRunStatus, status_code=status.HTTP_202_ACCEPTED)
async def run_mapping(
    engagement_id: str = Path(...),
    payload: MappingRunRequest = MappingRunRequest(),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Trigger the AI mapping pipeline (P2.1 + P2.2)."""
    await _get_engagement(db, engagement_id)
    _run_state[engagement_id] = {"status": "running", "progress_pct": 0, "message": "Starting…"}
    background_tasks.add_task(_run_mapping_pipeline, engagement_id, payload.domain_ids, payload.force_rerun)
    return MappingRunStatus(engagement_id=engagement_id, status="running", message="Started")


@router.get("/status", response_model=MappingRunStatus)
async def get_mapping_status(engagement_id: str = Path(...)):
    state = _run_state.get(engagement_id, {"status": "idle", "message": "No run started"})
    return MappingRunStatus(engagement_id=engagement_id, **{k: v for k, v in state.items() if k in MappingRunStatus.model_fields})


@router.get("", response_model=list[MappingEntryOut])
async def list_mappings(
    engagement_id: str = Path(...),
    domain_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = (select(MappingEntry)
         .where(MappingEntry.engagement_id == engagement_id)
         .order_by(MappingEntry.domain_id, MappingEntry.src_table, MappingEntry.src_field)
         .offset((page - 1) * per_page).limit(per_page))
    if domain_id:
        q = q.where(MappingEntry.domain_id == domain_id)
    if status_filter:
        q = q.where(MappingEntry.status == status_filter)
    result = await db.execute(q)
    return result.scalars().all()


@router.patch("/approve", status_code=status.HTTP_200_OK)
async def bulk_approve(
    engagement_id: str = Path(...),
    payload: MappingApproval = ...,
    db: AsyncSession = Depends(get_db),
):
    action_to_status = {"confirm": "confirmed", "reject": "rejected", "reset": "pending"}
    new_status = action_to_status.get(payload.action)
    if not new_status:
        raise HTTPException(400, f"Unknown action '{payload.action}'")
    await db.execute(
        update(MappingEntry)
        .where(MappingEntry.id.in_(payload.mapping_ids), MappingEntry.engagement_id == engagement_id)
        .values(status=new_status)
    )
    db.add(AuditEvent(
        engagement_id=engagement_id, event_type=f"mapping.{payload.action}",
        actor_type="sme", actor_id="dev@fis.com",
        summary=f"{len(payload.mapping_ids)} mappings {payload.action}ed",
        detail={"ids": payload.mapping_ids[:10]},
    ))
    await db.commit()
    return {"updated": len(payload.mapping_ids)}


async def _run_mapping_pipeline(engagement_id: str, domain_ids, force_rerun: bool) -> None:
    from app.db.session import get_session_factory
    from app.services.ai.rag import rag_service
    from app.services.ai.mapper import semantic_mapper
    from app.services.schema.profiler import domain_profiler
    from app.services.schema.extractor import ParsedTable as PT, ParsedField as PF, SchemaParseResult as SPR

    async with get_session_factory()() as db:
        try:
            state = _run_state[engagement_id]
            state.update(progress_pct=10, message="Loading schemas…")

            src_q = await db.execute(select(SchemaFile).where(
                SchemaFile.engagement_id == engagement_id, SchemaFile.side == "src",
                SchemaFile.parse_status == "complete").order_by(SchemaFile.uploaded_at.desc()).limit(1))
            tgt_q = await db.execute(select(SchemaFile).where(
                SchemaFile.engagement_id == engagement_id, SchemaFile.side == "tgt",
                SchemaFile.parse_status == "complete").order_by(SchemaFile.uploaded_at.desc()).limit(1))
            src_file = src_q.scalar_one_or_none()
            tgt_file = tgt_q.scalar_one_or_none()
            if not src_file or not tgt_file:
                state.update(status="failed", message="Schema files missing"); return

            def _rebuild(parse_dict):
                r = SPR()
                for td in (parse_dict or {}).get("tables", []):
                    t = PT(name=td["name"])
                    for fd in td.get("fields", []):
                        t.fields.append(PF(td["name"], fd.get("field",""), fd.get("type",""), description=fd.get("description","")))
                    r.tables.append(t)
                return r

            tgt_count = await rag_service.count(engagement_id, "tgt", db)
            if tgt_count == 0 or force_rerun:
                state.update(progress_pct=25, message="Building Frp embeddings…")
                await rag_service.embed_schema(engagement_id, "tgt", _rebuild(tgt_file.parse_result), db)

            state.update(progress_pct=40, message="Classifying Relius domains…")
            profile = domain_profiler.profile(_rebuild(src_file.parse_result))
            domains_to_map = [d for d in profile.domains if d.tables]
            if domain_ids:
                domains_to_map = [d for d in domains_to_map if d.id in domain_ids]

            all_proposals = []
            for i, domain in enumerate(domains_to_map):
                pct = 40 + int((i / max(len(domains_to_map), 1)) * 50)
                state.update(progress_pct=pct, message=f"Mapping {domain.name}…")
                proposals = await semantic_mapper.map_domain(engagement_id, domain.id, domain.tables, db)
                all_proposals.extend(proposals)

            state.update(progress_pct=92, message="Saving proposals…")
            await semantic_mapper.save_proposals(engagement_id, all_proposals, db)

            auto   = sum(1 for p in all_proposals if p.status == "auto_approved")
            review = sum(1 for p in all_proposals if p.status == "review")
            gaps   = sum(1 for p in all_proposals if p.status == "gap")
            state.update(status="complete", progress_pct=100,
                message=f"Complete — {auto} auto-approved, {review} review, {gaps} gaps",
                total_mappings=len(all_proposals), auto_approved=auto, needs_review=review, gaps=gaps)
        except Exception as exc:
            logger.error("mapping.pipeline.error", engagement=engagement_id, error=str(exc))
            _run_state.get(engagement_id, {}).update(status="failed", message=str(exc))


async def _get_engagement(db: AsyncSession, eid: str) -> Engagement:
    r = await db.execute(select(Engagement).where(Engagement.id == eid))
    e = r.scalar_one_or_none()
    if not e:
        raise HTTPException(404, f"Engagement {eid} not found")
    return e
