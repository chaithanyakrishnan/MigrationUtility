"""
app/api/routes/project.py
Migration-project endpoints (v5 mig flow): table selection, AI mapping with
transaction-card assignment, transaction-card review, and the batch run that
writes fixed-width Frp transaction-card output.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import (
    Engagement, AuditEvent, ProjectState, ProjectMapping, ProjectExport,
    KnowledgeBase, KBTransactionCard,
)
from app.schemas.schemas import (
    ProjectStateOut, ProjectTablesUpdate, ProjectMappingOut, ProjectMappingPatch,
    ProjectCardOut, ProjectCardFieldOut, ProjectBatchResult,
)
from app.services.kb.mapping_seed import MAPPING_CATALOGUE, derive_txn_code
from app.services.pipeline.txn_export import generate_export

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements/{engagement_id}/project")


# ── helpers ───────────────────────────────────────────────────
async def _get_engagement(db: AsyncSession, eng_id: str) -> Engagement:
    e = (await db.execute(select(Engagement).where(Engagement.id == eng_id))).scalar_one_or_none()
    if not e:
        raise HTTPException(404, f"Engagement {eng_id} not found")
    return e


async def _get_or_create_state(db: AsyncSession, eng_id: str) -> ProjectState:
    st = (await db.execute(
        select(ProjectState).where(ProjectState.engagement_id == eng_id)
    )).scalar_one_or_none()
    if st is None:
        st = ProjectState(engagement_id=eng_id, selected_tables=[], approved_cards=[], mapping_seeded=False)
        db.add(st)
        await db.flush()
    return st


def _eff_txn(m: ProjectMapping) -> str | None:
    if m.txn_override is not None:
        return m.txn_override or None
    return m.txn_code


def _mapping_out(m: ProjectMapping) -> ProjectMappingOut:
    return ProjectMappingOut(
        id=m.id, domain_id=m.domain_id, src_table=m.src_table, src_field=m.src_field,
        frp=m.frp_override if m.frp_override is not None else (m.frp_record or ""),
        tgt=m.tgt_override if m.tgt_override is not None else (m.tgt_display or ""),
        txn=_eff_txn(m),
        confidence=m.confidence or 0, mapping_type=m.mapping_type, note=m.note,
        is_multi=m.is_multi, approved=m.approved,
        frp_modified=m.frp_override is not None,
        tgt_modified=m.tgt_override is not None,
        txn_modified=m.txn_override is not None,
    )


async def _mappings(db: AsyncSession, eng_id: str) -> list[ProjectMapping]:
    return list((await db.execute(
        select(ProjectMapping).where(ProjectMapping.engagement_id == eng_id)
        .order_by(ProjectMapping.sort_order)
    )).scalars().all())


# ── project state + table selection ───────────────────────────
@router.get("", response_model=ProjectStateOut)
async def get_project(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    await _get_engagement(db, engagement_id)
    st = await _get_or_create_state(db, engagement_id)
    await db.commit()
    return ProjectStateOut(
        selected_tables=st.selected_tables or [],
        approved_cards=st.approved_cards or [],
        mapping_seeded=st.mapping_seeded,
    )


@router.put("/tables", response_model=ProjectStateOut)
async def set_tables(
    payload: ProjectTablesUpdate,
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    await _get_engagement(db, engagement_id)
    st = await _get_or_create_state(db, engagement_id)
    st.selected_tables = payload.tables
    await db.commit()
    return ProjectStateOut(
        selected_tables=st.selected_tables or [], approved_cards=st.approved_cards or [],
        mapping_seeded=st.mapping_seeded,
    )


# ── AI mapping ────────────────────────────────────────────────
@router.post("/mapping/run", response_model=list[ProjectMappingOut])
async def run_mapping(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    """Seed AI-proposed mappings for the selected tables, with T-code assignment."""
    await _get_engagement(db, engagement_id)
    st = await _get_or_create_state(db, engagement_id)
    selected = set(st.selected_tables or [])

    # Clear any previous run, then seed from the catalogue filtered to scope.
    for old in await _mappings(db, engagement_id):
        await db.delete(old)
    await db.flush()

    rows = [m for m in MAPPING_CATALOGUE if not selected or m["src"] in selected]
    for i, m in enumerate(rows):
        db.add(ProjectMapping(
            engagement_id=engagement_id, domain_id=m.get("dom"),
            src_table=m["src"], src_field=m["field"],
            frp_record=m["frp"], tgt_display=m["tgt"],
            txn_code=derive_txn_code(m), confidence=m["conf"], mapping_type=m["type"],
            note=m.get("note") or None, is_multi=bool(m.get("multi")), sort_order=i,
        ))
    st.mapping_seeded = True
    db.add(AuditEvent(
        engagement_id=engagement_id, event_type="project.mapping_run", actor_type="ai",
        actor_id="system", summary=f"AI mapping proposed {len(rows)} field mappings",
        detail={"count": len(rows), "tables": len(selected)},
    ))
    await db.commit()
    return [_mapping_out(m) for m in await _mappings(db, engagement_id)]


@router.get("/mappings", response_model=list[ProjectMappingOut])
async def list_mappings(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    return [_mapping_out(m) for m in await _mappings(db, engagement_id)]


@router.patch("/mappings/{mapping_id}", response_model=ProjectMappingOut)
async def patch_mapping(
    payload: ProjectMappingPatch,
    engagement_id: str = Path(...),
    mapping_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    m = (await db.execute(
        select(ProjectMapping).where(
            ProjectMapping.id == mapping_id, ProjectMapping.engagement_id == engagement_id)
    )).scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Mapping not found")
    if payload.approved is not None:
        m.approved = payload.approved
    if payload.frp_override is not None:
        m.frp_override = payload.frp_override or None
    if payload.tgt_override is not None:
        m.tgt_override = payload.tgt_override or None
    if payload.txn_override is not None:
        # normalise to uppercase; empty string = explicitly unassigned
        m.txn_override = payload.txn_override.strip().upper()
    await db.commit()
    await db.refresh(m)
    return _mapping_out(m)


@router.post("/mappings/approve-all", response_model=list[ProjectMappingOut])
async def approve_all(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    ms = await _mappings(db, engagement_id)
    for m in ms:
        m.approved = True
    await db.commit()
    return [_mapping_out(m) for m in ms]


# ── transaction cards ─────────────────────────────────────────
async def _kb_cards(db: AsyncSession) -> dict[str, KBTransactionCard]:
    kb = (await db.execute(select(KnowledgeBase).where(KnowledgeBase.kind == "frp"))).scalar_one_or_none()
    if kb is None:
        return {}
    cards = (await db.execute(
        select(KBTransactionCard).where(KBTransactionCard.kb_id == kb.id)
        .options(selectinload(KBTransactionCard.fields))
    )).scalars().all()
    return {c.code: c for c in cards}


async def _cards_in_scope(db: AsyncSession, engagement_id: str) -> list[ProjectCardOut]:
    st = await _get_or_create_state(db, engagement_id)
    approved_codes = set(st.approved_cards or [])
    kb_cards = await _kb_cards(db)
    # group approved mappings by effective T-code
    groups: dict[str, list[ProjectMapping]] = {}
    for m in await _mappings(db, engagement_id):
        if not m.approved:
            continue
        code = _eff_txn(m)
        if code:
            groups.setdefault(code, []).append(m)

    out: list[ProjectCardOut] = []
    for code in sorted(groups):
        kb_card = kb_cards.get(code)
        fields: list[ProjectCardFieldOut] = []
        if kb_card:
            for f in sorted(kb_card.fields, key=lambda x: x.sort_order):
                a, _, b = (f.col_range or "").partition("-")
                try:
                    length = int(b) - int(a) + 1 if b else 1
                except ValueError:
                    length = None
                fields.append(ProjectCardFieldOut(
                    col_range=f.col_range, length=length,
                    frp_name=f"{f.code} ({f.name})", relius_source=f.src_guess or "",
                    field_type=f.field_type, note=f.note,
                ))
        # append the mapped Relius fields feeding this card
        for m in groups[code]:
            frp = m.frp_override if m.frp_override is not None else (m.frp_record or "")
            tgt = m.tgt_override if m.tgt_override is not None else (m.tgt_display or "")
            fields.append(ProjectCardFieldOut(
                col_range="—", length=None, frp_name=f"{frp} — {tgt}",
                relius_source=f"{m.src_table}.{m.src_field}", field_type=m.mapping_type,
                note=None if kb_card else f"Column position pending — {code} layout not in Frp KB",
            ))
        out.append(ProjectCardOut(
            code=code, name=kb_card.name if kb_card else None,
            has_layout=bool(kb_card and kb_card.has_layout),
            record_length=kb_card.record_length if kb_card else 110,
            approved=code in approved_codes, fields=fields,
        ))
    return out


@router.get("/cards", response_model=list[ProjectCardOut])
async def get_cards(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    cards = await _cards_in_scope(db, engagement_id)
    await db.commit()
    return cards


@router.patch("/cards/{code}", response_model=ProjectCardOut)
async def approve_card(
    engagement_id: str = Path(...), code: str = Path(...), db: AsyncSession = Depends(get_db),
):
    st = await _get_or_create_state(db, engagement_id)
    approved = set(st.approved_cards or [])
    approved.add(code)
    st.approved_cards = sorted(approved)
    await db.commit()
    cards = await _cards_in_scope(db, engagement_id)
    match = next((c for c in cards if c.code == code), None)
    if match is None:
        raise HTTPException(404, f"Card {code} not in scope")
    return match


# ── batch run ─────────────────────────────────────────────────
@router.post("/batch/run", response_model=ProjectBatchResult)
async def run_batch(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    """Generate fixed-width Frp transaction-card output for the approved cards."""
    st = await _get_or_create_state(db, engagement_id)
    approved_codes = set(st.approved_cards or [])
    kb_cards = await _kb_cards(db)

    # in-scope codes = approved mappings' effective T-codes that are approved cards
    scope_codes = {c for c in approved_codes}
    if not scope_codes:
        # fall back to all cards that have approved mappings
        for m in await _mappings(db, engagement_id):
            if m.approved and _eff_txn(m):
                scope_codes.add(_eff_txn(m))
    cards_payload = []
    for code in scope_codes:
        kb_card = kb_cards.get(code)
        if not kb_card:
            continue
        cards_payload.append({
            "code": code, "has_layout": kb_card.has_layout,
            "fields": [
                {"sub_card": f.sub_card, "code": f.code, "name": f.name,
                 "col_range": f.col_range, "field_type": f.field_type, "note": f.note}
                for f in kb_card.fields
            ],
        })
    if not cards_payload:
        raise HTTPException(400, "No approved transaction cards with layouts to export")

    lines, manifest = generate_export(cards_payload)
    files_read = len(st.selected_tables or []) or 1
    filename = "frp_transaction_cards_export.txt"
    content = "\r\n".join(lines) + "\r\n"

    # replace any prior export
    for old in (await db.execute(
        select(ProjectExport).where(ProjectExport.engagement_id == engagement_id)
    )).scalars().all():
        await db.delete(old)
    db.add(ProjectExport(
        engagement_id=engagement_id, filename=filename, content=content,
        line_count=len(lines), files_read=files_read, manifest=manifest,
    ))
    db.add(AuditEvent(
        engagement_id=engagement_id, event_type="project.batch_run", actor_type="system",
        actor_id="system", summary=f"Batch run wrote {len(lines)} transaction card line(s)",
        detail={"lines": len(lines), "files_read": files_read},
    ))
    await db.commit()
    return ProjectBatchResult(filename=filename, files_read=files_read, line_count=len(lines), manifest=manifest)


@router.get("/export/download", response_class=PlainTextResponse)
async def download_export(engagement_id: str = Path(...), db: AsyncSession = Depends(get_db)):
    exp = (await db.execute(
        select(ProjectExport).where(ProjectExport.engagement_id == engagement_id)
        .order_by(desc(ProjectExport.created_at))
    )).scalars().first()
    if exp is None:
        raise HTTPException(404, "No export generated yet")
    return PlainTextResponse(
        content=exp.content or "",
        headers={"Content-Disposition": f'attachment; filename="{exp.filename}"'},
    )
