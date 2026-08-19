"""
app/services/ai/mapper.py
P2.1 — Semantic Mapper  +  P2.2 — Confidence Scorer

The core AI mapping pipeline:
  1. For each source (Relius) field, retrieve top-20 candidate target (Frp) fields via A1 RAG
  2. Claude LLM reranks candidates using full field context + knowledge base
  3. P2.2 assigns confidence bands and routing decisions
  4. Results written to mapping_registry (P2.3)

Confidence bands (P2.2):
  ≥ 85%  → auto_approved  (no SME review required)
  60–84% → review         (H1 human queue — SME must confirm)
  < 60%  → gap            (no viable mapping found — SME must define manually)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import MappingEntry, AuditEvent, FieldEmbedding
from app.services.ai.rag import rag_service, FieldCandidate
from app.services.schema.extractor import ParsedField, ParsedTable

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class MappingProposal:
    """A single AI-proposed source → target mapping."""
    domain_id: str
    src_table: str
    src_field: str
    tgt_table: str
    tgt_field: str
    confidence: int            # 0–100
    mapping_type: str          # direct | transform | crosswalk | composite | constant | gap
    transform_rule: str = ""
    note: str = ""
    is_multi_source: bool = False
    multi_sources: list[dict] = field(default_factory=list)
    is_udf: bool = False
    is_constant: bool = False
    constant_value: str = ""
    status: str = "pending"    # set by P2.2


class SemanticMapper:
    """
    P2.1 + P2.2 — Semantic Mapper and Confidence Scorer.

    Main entry point: map_domain(engagement_id, domain_id, src_fields, db)
    Returns a list of MappingProposal objects.
    """

    # Candidate pool size from RAG before LLM reranking
    RAG_TOP_K = 20

    # Known Relius constants — always mapped at 100% confidence
    CONSTANTS = {
        "CA007": ("050",  "Cash Control Account Type — constant '050' for standard cash"),
        "AR007": ("+531", "Auto Rebalance activity code — constant '+531'"),
        "FM006": ("+450", "File Maintenance activity code — constant '+450'"),
    }

    # ── Main mapping loop ─────────────────────────────────────
    async def map_domain(
        self,
        engagement_id: str,
        domain_id: str,
        src_tables: list[ParsedTable],
        db: AsyncSession,
        existing_mappings: Optional[list[str]] = None,
    ) -> list[MappingProposal]:
        """
        Map all source fields in the given domain to Frp target fields.
        Returns proposals — does not write to DB (caller does that via save_proposals).
        """
        logger.info("mapper.domain.start", engagement=engagement_id, domain=domain_id)
        proposals: list[MappingProposal] = []

        for table in src_tables:
            for src_field in table.fields:
                if src_field.field_name in (existing_mappings or []):
                    continue  # skip already-mapped fields

                # Check constants first
                proposal = self._check_constant(domain_id, table, src_field)
                if proposal:
                    proposals.append(proposal)
                    continue

                # RAG retrieval — get candidate Frp fields
                query = rag_service._field_text(table, src_field)
                candidates = await rag_service.retrieve(
                    engagement_id=engagement_id,
                    side="tgt",
                    query_text=query,
                    top_k=self.RAG_TOP_K,
                    db=db,
                )

                if not candidates:
                    proposals.append(self._gap_proposal(domain_id, table.name, src_field.field_name))
                    continue

                # LLM reranking for top candidates
                best = await self._llm_rerank(src_field, table, candidates)
                proposal = self._build_proposal(domain_id, table, src_field, best)
                proposals.append(proposal)

        # Apply confidence scoring (P2.2)
        for p in proposals:
            p.status = self._confidence_to_status(p.confidence)

        logger.info(
            "mapper.domain.complete",
            engagement=engagement_id,
            domain=domain_id,
            total=len(proposals),
            auto=sum(1 for p in proposals if p.status == "auto_approved"),
            review=sum(1 for p in proposals if p.status == "review"),
            gap=sum(1 for p in proposals if p.status == "gap"),
        )
        return proposals

    async def save_proposals(
        self,
        engagement_id: str,
        proposals: list[MappingProposal],
        db: AsyncSession,
    ) -> int:
        """Persist proposals to the mapping_registry (MappingEntry table)."""
        count = 0
        for p in proposals:
            entry = MappingEntry(
                engagement_id=engagement_id,
                domain_id=p.domain_id,
                src_table=p.src_table,
                src_field=p.src_field,
                src_display=f"{p.src_table}.{p.src_field}",
                tgt_table=p.tgt_table,
                tgt_field=p.tgt_field,
                tgt_display=f"{p.tgt_table} {p.tgt_field}",
                confidence=p.confidence,
                mapping_type=p.mapping_type,
                transform_rule=p.transform_rule,
                is_multi_source=p.is_multi_source,
                multi_sources=p.multi_sources or None,
                is_udf=p.is_udf,
                is_constant=p.is_constant,
                constant_value=p.constant_value or None,
                note=p.note,
                status=p.status,
            )
            db.add(entry)
            count += 1

        db.add(AuditEvent(
            engagement_id=engagement_id,
            event_type="mapping.proposals_saved",
            actor_type="ai",
            actor_id="system",
            summary=f"{count} mapping proposals saved",
            detail={
                "total": count,
                "auto_approved": sum(1 for p in proposals if p.status == "auto_approved"),
                "review": sum(1 for p in proposals if p.status == "review"),
                "gap": sum(1 for p in proposals if p.status == "gap"),
            },
        ))
        await db.commit()
        return count

    # ── LLM reranking (Claude) ────────────────────────────────
    async def _llm_rerank(
        self,
        src_field: ParsedField,
        table: ParsedTable,
        candidates: list[FieldCandidate],
    ) -> FieldCandidate:
        """
        Ask Claude to pick the best Frp target field from the RAG candidates.
        Falls back to top RAG result if LLM call fails.
        """
        top5 = candidates[:5]
        prompt = self._build_rerank_prompt(src_field, table, top5)

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            msg = await client.messages.create(
                model=settings.claude_model,
                max_tokens=512,
                system=(
                    "You are a pension data migration expert. "
                    "Given a Relius source field and candidate Frp target fields, "
                    "return ONLY a JSON object: "
                    '{\"best_index\": <0-4>, \"confidence\": <0-100>, '
                    '"mapping_type\": \"direct|transform|crosswalk|composite\", '
                    '"transform_rule\": \"\", \"note\": \"\"}'
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:-1])
            result = json.loads(raw)
            best_idx = max(0, min(int(result.get("best_index", 0)), len(top5) - 1))
            best = top5[best_idx]
            # Override combined_score with LLM confidence
            best.combined_score = float(result.get("confidence", best.combined_score * 100)) / 100
            return best

        except Exception as exc:
            logger.warning("mapper.llm_rerank.failed", error=str(exc))
            return top5[0]  # fall back to top RAG result

    @staticmethod
    def _build_rerank_prompt(
        src_field: ParsedField,
        table: ParsedTable,
        candidates: list[FieldCandidate],
    ) -> str:
        src_text = (
            f"Source field: {table.name}.{src_field.field_name}\n"
            f"Type: {src_field.data_type}\n"
            f"Description: {src_field.description or '(none)'}\n"
        )
        cand_text = "\n".join(
            f"{i}. {c.table_name}.{c.field_name} | {c.data_type} | {c.description[:80]}"
            for i, c in enumerate(candidates)
        )
        return (
            f"Relius source field:\n{src_text}\n\n"
            f"Candidate Frp target fields (index 0–{len(candidates)-1}):\n{cand_text}\n\n"
            "Pick the best match. Return JSON only."
        )

    # ── Helpers ───────────────────────────────────────────────
    def _check_constant(
        self, domain_id: str, table: ParsedTable, field: ParsedField
    ) -> Optional[MappingProposal]:
        if field.field_name.upper() in self.CONSTANTS:
            val, note = self.CONSTANTS[field.field_name.upper()]
            return MappingProposal(
                domain_id=domain_id,
                src_table=table.name,
                src_field=field.field_name,
                tgt_table="CONSTANTS",
                tgt_field=field.field_name,
                confidence=100,
                mapping_type="constant",
                constant_value=val,
                is_constant=True,
                note=note,
                status="auto_approved",
            )
        return None

    def _build_proposal(
        self,
        domain_id: str,
        table: ParsedTable,
        src_field: ParsedField,
        best: FieldCandidate,
    ) -> MappingProposal:
        confidence = int(best.combined_score * 100)
        return MappingProposal(
            domain_id=domain_id,
            src_table=table.name,
            src_field=src_field.field_name,
            tgt_table=best.table_name,
            tgt_field=best.field_name,
            confidence=confidence,
            mapping_type="direct",
            note=f"RAG score: {best.vector_score:.2f} vec + {best.bm25_score:.2f} bm25",
        )

    @staticmethod
    def _gap_proposal(domain_id: str, table_name: str, field_name: str) -> MappingProposal:
        return MappingProposal(
            domain_id=domain_id,
            src_table=table_name,
            src_field=field_name,
            tgt_table="",
            tgt_field="",
            confidence=0,
            mapping_type="gap",
            note="No candidate Frp field found — SME must define manually",
            status="gap",
        )

    @staticmethod
    def _confidence_to_status(confidence: int) -> str:
        """P2.2 confidence band routing."""
        if confidence >= 85:
            return "auto_approved"
        elif confidence >= 60:
            return "review"
        else:
            return "gap"


# Module-level singleton
semantic_mapper = SemanticMapper()
