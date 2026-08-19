"""
app/services/schema/library.py
Persistent cross-engagement schema understanding library.

Relius (source) and Frp (target) are vendor products whose schemas are largely
identical across clients. This service accumulates a canonical understanding of
each product (keyed by product + version), auto-merging generic schema metadata
from every engagement, and lets a new engagement reuse it without re-uploading.

No client data / PII — schema metadata only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Engagement, FieldEmbedding, SchemaFile,
    SchemaKnowledge, SchemaKnowledgeField,
)
from app.services.schema.extractor import ParsedField, ParsedTable, SchemaParseResult
from app.services.schema.profiler import build_parse_result_dict, domain_profiler

logger = structlog.get_logger(__name__)

_PRODUCT_BY_SIDE = {"src": "relius", "tgt": "frp"}


def product_for_side(side: str) -> str:
    return _PRODUCT_BY_SIDE.get(side, side)


def version_for(engagement: Engagement, product: str) -> str:
    raw = engagement.relius_version if product == "relius" else engagement.frp_version
    return (raw or "").strip() or "unspecified"


class SchemaLibrary:
    # ── Lookup ────────────────────────────────────────────────
    async def get(self, product: str, version: str, db: AsyncSession) -> Optional[SchemaKnowledge]:
        q = await db.execute(
            select(SchemaKnowledge).where(
                SchemaKnowledge.product == product,
                SchemaKnowledge.version == version,
            )
        )
        return q.scalar_one_or_none()

    async def get_or_create(self, product: str, version: str, db: AsyncSession) -> SchemaKnowledge:
        sk = await self.get(product, version, db)
        if sk is None:
            sk = SchemaKnowledge(product=product, version=version)
            db.add(sk)
            await db.flush()
        return sk

    async def summary(self, product: str, version: str, db: AsyncSession) -> dict:
        sk = await self.get(product, version, db)
        if not sk or sk.field_count == 0:
            return {"exists": False, "product": product, "version": version}
        return {
            "exists":            True,
            "product":           product,
            "version":           version,
            "table_count":       sk.table_count,
            "field_count":       sk.field_count,
            "domain_count":      sk.domain_count,
            "contributor_count": sk.contributor_count,
            "updated_at":        sk.updated_at.isoformat() if sk.updated_at else None,
        }

    async def catalog(self, product: str, version: str, db: AsyncSession) -> dict:
        """
        Full table/field catalog for the library understanding — drives the
        read-only "View schema" popup. Does NOT touch the engagement.
        """
        sk = await self.get(product, version, db)
        if not sk:
            return {"exists": False, "product": product, "version": version, "tables": []}
        rows = (await db.execute(
            select(SchemaKnowledgeField)
            .where(SchemaKnowledgeField.knowledge_id == sk.id)
            .order_by(SchemaKnowledgeField.table_name, SchemaKnowledgeField.field_name)
        )).scalars().all()
        tables: dict[str, dict] = {}
        for f in rows:
            t = tables.setdefault(f.table_name, {"name": f.table_name, "domain_id": f.domain_id, "fields": []})
            t["fields"].append({
                "field":       f.field_name,
                "type":        f.data_type or "",
                "description": f.description or "",
                "is_pk":       bool(f.is_pk),
                "is_fk":       bool(f.is_fk),
                "occurrences": f.occurrence_count or 1,
            })
        return {
            "exists":       True,
            "product":      product,
            "version":      version,
            "table_count":  sk.table_count,
            "field_count":  sk.field_count,
            "domain_count": sk.domain_count,
            "tables":       list(tables.values()),
        }

    # ── Merge (auto-learn generic metadata) ───────────────────
    async def merge_from_parse(
        self, engagement_id: str, side: str, parse_result_dict: dict, db: AsyncSession,
    ) -> Optional[SchemaKnowledge]:
        """
        Fold the generic schema metadata from an engagement's parse into the
        library. Descriptions/types are gap-filled (kept when already present);
        domain/pk/fk are refreshed; occurrence_count is bumped per field.
        Best-effort — never raises into the caller's pipeline.
        """
        eng = (await db.execute(select(Engagement).where(Engagement.id == engagement_id))).scalar_one_or_none()
        if eng is None:
            return None
        product = product_for_side(side)
        version = version_for(eng, product)
        sk = await self.get_or_create(product, version, db)

        existing = {
            (f.table_name, f.field_name): f
            for f in (await db.execute(
                select(SchemaKnowledgeField).where(SchemaKnowledgeField.knowledge_id == sk.id)
            )).scalars().all()
        }

        for t in parse_result_dict.get("tables_detail", []):
            tname = (t.get("name") or "").upper()
            if not tname:
                continue
            for f in t.get("fields", []):
                fname = (f.get("field") or "").upper()
                if not fname:
                    continue
                self._upsert_field(
                    db, sk, existing, tname, fname,
                    data_type=(f.get("type") or "").strip(),
                    description=(f.get("description") or "").strip(),
                    domain_id=t.get("domain_id"),
                    is_pk=bool(f.get("is_pk")),
                    is_fk=bool(f.get("is_fk")),
                    references=f.get("references"),
                    overwrite=False,
                )

        await db.flush()
        self._recompute_counts(sk, existing.values(), bump_contributor=True)
        await db.commit()
        logger.info("schema.library.merged", product=product, version=version,
                    fields=sk.field_count, tables=sk.table_count)
        return sk

    async def merge_field_edits(
        self, engagement_id: str, side: str, field_edits: list[dict], db: AsyncSession,
    ) -> None:
        """
        Fold SME corrections (DomainReview.field_edits) into the library. Because
        these are explicit human corrections they OVERWRITE the canonical value.
        """
        if not field_edits:
            return
        eng = (await db.execute(select(Engagement).where(Engagement.id == engagement_id))).scalar_one_or_none()
        if eng is None:
            return
        product = product_for_side(side)
        version = version_for(eng, product)
        sk = await self.get_or_create(product, version, db)
        existing = {
            (f.table_name, f.field_name): f
            for f in (await db.execute(
                select(SchemaKnowledgeField).where(SchemaKnowledgeField.knowledge_id == sk.id)
            )).scalars().all()
        }
        for fe in field_edits:
            tname = (fe.get("table") or "").upper()
            fname = (fe.get("field") or "").upper()
            if not tname or not fname:
                continue
            self._upsert_field(
                db, sk, existing, tname, fname,
                data_type=(fe.get("type") or "").strip(),
                description=(fe.get("description") or "").strip(),
                domain_id=None,
                is_pk=bool(fe.get("is_pk")),
                is_fk=bool(fe.get("is_fk")),
                references=None,
                overwrite=True,  # SME is authoritative
            )
        await db.flush()
        self._recompute_counts(sk, existing.values(), bump_contributor=False)
        await db.commit()
        logger.info("schema.library.edits_merged", product=product, version=version, edits=len(field_edits))

    def _upsert_field(self, db, sk, existing, tname, fname, *, data_type, description,
                      domain_id, is_pk, is_fk, references, overwrite):
        rec = existing.get((tname, fname))
        if rec is None:
            rec = SchemaKnowledgeField(
                knowledge_id=sk.id, table_name=tname, field_name=fname,
                data_type=data_type or None, description=description or None,
                domain_id=domain_id, is_pk=is_pk, is_fk=is_fk,
                references=references, occurrence_count=1,
            )
            existing[(tname, fname)] = rec
            # db.add (not sk.fields.append) — appending to the relationship would
            # trigger an async lazy-load of sk.fields and raise MissingGreenlet.
            db.add(rec)
            return
        # Update existing
        if description and (overwrite or not (rec.description or "").strip()):
            rec.description = description
        if data_type and (overwrite or not (rec.data_type or "").strip()):
            rec.data_type = data_type
        if domain_id:
            rec.domain_id = domain_id
        rec.is_pk = is_pk if overwrite else (rec.is_pk or is_pk)
        rec.is_fk = is_fk if overwrite else (rec.is_fk or is_fk)
        if references and not rec.references:
            rec.references = references
        rec.occurrence_count = (rec.occurrence_count or 0) + 1
        rec.last_updated = datetime.utcnow()

    @staticmethod
    def _recompute_counts(sk, fields, *, bump_contributor: bool) -> None:
        fields = list(fields)
        sk.field_count  = len(fields)
        sk.table_count  = len({f.table_name for f in fields})
        sk.domain_count = len({f.domain_id for f in fields if f.domain_id})
        if bump_contributor:
            sk.contributor_count = (sk.contributor_count or 0) + 1
        sk.updated_at = datetime.utcnow()

    # ── Backfill (one-time, from already-parsed engagements) ──
    async def backfill_from_existing(self, db: AsyncSession) -> int:
        """
        Seed the library from schema files parsed before the library existed.
        Seeds each (product, version) bucket from its MOST RECENT completed scan
        only — not the union of every historical run — so an evolving/older parse
        can't inflate the catalog with stale or false-positive tables.
        Only fills buckets that are still empty (idempotent). Best-effort.
        """
        files = (await db.execute(
            select(SchemaFile).where(
                SchemaFile.parse_status == "complete",
                SchemaFile.origin == "upload",
            ).order_by(SchemaFile.uploaded_at)  # oldest → newest
        )).scalars().all()
        if not files:
            return 0

        engagements = {
            e.id: e for e in (await db.execute(select(Engagement))).scalars().all()
        }
        # Skip buckets that already hold understanding
        nonempty = {
            (sk.product, sk.version)
            for sk in (await db.execute(select(SchemaKnowledge))).scalars().all()
            if (sk.field_count or 0) > 0
        }

        # Keep only the newest completed scan per (product, version)
        latest: dict[tuple, SchemaFile] = {}
        for sf in files:
            eng = engagements.get(sf.engagement_id)
            if not eng or not sf.parse_result:
                continue
            key = (product_for_side(sf.side), version_for(eng, product_for_side(sf.side)))
            if key in nonempty:
                continue
            latest[key] = sf  # later iterations are newer → overwrite

        merged = 0
        for sf in latest.values():
            await self.merge_from_parse(sf.engagement_id, sf.side, sf.parse_result, db)
            merged += 1
        if merged:
            logger.info("schema.library.backfilled", buckets=merged)
        return merged

    # ── Reuse ("Use it") ──────────────────────────────────────
    async def seed_engagement(self, engagement_id: str, side: str, db: AsyncSession) -> Optional[SchemaFile]:
        """
        Materialise the library understanding into an engagement: create a
        synthetic completed SchemaFile (origin='library') and engagement-scoped
        FieldEmbedding rows (reusing stored vectors). Returns the SchemaFile, or
        None if there's no understanding for this product/version.
        """
        eng = (await db.execute(select(Engagement).where(Engagement.id == engagement_id))).scalar_one_or_none()
        if eng is None:
            return None
        product = product_for_side(side)
        version = version_for(eng, product)
        sk = await self.get(product, version, db)
        if not sk:
            return None
        lib_fields = (await db.execute(
            select(SchemaKnowledgeField).where(SchemaKnowledgeField.knowledge_id == sk.id)
        )).scalars().all()
        if not lib_fields:
            return None

        # Rebuild an extractor result, then run the SAME profiler + dict builder
        # the upload pipeline uses, so downstream screens see an identical shape.
        tables: dict[str, ParsedTable] = {}
        for lf in lib_fields:
            tbl = tables.setdefault(lf.table_name, ParsedTable(name=lf.table_name))
            tbl.fields.append(ParsedField(
                table_name=lf.table_name, field_name=lf.field_name,
                data_type=lf.data_type or "", is_pk=bool(lf.is_pk), is_fk=bool(lf.is_fk),
                references=lf.references, description=lf.description or "",
            ))
        parse_result = SchemaParseResult(tables=list(tables.values()))
        profile = domain_profiler.profile(parse_result)
        result_dict = build_parse_result_dict(parse_result, profile)

        sf = SchemaFile(
            engagement_id=engagement_id, side=side,
            filename=f"{product}@{version} (reused from library)",
            file_type="library", parse_status="complete",
            parse_result=result_dict, origin="library", uploaded_by="library",
        )
        db.add(sf)

        # Engagement embeddings — created without vectors; retrieval uses the
        # text fallback in rag.py, so mapping works without recomputing vectors.
        await db.execute(delete(FieldEmbedding).where(
            FieldEmbedding.engagement_id == engagement_id, FieldEmbedding.side == side,
        ))
        for lf in lib_fields:
            db.add(FieldEmbedding(
                engagement_id=engagement_id, side=side,
                table_name=lf.table_name, field_name=lf.field_name,
                domain_id=lf.domain_id, data_type=lf.data_type or "",
                description=lf.description or "",
            ))
        await db.commit()
        await db.refresh(sf)
        logger.info("schema.library.seeded", engagement=engagement_id, side=side,
                    product=product, version=version, fields=len(lib_fields))
        return sf


schema_library = SchemaLibrary()
