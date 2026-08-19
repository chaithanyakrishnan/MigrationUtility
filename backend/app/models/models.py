"""
app/models/models.py
SQLAlchemy ORM models for MigrateIQ.
All tables in one file for clarity during early build; split by domain later.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, Float,
    ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


# ── pgvector type (registered when extension is loaded) ───────
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_DIM = 768  # all-mpnet-base-v2 output dimension
    _has_pgvector = True
except ImportError:
    Vector = None
    VECTOR_DIM = 768
    _has_pgvector = False


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ── Engagement ────────────────────────────────────────────────
class Engagement(Base):
    """Top-level container for a single Relius → Frp migration."""
    __tablename__ = "engagements"

    id          = Column(String(), primary_key=True, default=_uuid)
    name        = Column(String(255), nullable=False)
    client_name = Column(String(255), nullable=False)
    status      = Column(
        String(50),
        default="active", nullable=False,
    )
    current_step  = Column(Integer, default=1, nullable=False)  # 1–8
    max_unlocked  = Column(Integer, default=1, nullable=False)  # highest step reached
    relius_version = Column(String(50))   # e.g. "19.3"
    frp_version   = Column(String(50))   # e.g. "2024.2"
    created_by    = Column(String(255), nullable=False)
    created_at    = Column(DateTime, default=_now, nullable=False)
    updated_at    = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    # relationships
    schema_files  = relationship("SchemaFile",     back_populates="engagement", cascade="all, delete-orphan")
    domain_reviews = relationship("DomainReview",  back_populates="engagement", cascade="all, delete-orphan")
    mappings       = relationship("MappingEntry",  back_populates="engagement", cascade="all, delete-orphan")
    etl_artefacts  = relationship("ETLArtefact",   back_populates="engagement", cascade="all, delete-orphan")
    audit_events   = relationship("AuditEvent",    back_populates="engagement")


# ── Knowledge Bases (v5 KB architecture) ──────────────────────
class KnowledgeBase(Base):
    """
    A reusable, one-time Knowledge Base — either the Relius source catalogue
    or the Frp target catalogue (records + transaction-card layouts + load
    order + constants). Migration projects draw on these instead of
    re-uploading schemas. One row per kind.
    """
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        UniqueConstraint("kind", name="uq_kb_kind"),
    )

    id         = Column(String(), primary_key=True, default=_uuid)
    kind       = Column(String(20), nullable=False)   # "relius" | "frp"
    status     = Column(String(20), default="draft", nullable=False)  # draft | built
    version    = Column(String(50), default="v1", nullable=False)
    # relius: {tables, domains, fields}
    # frp:   {records, elements, txn_count, txn_fields}
    stats      = Column(JSONB, default=dict)
    # Frp-only extras: load order + constants registry live on the KB itself.
    load_order = Column(JSONB)   # ordered list of {seq, record, type, reason}
    constants  = Column(JSONB)   # list of {code, record, required_value, status}
    built_at   = Column(DateTime)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    relius_domains = relationship("KBReliusDomain",     back_populates="kb", cascade="all, delete-orphan")
    frp_records   = relationship("KBFrpRecord",       back_populates="kb", cascade="all, delete-orphan")
    txn_cards      = relationship("KBTransactionCard",  back_populates="kb", cascade="all, delete-orphan")


class KBReliusDomain(Base):
    """A business domain in the Relius KB (Plan, Participant, Loans, …)."""
    __tablename__ = "kb_relius_domains"
    __table_args__ = (
        Index("ix_kb_relius_domain_kb", "kb_id"),
    )

    id           = Column(String(), primary_key=True, default=_uuid)
    kb_id        = Column(String(), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    domain_id    = Column(String(100), nullable=False)   # "plan", "part", …
    name         = Column(String(255), nullable=False)
    icon         = Column(String(16))
    table_count  = Column(Integer, default=0)
    row_estimate = Column(String(50))
    completeness = Column(Integer, default=0)
    tables       = Column(JSONB)   # list of table names
    approved     = Column(Boolean, default=False, nullable=False)
    sort_order   = Column(Integer, default=0)

    kb     = relationship("KnowledgeBase", back_populates="relius_domains")
    fields = relationship("KBReliusField", back_populates="domain", cascade="all, delete-orphan")


class KBReliusField(Base):
    """One field catalogued under a Relius KB domain."""
    __tablename__ = "kb_relius_fields"
    __table_args__ = (
        Index("ix_kb_relius_field_domain", "domain_id"),
    )

    id          = Column(String(), primary_key=True, default=_uuid)
    domain_id   = Column(String(), ForeignKey("kb_relius_domains.id", ondelete="CASCADE"), nullable=False)
    table_name  = Column(String(255), nullable=False)
    field_name  = Column(String(255), nullable=False)
    display_name = Column(String(255))
    data_type   = Column(String(100))
    description = Column(Text)
    is_key      = Column(Boolean, default=False)
    included    = Column(Boolean, default=True)
    approved    = Column(Boolean, default=False)
    sort_order  = Column(Integer, default=0)

    domain = relationship("KBReliusDomain", back_populates="fields")


class KBFrpRecord(Base):
    """An Frp record group (Participant Header, Plan Record, HIVR, …)."""
    __tablename__ = "kb_frp_records"
    __table_args__ = (
        Index("ix_kb_frp_record_kb", "kb_id"),
    )

    id            = Column(String(), primary_key=True, default=_uuid)
    kb_id         = Column(String(), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    record_id     = Column(String(100), nullable=False)   # "addr", "am", …
    prefix        = Column(String(20))                     # "AA", "PL", "BR"
    name          = Column(String(255), nullable=False)
    icon          = Column(String(16))
    category      = Column(String(100))
    category_color = Column(String(20))
    description   = Column(Text)
    approved      = Column(Boolean, default=False, nullable=False)
    sort_order    = Column(Integer, default=0)

    kb     = relationship("KnowledgeBase", back_populates="frp_records")
    fields = relationship("KBFrpField", back_populates="record", cascade="all, delete-orphan")


class KBFrpField(Base):
    """A data element within an Frp record."""
    __tablename__ = "kb_frp_fields"
    __table_args__ = (
        Index("ix_kb_frp_field_record", "record_id"),
    )

    id           = Column(String(), primary_key=True, default=_uuid)
    record_id    = Column(String(), ForeignKey("kb_frp_records.id", ondelete="CASCADE"), nullable=False)
    code         = Column(String(50), nullable=False)   # "AA005"
    name         = Column(String(255), nullable=False)
    description  = Column(Text)
    is_key       = Column(Boolean, default=False)
    legal_values = Column(JSONB)   # list of {v, l}
    included     = Column(Boolean, default=True)
    approved     = Column(Boolean, default=False)
    sort_order   = Column(Integer, default=0)

    record = relationship("KBFrpRecord", back_populates="fields")


class KBTransactionCard(Base):
    """An Frp transaction card (T-code) with a fixed-width layout spec."""
    __tablename__ = "kb_transaction_cards"
    __table_args__ = (
        Index("ix_kb_txn_card_kb", "kb_id"),
    )

    id            = Column(String(), primary_key=True, default=_uuid)
    kb_id         = Column(String(), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    code          = Column(String(20), nullable=False)   # "T813"
    name          = Column(String(255))
    category      = Column(String(100))                   # "participant", "loans", …
    icon          = Column(String(16))
    has_layout    = Column(Boolean, default=False)        # confirmed fixed-width spec?
    record_length = Column(Integer, default=110)
    note          = Column(Text)
    approved      = Column(Boolean, default=False, nullable=False)
    selected      = Column(Boolean, default=False)        # in the KB scope
    sort_order    = Column(Integer, default=0)

    kb     = relationship("KnowledgeBase", back_populates="txn_cards")
    fields = relationship("KBTransactionCardField", back_populates="card", cascade="all, delete-orphan")


class KBTransactionCardField(Base):
    """One fixed-width column in a transaction card layout."""
    __tablename__ = "kb_transaction_card_fields"
    __table_args__ = (
        Index("ix_kb_txn_field_card", "card_id"),
    )

    id          = Column(String(), primary_key=True, default=_uuid)
    card_id     = Column(String(), ForeignKey("kb_transaction_cards.id", ondelete="CASCADE"), nullable=False)
    sub_card    = Column(String(10), default="01")   # "01", "02", "0X", "00"
    code        = Column(String(50), nullable=False)  # "TRAN-CODE"
    name        = Column(String(255))
    col_range   = Column(String(20))   # "1-3"
    picture     = Column(String(50))   # "X(3)"
    req_opt     = Column(String(10))   # "Req" | "Opt"
    src_guess   = Column(String(255))  # AI-proposed Relius source ("CONST", "EELOAN.LOANNUM")
    confidence  = Column(Integer)
    field_type  = Column(String(50))   # direct | crosswalk | derived | constant | transform
    note        = Column(Text)
    sort_order  = Column(Integer, default=0)

    card = relationship("KBTransactionCard", back_populates="fields")


# ── Migration project (v5 mig flow) ───────────────────────────
class ProjectState(Base):
    """
    Per-engagement migration-project state: which Relius tables are in scope,
    which transaction cards are approved, and whether mappings were seeded.
    One row per engagement (the migration project).
    """
    __tablename__ = "project_state"
    __table_args__ = (
        UniqueConstraint("engagement_id", name="uq_project_state"),
    )

    id              = Column(String(), primary_key=True, default=_uuid)
    engagement_id   = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    selected_tables = Column(JSONB)   # list of Relius table names in scope
    approved_cards  = Column(JSONB)   # list of approved transaction-card codes
    mapping_seeded  = Column(Boolean, default=False, nullable=False)
    created_at      = Column(DateTime, default=_now, nullable=False)
    updated_at      = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class ProjectMapping(Base):
    """
    An AI-proposed field mapping for a migration project, with the Frp
    transaction card (T-code) it feeds. SME can edit the Frp record/target/
    T-code and confirm. Separate from the cross-engagement MappingEntry registry.
    """
    __tablename__ = "project_mappings"
    __table_args__ = (
        Index("ix_project_mapping_eng", "engagement_id"),
    )

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    domain_id     = Column(String(100))
    src_table     = Column(String(255), nullable=False)
    src_field     = Column(String(255), nullable=False)
    frp_record   = Column(String(255))   # "Participant Header"
    tgt_display   = Column(String(512))    # "PH005 Plan ID"
    txn_code      = Column(String(20))     # assigned T-code (nullable = unassigned)
    confidence    = Column(Integer, default=0)
    mapping_type  = Column(String(50))
    note          = Column(Text)
    is_multi      = Column(Boolean, default=False)
    approved      = Column(Boolean, default=False, nullable=False)
    # SME overrides (null = use AI default)
    frp_override = Column(String(255))
    tgt_override  = Column(String(512))
    txn_override  = Column(String(20))     # "" = explicitly unassigned
    sort_order    = Column(Integer, default=0)


class ProjectExport(Base):
    """Generated fixed-width Frp transaction-card output file for a batch run."""
    __tablename__ = "project_exports"

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    filename      = Column(String(512), nullable=False)
    content       = Column(Text)          # the fixed-width .txt payload
    line_count    = Column(Integer, default=0)
    files_read    = Column(Integer, default=0)
    manifest      = Column(JSONB)         # per-line description
    created_at    = Column(DateTime, default=_now, nullable=False)


# ── Schema files (uploaded by SME) ────────────────────────────
class SchemaFile(Base):
    """Uploaded schema export file (Relius DDL, Frp data dict, etc.)."""
    __tablename__ = "schema_files"

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    side          = Column(String(50), nullable=False)  # relius=src, frp=tgt
    filename      = Column(String(512), nullable=False)
    file_type     = Column(String(50))   # sql, json, xlsx, pdf, docx, txt
    size_bytes    = Column(BigInteger)
    s3_key        = Column(String(1024))  # where the file lives in S3
    parse_status  = Column(
        String(50),
        default="pending", nullable=False,
    )
    parse_result  = Column(JSONB)  # {tables: N, fields: N, domains: N, fk_count: N}
    parse_error   = Column(Text)
    origin        = Column(String(50), default="upload", nullable=False)  # "upload" | "library"
    uploaded_by   = Column(String(255), nullable=False)
    uploaded_at   = Column(DateTime, default=_now, nullable=False)

    engagement = relationship("Engagement", back_populates="schema_files")


# ── Domain review (Screen 2 — Relius Schema Review) ───────────
class DomainReview(Base):
    """SME review notes for a Relius or Frp domain."""
    __tablename__ = "domain_reviews"
    __table_args__ = (
        UniqueConstraint("engagement_id", "domain_id", "side", name="uq_domain_review"),
    )

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    side          = Column(String(50), nullable=False)
    domain_id     = Column(String(100), nullable=False)  # e.g. "plan", "part", "frp-hivr"
    approved      = Column(Boolean, default=False, nullable=False)
    completeness  = Column(Integer)  # 0–100
    field_edits   = Column(JSONB)    # list of {field, old_type, new_type, old_desc, new_desc}
    include_fields = Column(JSONB)   # list of field names explicitly included
    exclude_fields = Column(JSONB)   # list of field names explicitly excluded
    reviewed_by   = Column(String(255))
    reviewed_at   = Column(DateTime)
    created_at    = Column(DateTime, default=_now, nullable=False)
    updated_at    = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    engagement = relationship("Engagement", back_populates="domain_reviews")


# ── Field embeddings (A1 RAG knowledge base) ──────────────────
class FieldEmbedding(Base):
    """Vector embedding for a schema field — powers semantic mapping."""
    __tablename__ = "field_embeddings"

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    side          = Column(String(50), nullable=False)
    table_name    = Column(String(255), nullable=False)
    field_name    = Column(String(255), nullable=False)
    domain_id     = Column(String(100))
    data_type     = Column(String(100))
    description   = Column(Text)
    # Vector column — only created if pgvector is installed
    embedding     = Column(Vector(VECTOR_DIM)) if _has_pgvector else Column(JSONB)
    embedding_version = Column(String(50), default="v1")
    created_at    = Column(DateTime, default=_now, nullable=False)
    updated_at    = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    __table_args__ = (
        Index("ix_field_embed_engagement", "engagement_id"),
        Index("ix_field_embed_side_table", "engagement_id", "side", "table_name"),
    )


# ── Mapping entries (P2.3 mapping registry) ───────────────────
class MappingEntry(Base):
    """A single source→target field mapping with confidence and approval."""
    __tablename__ = "mapping_entries"
    __table_args__ = (
        UniqueConstraint("engagement_id", "src_table", "src_field", "tgt_table", "tgt_field",
                         name="uq_mapping_entry"),
        Index("ix_mapping_engagement_domain", "engagement_id", "domain_id"),
        Index("ix_mapping_confidence", "confidence"),
    )

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    domain_id     = Column(String(100), nullable=False)
    # Source (Relius)
    src_table     = Column(String(255), nullable=False)
    src_field     = Column(String(255), nullable=False)
    src_display   = Column(String(512))  # "PERSON.LASTNAM"
    # Target (Frp)
    tgt_table     = Column(String(255), nullable=False)
    tgt_field     = Column(String(255), nullable=False)
    tgt_display   = Column(String(512))  # "PH100 Last Name"
    # AI scoring
    confidence    = Column(Integer, nullable=False)  # 0–100
    mapping_type  = Column(String(50))   # direct | transform | crosswalk | composite | constant
    transform_rule = Column(Text)        # YAML rule or free-text
    is_multi_source = Column(Boolean, default=False)
    multi_sources  = Column(JSONB)       # list of {table, field} for composite mappings
    is_udf         = Column(Boolean, default=False)
    is_constant    = Column(Boolean, default=False)
    constant_value = Column(String(255))
    note          = Column(Text)
    # Approval
    status        = Column(
        String(50),
        default="pending", nullable=False,
    )
    approved_by   = Column(String(255))
    approved_at   = Column(DateTime)
    # Lineage
    git_commit_sha = Column(String(64))   # commit in mapping registry repo
    i4_source      = Column(Boolean, default=False)  # came from I4 learning store
    created_at    = Column(DateTime, default=_now, nullable=False)
    updated_at    = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    engagement = relationship("Engagement", back_populates="mappings")


# ── Control files ─────────────────────────────────────────────
class ControlFile(Base):
    """Uploaded Frp control file (.txt) for a migration engagement."""
    __tablename__ = "control_files"

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    filename      = Column(String(512), nullable=False)
    file_type     = Column(String(100))  # "Ct_Vesting", "Ct_Loan" etc.
    s3_key        = Column(String(1024))
    line_count    = Column(Integer)
    parsed_kv     = Column(JSONB)        # parsed key-value pairs from the file
    env_specific_flags = Column(JSONB)   # keys flagged as environment-specific
    uploaded_by   = Column(String(255), nullable=False)
    uploaded_at   = Column(DateTime, default=_now, nullable=False)


# ── ETL artefacts (generated scripts) ─────────────────────────
class ETLArtefact(Base):
    """Generated ETL script or format spec for a migration engagement."""
    __tablename__ = "etl_artefacts"

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    artefact_type = Column(String(100), nullable=False)  # "etl_script" | "format_spec" | "recon_report"
    filename      = Column(String(512), nullable=False)
    s3_key        = Column(String(1024))
    content_hash  = Column(String(128))  # SHA-256 of content
    generation_config = Column(JSONB)    # format, mode, encoding, null_indicator etc.
    generated_by  = Column(String(255))
    generated_at  = Column(DateTime, default=_now, nullable=False)

    engagement = relationship("Engagement", back_populates="etl_artefacts")


# ── Reconciliation results ────────────────────────────────────
class ReconResult(Base):
    """Result of a reconciliation check run."""
    __tablename__ = "recon_results"

    id            = Column(String(), primary_key=True, default=_uuid)
    engagement_id = Column(String(), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    run_id        = Column(String(), default=_uuid, nullable=False)
    check_id      = Column(String(100), nullable=False)  # "row_count_plan", "balance_part" etc.
    check_name    = Column(String(255), nullable=False)
    status        = Column(String(50), nullable=False)
    expected      = Column(Text)
    actual        = Column(Text)
    delta         = Column(Float)
    detail        = Column(JSONB)
    auto_resolved = Column(Boolean, default=False)
    resolution    = Column(Text)
    run_at        = Column(DateTime, default=_now, nullable=False)


# ── Audit events (I3 — append-only) ───────────────────────────
class AuditEvent(Base):
    """
    Immutable audit log. Never update or delete rows.
    Covers all system, AI, and human actions.
    """
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_engagement_ts", "engagement_id", "created_at"),
        Index("ix_audit_event_type", "event_type"),
    )

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    engagement_id = Column(String(), ForeignKey("engagements.id"), nullable=True)
    event_type    = Column(String(100), nullable=False)
    # e.g. "schema.loaded" | "mapping.approved" | "ai.auto_resolved" | "etl.generated" | "cutover.approved"
    actor_type    = Column(String(50), nullable=False)
    actor_id      = Column(String(255))   # user email or "system"
    summary       = Column(Text, nullable=False)
    detail        = Column(JSONB)         # arbitrary structured context
    created_at    = Column(DateTime, server_default=func.now(), nullable=False)

    engagement = relationship("Engagement", back_populates="audit_events")


# ── I4 cross-engagement learning store ───────────────────────
class LearnedMapping(Base):
    """
    Cross-engagement learning store (I4).
    Stores approved mapping decisions indexed by plan type for reuse.
    No client PII — schema metadata only.
    """
    __tablename__ = "learned_mappings"
    __table_args__ = (
        Index("ix_learned_plan_type", "plan_type", "relius_version"),
    )

    id              = Column(String(), primary_key=True, default=_uuid)
    plan_type       = Column(String(100), nullable=False)   # "401k_standard", "safe_harbour" etc.
    relius_version  = Column(String(50))
    frp_version    = Column(String(50))
    src_table       = Column(String(255), nullable=False)
    src_field       = Column(String(255), nullable=False)
    tgt_table       = Column(String(255), nullable=False)
    tgt_field       = Column(String(255), nullable=False)
    mapping_type    = Column(String(50))
    transform_rule  = Column(Text)
    confidence_prior = Column(Integer)   # suggested starting confidence for new engagements
    approval_count  = Column(Integer, default=1)  # how many times this has been approved
    rejection_count = Column(Integer, default=0)
    last_seen_at    = Column(DateTime, default=_now, nullable=False)
    created_at      = Column(DateTime, default=_now, nullable=False)

    # Vector embedding for I4 semantic retrieval
    embedding = Column(Vector(VECTOR_DIM)) if _has_pgvector else Column(JSONB)


# ── Persistent schema understanding library (cross-engagement) ─
class SchemaKnowledge(Base):
    """
    Canonical, cross-engagement understanding of a vendor-product schema
    (Relius or Frp), keyed by product + version. Accumulates schema metadata
    from every engagement so it can be reused on the next implementation.
    No client data/PII — schema metadata only.
    """
    __tablename__ = "schema_knowledge"
    __table_args__ = (
        UniqueConstraint("product", "version", name="uq_schema_knowledge"),
    )

    id                = Column(String(), primary_key=True, default=_uuid)
    product           = Column(String(50), nullable=False)   # "relius" | "frp"
    version           = Column(String(50), nullable=False, default="unspecified")
    table_count       = Column(Integer, default=0, nullable=False)
    field_count       = Column(Integer, default=0, nullable=False)
    domain_count      = Column(Integer, default=0, nullable=False)
    contributor_count = Column(Integer, default=0, nullable=False)  # distinct engagements merged
    notes             = Column(Text)
    created_at        = Column(DateTime, default=_now, nullable=False)
    updated_at        = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    fields = relationship("SchemaKnowledgeField", back_populates="knowledge",
                          cascade="all, delete-orphan")


class SchemaKnowledgeField(Base):
    """One canonical field in the schema understanding library."""
    __tablename__ = "schema_knowledge_fields"
    __table_args__ = (
        UniqueConstraint("knowledge_id", "table_name", "field_name", name="uq_skf"),
        Index("ix_skf_knowledge", "knowledge_id"),
        Index("ix_skf_knowledge_table", "knowledge_id", "table_name"),
    )

    id            = Column(String(), primary_key=True, default=_uuid)
    knowledge_id  = Column(String(), ForeignKey("schema_knowledge.id", ondelete="CASCADE"), nullable=False)
    table_name    = Column(String(255), nullable=False)
    field_name    = Column(String(255), nullable=False)
    data_type     = Column(String(100))
    description   = Column(Text)
    domain_id     = Column(String(100))
    is_pk         = Column(Boolean, default=False)
    is_fk         = Column(Boolean, default=False)
    references    = Column(String(512))
    occurrence_count = Column(Integer, default=1, nullable=False)  # how many engagements carried this field
    last_updated  = Column(DateTime, default=_now, onupdate=_now, nullable=False)
    # Stored as a JSON list to match the JSONB column the migrations create.
    # (Vector search uses the text fallback in rag.py, so no pgvector type here —
    # declaring Vector over a JSONB column breaks reads with the pgvector driver.)
    embedding     = Column(JSONB)

    knowledge = relationship("SchemaKnowledge", back_populates="fields")
