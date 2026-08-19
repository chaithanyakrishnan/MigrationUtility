"""
app/api/routes/schema.py
Schema file upload, parsing, profiling, and RAG embedding.
Screens 1 (Relius) and 3 (Frp).
"""
from __future__ import annotations

from typing import Literal, List
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Engagement, SchemaFile, AuditEvent, DomainReview
from app.schemas.schemas import SchemaFileOut, SchemaParseResult as SchemaParseResultSchema

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/engagements/{engagement_id}/schema")

ALLOWED_EXTENSIONS = {".sql", ".ddl", ".json", ".xlsx", ".xls", ".csv", ".txt", ".pdf", ".docx"}
# COBOL copybooks / record layouts — accepted for the Frp (tgt) side only.
COBOL_EXTENSIONS = {".cbl", ".cob", ".cpy", ".cobol", ".copybook", ".cpb"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload/{side}", response_model=SchemaFileOut, status_code=status.HTTP_201_CREATED)
async def upload_schema_file(
    engagement_id: str = Path(...),
    side: Literal["src", "tgt"] = Path(...),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """Upload a schema file. Parsing + profiling + RAG embedding run in background."""
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, f"Engagement {engagement_id} not found")

    from pathlib import Path as FP
    ext = FP(file.filename or "").suffix.lower()
    # COBOL copybooks are only valid as Frp / FRP (target) record layouts.
    allowed = ALLOWED_EXTENSIONS | (COBOL_EXTENSIONS if side == "tgt" else set())
    if ext not in allowed:
        raise HTTPException(400, f"'{ext}' not supported for {side}. Use: {', '.join(sorted(allowed))}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max 50 MB.")

    # Multiple documents per side are supported — files accumulate and the
    # /domains endpoint merges across all of them. Use DELETE /files/{id} to
    # remove a file that was uploaded by mistake.
    sf = SchemaFile(
        engagement_id=engagement_id,
        side=side,
        filename=file.filename or "upload",
        file_type=ext.lstrip("."),
        size_bytes=len(content),
        parse_status="parsing",
        uploaded_by="dev@fis.com",
    )
    db.add(sf)
    await db.flush()
    file_id = sf.id

    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="schema.upload_started",
        actor_type="sme", actor_id="dev@fis.com",
        summary=f"'{file.filename}' uploaded ({side})",
        detail={"filename": file.filename, "side": side, "size": len(content)},
    ))
    await db.commit()

    background_tasks.add_task(
        _parse_profile_embed,
        file_id, engagement_id, file.filename or "", content, side
    )

    await db.refresh(sf)
    return sf


@router.get("/files", response_model=List[SchemaFileOut])
async def list_schema_files(
    engagement_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchemaFile)
        .where(SchemaFile.engagement_id == engagement_id)
        .order_by(SchemaFile.uploaded_at)
    )
    return result.scalars().all()


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema_file(
    engagement_id: str = Path(...),
    file_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Remove one uploaded schema file (e.g. uploaded by mistake)."""
    result = await db.execute(
        select(SchemaFile).where(
            SchemaFile.id == file_id,
            SchemaFile.engagement_id == engagement_id,
        )
    )
    sf = result.scalar_one_or_none()
    if not sf:
        raise HTTPException(404, "Schema file not found")
    fname, side = sf.filename, sf.side
    await db.delete(sf)
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="schema.file_deleted",
        actor_type="sme", actor_id="dev@fis.com",
        summary=f"Removed schema file '{fname}' ({side})",
        detail={"file_id": file_id, "filename": fname, "side": side},
    ))
    await db.commit()


@router.get("/files/{file_id}/status", response_model=SchemaFileOut)
async def get_file_status(
    engagement_id: str = Path(...),
    file_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SchemaFile).where(
            SchemaFile.id == file_id,
            SchemaFile.engagement_id == engagement_id,
        )
    )
    sf = result.scalar_one_or_none()
    if not sf:
        raise HTTPException(404, "Schema file not found")
    return sf


@router.get("/files/{file_id}/parse-result")
async def get_parse_result(
    engagement_id: str = Path(...),
    file_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Full parse result including all tables, domains, and completeness scores."""
    result = await db.execute(
        select(SchemaFile).where(
            SchemaFile.id == file_id,
            SchemaFile.engagement_id == engagement_id,
            SchemaFile.parse_status == "complete",
        )
    )
    sf = result.scalar_one_or_none()
    if not sf:
        raise HTTPException(404, "Not found or not yet parsed")
    return sf.parse_result or {}


async def _complete_files(db: AsyncSession, engagement_id: str, side: str) -> list[SchemaFile]:
    """All successfully-parsed schema files for a side, oldest first."""
    result = await db.execute(
        select(SchemaFile).where(
            SchemaFile.engagement_id == engagement_id,
            SchemaFile.side == side,
            SchemaFile.parse_status == "complete",
        ).order_by(SchemaFile.uploaded_at)
    )
    return list(result.scalars().all())


@router.get("/domains")
async def get_schema_domains(
    engagement_id: str = Path(...),
    side: str = "src",
    db: AsyncSession = Depends(get_db),
):
    """
    Return the domain breakdown merged across ALL parsed schema files for a
    side (multiple documents are supported). Screen 2 (Relius Review) and
    Screen 4 (Frp Review) read this. Completeness is recomputed from the
    merged tables and any SME field edits.
    """
    from app.services.schema.profiler import score_schema_completeness

    files = await _complete_files(db, engagement_id, side)
    if not files:
        return {"domains": [], "total_tables": 0, "total_fields": 0}

    # Merge tables across every file; carry domain name/icon + warnings forward
    all_tables: list[dict] = []
    domain_meta: dict[str, dict] = {}
    domain_warnings: dict[str, list] = {}
    file_warnings: list = []
    fk_count = 0
    for sf in files:
        pr = sf.parse_result or {}
        all_tables.extend(pr.get("tables_detail", []))
        fk_count += pr.get("fk_count", 0)
        file_warnings.extend(pr.get("warnings", []) or [])
        for d in pr.get("domains_detail", []):
            domain_meta.setdefault(d["id"], {"name": d.get("name", d["id"]), "icon": d.get("icon", "")})
            if d.get("warnings"):
                domain_warnings.setdefault(d["id"], []).extend(d["warnings"])

    # Group merged tables by domain
    by_domain: dict[str, list] = {}
    for t in all_tables:
        by_domain.setdefault(t.get("domain_id", "unknown"), []).append(t)
    for did in by_domain:
        domain_meta.setdefault(did, {"name": did, "icon": ""})

    # SME field edits, for completeness recompute
    rev_q = await db.execute(
        select(DomainReview).where(
            DomainReview.engagement_id == engagement_id,
            DomainReview.side == side,
        )
    )
    reviews = {r.domain_id: r for r in rev_q.scalars().all()}

    domains = []
    for did, meta in domain_meta.items():
        tbls = by_domain.get(did, [])
        rev = reviews.get(did)
        edit_map = {
            (fe["table"], fe["field"]): fe
            for fe in (rev.field_edits or [])
            if fe.get("table") and fe.get("field")
        } if rev else {}

        score_tables, field_count = [], 0
        for t in tbls:
            fields = []
            for f in t.get("fields", []):
                e = edit_map.get((t.get("name"), f.get("field")))
                src = e if e else f
                fields.append({
                    "is_pk":       src.get("is_pk"),
                    "is_fk":       src.get("is_fk"),
                    "description": src.get("description"),
                })
            field_count += len(t.get("fields", []))
            score_tables.append({"fields": fields})

        completeness = score_schema_completeness(score_tables) if score_tables else 0
        domains.append({
            "id":           did,
            "name":         meta["name"],
            "icon":         meta["icon"],
            "table_count":  len(tbls),
            "field_count":  field_count,
            "completeness": completeness,
            "needs_review": completeness < 80,
            "warnings":     domain_warnings.get(did, []),
            "tables":       [t.get("name") for t in tbls],
        })

    total_tables = sum(d["table_count"] for d in domains)
    total_fields = sum(d["field_count"] for d in domains)
    return {
        "domains":      domains,
        "total_tables": total_tables,
        "total_fields": total_fields,
        "card_tables":  total_tables,
        "card_fields":  total_fields,
        "fk_count":     fk_count,
        "warnings":     file_warnings,
        "file_count":   len(files),
    }


@router.get("/domains/{domain_id}/tables")
async def get_domain_tables(
    engagement_id: str = Path(...),
    domain_id: str = Path(...),
    side: str = "src",
    db: AsyncSession = Depends(get_db),
):
    """
    Return all tables and fields for a specific domain, merged across every
    parsed schema file for the side. Used by the domain detail panel.
    """
    files = await _complete_files(db, engagement_id, side)
    domain_tables = [
        t
        for sf in files
        for t in (sf.parse_result or {}).get("tables_detail", [])
        if t.get("domain_id") == domain_id
    ]
    return {"domain_id": domain_id, "tables": domain_tables}


# ── Schema understanding library (cross-engagement reuse) ────
@router.get("/knowledge")
async def get_schema_knowledge(
    engagement_id: str = Path(...),
    side: str = "src",
    db: AsyncSession = Depends(get_db),
):
    """
    Does a persistent schema understanding already exist for this engagement's
    product (relius/frp) + version? Drives the "reuse" banner on the upload screen.
    """
    from app.core.config import get_settings
    if not get_settings().schema_library_enabled:
        return {"exists": False}
    from app.services.schema.library import schema_library, product_for_side, version_for

    eng = (await db.execute(select(Engagement).where(Engagement.id == engagement_id))).scalar_one_or_none()
    if not eng:
        raise HTTPException(404, f"Engagement {engagement_id} not found")
    product = product_for_side(side)
    return await schema_library.summary(product, version_for(eng, product), db)


@router.get("/knowledge/tables")
async def get_schema_knowledge_tables(
    engagement_id: str = Path(...),
    side: str = "src",
    db: AsyncSession = Depends(get_db),
):
    """Full library catalog (tables + fields) for the read-only 'View schema' popup."""
    from app.core.config import get_settings
    if not get_settings().schema_library_enabled:
        return {"exists": False, "tables": []}
    from app.services.schema.library import schema_library, product_for_side, version_for

    eng = (await db.execute(select(Engagement).where(Engagement.id == engagement_id))).scalar_one_or_none()
    if not eng:
        raise HTTPException(404, f"Engagement {engagement_id} not found")
    product = product_for_side(side)
    return await schema_library.catalog(product, version_for(eng, product), db)


@router.post("/knowledge/use", response_model=SchemaFileOut)
async def use_schema_knowledge(
    engagement_id: str = Path(...),
    side: str = "src",
    db: AsyncSession = Depends(get_db),
):
    """Seed this engagement from the library understanding (the "Use it" action)."""
    from app.services.schema.library import schema_library
    sf = await schema_library.seed_engagement(engagement_id, side, db)
    if sf is None:
        raise HTTPException(404, "No schema understanding available for this product/version")
    db.add(AuditEvent(
        engagement_id=engagement_id,
        event_type="schema.library.reused",
        actor_type="sme", actor_id="dev@fis.com",
        summary=f"Reused library understanding for {side} ({sf.filename})",
        detail={"side": side, "file_id": sf.id},
    ))
    await db.commit()
    return sf


# ── Background: parse → profile → embed ──────────────────────
async def _parse_profile_embed(
    file_id: str,
    engagement_id: str,
    filename: str,
    content: bytes,
    side: str,
) -> None:
    """
    Background pipeline: Extract → Profile → Embed.
    Uses two separate DB sessions:
      Session 1: parse file, classify domains, store result on SchemaFile
      Session 2: generate and store field embeddings (may take longer)
    """
    from app.db.session import get_session_factory
    from app.services.schema.extractor import extractor
    from app.services.schema.profiler import domain_profiler, build_parse_result_dict
    from app.services.ai.rag import rag_service

    factory = get_session_factory()

    # ── Session 1: Extract + Profile + persist to SchemaFile ──
    parse_result = None
    domain_map   = {}
    try:
        logger.info("schema.parse.start", file_id=file_id, filename=filename)
        parse_result = extractor.extract(filename, content)
        profile      = domain_profiler.profile(parse_result)
        domain_map   = profile.domain_map

        result_dict = build_parse_result_dict(parse_result, profile)

        # Validate: a file that yields no tables or no fields is a failed parse,
        # not a silent success. This catches a wrong file uploaded with a valid
        # extension (e.g. a non-COBOL file renamed to .cbl).
        if parse_result.table_count == 0 or parse_result.field_count == 0:
            reason = "; ".join(parse_result.warnings) or (
                "No tables or fields could be extracted — the file may be the "
                "wrong format or not a recognised schema / COBOL copybook."
            )
            async with factory() as db_fail:
                sf_q = await db_fail.execute(select(SchemaFile).where(SchemaFile.id == file_id))
                sf = sf_q.scalar_one_or_none()
                if sf:
                    sf.parse_status = "failed"
                    sf.parse_error  = reason
                    sf.parse_result = result_dict  # keep warnings/partial detail
                db_fail.add(AuditEvent(
                    engagement_id=engagement_id,
                    event_type="schema.parse_failed",
                    actor_type="system", actor_id="system",
                    summary=f"Parse produced no usable schema ({parse_result.raw_format}): {reason[:160]}",
                    detail={"warnings": parse_result.warnings, "format": parse_result.raw_format},
                ))
                await db_fail.commit()
            logger.warning("schema.parse_empty", file_id=file_id, reason=reason)
            return  # nothing to embed

        async with factory() as db1:
            sf_q = await db1.execute(select(SchemaFile).where(SchemaFile.id == file_id))
            sf = sf_q.scalar_one_or_none()
            if sf:
                sf.parse_status = "complete"
                sf.parse_result = result_dict
            db1.add(AuditEvent(
                engagement_id=engagement_id,
                event_type="schema.parsed",
                actor_type="system",
                actor_id="system",
                summary=(
                    f"Parsed: {parse_result.table_count} tables, "
                    f"{parse_result.field_count} fields, "
                    f"{len([d for d in profile.domains if d.table_count > 0])} domains"
                ),
                detail={
                    "table_count":    parse_result.table_count,
                    "field_count":    parse_result.field_count,
                    "domain_summary": {d.id: d.table_count for d in profile.domains},
                },
            ))
            await db1.commit()

        logger.info("schema.parsed", file_id=file_id,
                    tables=parse_result.table_count, fields=parse_result.field_count)

    except Exception as exc:
        logger.error("schema.parse_error", file_id=file_id, error=str(exc), exc_info=True)
        try:
            async with factory() as db_err:
                sf_q = await db_err.execute(select(SchemaFile).where(SchemaFile.id == file_id))
                sf = sf_q.scalar_one_or_none()
                if sf:
                    sf.parse_status = "failed"
                    sf.parse_error  = str(exc)
                await db_err.commit()
        except Exception:
            pass
        return  # do not attempt embedding if parse failed

    # ── Session 2: Generate and store embeddings ──────────────
    try:
        logger.info("schema.embed.start", file_id=file_id, side=side)
        async with factory() as db2:
            embed_count = await rag_service.embed_schema(
                engagement_id=engagement_id,
                side=side,
                parse_result=parse_result,
                db=db2,
                domain_map=domain_map,
            )
            db2.add(AuditEvent(
                engagement_id=engagement_id,
                event_type="schema.embedded",
                actor_type="system",
                actor_id="system",
                summary=f"RAG: {embed_count} field embeddings stored (side={side})",
                detail={"embed_count": embed_count, "side": side},
            ))
            await db2.commit()
        logger.info("schema.embedded", file_id=file_id, count=embed_count)
    except Exception as exc:
        logger.error("schema.embed_error", file_id=file_id, error=str(exc), exc_info=True)
        # Embedding failure is non-fatal — parse result is already saved

    # ── Session 3: Auto-merge generic metadata into the library ──
    from app.core.config import get_settings
    if get_settings().schema_library_enabled:
        try:
            from app.services.schema.library import schema_library
            async with factory() as db3:
                sk = await schema_library.merge_from_parse(engagement_id, side, result_dict, db3)
                if sk is not None:
                    db3.add(AuditEvent(
                        engagement_id=engagement_id,
                        event_type="schema.library.merged",
                        actor_type="system", actor_id="system",
                        summary=f"Merged into {sk.product}@{sk.version} library "
                                f"({sk.table_count} tables, {sk.field_count} fields)",
                        detail={"product": sk.product, "version": sk.version,
                                "field_count": sk.field_count, "side": side},
                    ))
                    await db3.commit()
        except Exception as exc:
            logger.error("schema.library.merge_error", file_id=file_id, error=str(exc), exc_info=True)
            # Library merge is best-effort — never fails the upload
