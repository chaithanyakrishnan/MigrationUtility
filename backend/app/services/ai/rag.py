"""
app/services/ai/rag.py
A1 — Knowledge Base & RAG Service

Manages field-level embeddings for Relius and Frp schemas.
Provides retrieval for semantic mapping (P2.1).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, List

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

# numpy imported lazily — avoids crash if not installed
_np = None
def _get_np():
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np

from app.models.models import FieldEmbedding
from app.services.schema.extractor import ParsedField, ParsedTable, SchemaParseResult as ExtractorResult

logger = structlog.get_logger(__name__)

_embedder = None
EMBEDDING_DIM = 768


def _get_embedder():
    """Lazy-load the sentence transformer model. Falls back to hash embedder."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("rag.model.loading")
            _embedder = SentenceTransformer("all-mpnet-base-v2")
            logger.info("rag.model.ready")
        except Exception:
            logger.warning("rag.model.fallback", reason="sentence-transformers not available")
            _embedder = _FallbackEmbedder()
    return _embedder


class _FallbackEmbedder:
    """Hash-based fallback when sentence-transformers is not installed."""
    def encode(self, texts: List[str], **kwargs):
        np = _get_np()
        vectors = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            arr = np.frombuffer(h * 24, dtype=np.uint8)[:EMBEDDING_DIM].astype(np.float32)
            arr = (arr - 127.5) / 127.5
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
            vectors.append(arr)
        return np.array(vectors)


@dataclass
class FieldCandidate:
    table_name: str
    field_name: str
    domain_id: str
    data_type: str
    description: str
    vector_score: float = 0.0
    bm25_score: float = 0.0
    combined_score: float = 0.0


class RAGService:
    VECTOR_WEIGHT = 0.7
    BM25_WEIGHT   = 0.3

    async def embed_schema(
        self,
        engagement_id: str,
        side: str,
        parse_result: ExtractorResult,
        db: AsyncSession,
        domain_map: Optional[dict] = None,
    ) -> int:
        """Generate and store embeddings for all fields in a parsed schema."""
        # Clear existing embeddings for this engagement+side
        await db.execute(
            delete(FieldEmbedding).where(
                FieldEmbedding.engagement_id == engagement_id,
                FieldEmbedding.side == side,
            )
        )
        await db.commit()

        # Collect all fields
        all_fields: List[tuple] = [
            (table, field)
            for table in parse_result.tables
            for field in table.fields
        ]

        if not all_fields:
            logger.warning("rag.embed.no_fields", engagement=engagement_id, side=side)
            return 0

        logger.info("rag.embed.start", engagement=engagement_id, side=side, count=len(all_fields))

        # Build text for each field
        texts = [self._field_text(table, field) for table, field in all_fields]

        # Generate embeddings
        model = _get_embedder()
        try:
            vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
        except Exception as exc:
            logger.error("rag.embed.encode_failed", error=str(exc))
            return 0

        # Persist in batches of 100 to avoid huge transactions
        count = 0
        BATCH = 100
        for batch_start in range(0, len(all_fields), BATCH):
            batch_fields  = all_fields[batch_start:batch_start + BATCH]
            batch_vectors = vectors[batch_start:batch_start + BATCH]

            for (table, field), vector in zip(batch_fields, batch_vectors):
                domain_id = (domain_map or {}).get(table.name.upper(), "unknown")
                # Store embedding as JSON list (JSONB column — works without pgvector)
                embedding_list = vector.tolist()
                fe = FieldEmbedding(
                    engagement_id=engagement_id,
                    side=side,
                    table_name=table.name.upper(),
                    field_name=field.field_name.upper(),
                    domain_id=domain_id,
                    data_type=field.data_type or "",
                    description=field.description or "",
                    embedding=embedding_list,
                )
                db.add(fe)
                count += 1

            await db.commit()

        logger.info("rag.embed.complete", engagement=engagement_id, side=side, count=count)
        return count

    async def count(self, engagement_id: str, side: str, db: AsyncSession) -> int:
        from sqlalchemy import func
        result = await db.execute(
            select(func.count(FieldEmbedding.id)).where(
                FieldEmbedding.engagement_id == engagement_id,
                FieldEmbedding.side == side,
            )
        )
        return result.scalar_one() or 0

    async def clear(self, engagement_id: str, side: str, db: AsyncSession) -> int:
        result = await db.execute(
            delete(FieldEmbedding).where(
                FieldEmbedding.engagement_id == engagement_id,
                FieldEmbedding.side == side,
            )
        )
        await db.commit()
        return result.rowcount

    async def retrieve(
        self,
        engagement_id: str,
        side: str,
        query_text: str,
        top_k: int = 20,
        db: AsyncSession = None,
    ) -> List[FieldCandidate]:
        """
        Retrieve top_k most similar fields for a query.
        Uses pgvector if available, otherwise falls back to text match.
        """
        # Always use text fallback for now (pgvector not installed)
        return await self._text_retrieve(engagement_id, side, query_text, top_k, db)

    async def _text_retrieve(
        self,
        engagement_id: str,
        side: str,
        query_text: str,
        top_k: int,
        db: AsyncSession,
    ) -> List[FieldCandidate]:
        """Text-based retrieval — matches on field name and description."""
        rows = await db.execute(
            select(FieldEmbedding).where(
                FieldEmbedding.engagement_id == engagement_id,
                FieldEmbedding.side == side,
            ).limit(top_k * 10)
        )
        all_fields = rows.scalars().all()

        query_lower = query_text.lower()
        query_words = set(query_lower.split())
        scored = []
        for fe in all_fields:
            haystack = f"{fe.field_name} {fe.table_name} {fe.description or ''}".lower()
            matches = sum(1 for w in query_words if w in haystack)
            score = matches / max(len(query_words), 1)
            scored.append((score, fe))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            FieldCandidate(
                table_name=fe.table_name,
                field_name=fe.field_name,
                domain_id=fe.domain_id or "unknown",
                data_type=fe.data_type or "",
                description=fe.description or "",
                vector_score=score,
                combined_score=score,
            )
            for score, fe in scored[:top_k]
        ]

    @staticmethod
    def _field_text(table: ParsedTable, field: ParsedField) -> str:
        parts = [f"table:{table.name}", f"field:{field.field_name}"]
        if field.data_type:
            parts.append(f"type:{field.data_type}")
        if field.description:
            parts.append(f"description:{field.description}")
        return " ".join(parts)


rag_service = RAGService()
