"""
app/schemas/schemas.py
Pydantic v2 schemas for all API request and response bodies.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# ── Engagement ────────────────────────────────────────────────
class EngagementCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    client_name: str = Field(..., min_length=2, max_length=255)
    relius_version: Optional[str] = None
    frp_version: Optional[str] = None


class EngagementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    client_name: str
    status: str
    current_step: int
    max_unlocked: int
    relius_version: Optional[str]
    frp_version: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


class EngagementStepUpdate(BaseModel):
    # Flow-relative step within the migration project (mig flow has 4 steps).
    current_step: int = Field(..., ge=1, le=20)
    max_unlocked: int = Field(..., ge=1, le=20)


# ── Knowledge Bases (v5 KB architecture) ──────────────────────
class KnowledgeBaseSummary(BaseModel):
    """Lightweight KB status used by the Home launchpad."""
    kind: str                       # "relius" | "frp"
    status: str = "draft"           # draft | built
    built: bool = False
    version: str = "v1"
    stats: dict[str, Any] = {}
    built_at: Optional[datetime] = None


class KnowledgeBasesStatus(BaseModel):
    relius: KnowledgeBaseSummary
    frp: KnowledgeBaseSummary
    both_built: bool = False


# ── Relius KB ─────────────────────────────────────────────────
class KBReliusFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    table_name: str
    field_name: str
    display_name: Optional[str] = None
    data_type: Optional[str] = None
    description: Optional[str] = None
    is_key: bool = False
    included: bool = True
    approved: bool = False


class KBReliusDomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    domain_id: str
    name: str
    icon: Optional[str] = None
    table_count: int = 0
    row_estimate: Optional[str] = None
    completeness: int = 0
    tables: list[str] = []
    approved: bool = False
    fields: list[KBReliusFieldOut] = []


class KBReliusCatalog(BaseModel):
    kind: str = "relius"
    status: str = "draft"
    stats: dict[str, Any] = {}
    domains: list[KBReliusDomainOut] = []


class KBReliusFieldReview(BaseModel):
    id: str
    data_type: Optional[str] = None
    description: Optional[str] = None
    included: bool = True
    approved: bool = False


class KBReliusDomainReview(BaseModel):
    approved: bool = False
    fields: list[KBReliusFieldReview] = []


# ── Frp KB ───────────────────────────────────────────────────
class KBFrpFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    description: Optional[str] = None
    is_key: bool = False
    legal_values: Optional[list[dict]] = None
    included: bool = True
    approved: bool = False
    # Extraction-confidence (0–100) derived from the parsed field, so SMEs can
    # focus review on low-confidence rows. `confidence_flags` lists the reasons.
    confidence: int = 100
    confidence_flags: list[str] = []


class KBFrpRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    record_id: str
    prefix: Optional[str] = None
    name: str
    icon: Optional[str] = None
    category: Optional[str] = None
    category_color: Optional[str] = None
    description: Optional[str] = None
    approved: bool = False
    fields: list[KBFrpFieldOut] = []
    # Roll-ups so the record header can flag how much needs attention.
    low_conf_count: int = 0
    avg_confidence: int = 100


class KBFrpCatalog(BaseModel):
    kind: str = "frp"
    status: str = "draft"
    stats: dict[str, Any] = {}
    records: list[KBFrpRecordOut] = []


class KBTxnFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sub_card: str
    code: str
    name: Optional[str] = None
    col_range: Optional[str] = None
    picture: Optional[str] = None
    req_opt: Optional[str] = None
    src_guess: Optional[str] = None
    confidence: Optional[int] = None
    field_type: Optional[str] = None
    note: Optional[str] = None


class KBTxnCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    has_layout: bool = False
    record_length: int = 110
    note: Optional[str] = None
    approved: bool = False
    selected: bool = False
    fields: list[KBTxnFieldOut] = []


class KBFrpTxnCatalog(BaseModel):
    status: str = "draft"
    cards: list[KBTxnCardOut] = []
    load_order: list[dict] = []
    constants: list[dict] = []


class KBFrpFieldReview(BaseModel):
    id: str
    description: Optional[str] = None
    included: bool = True
    approved: bool = False


class KBFrpRecordReview(BaseModel):
    approved: bool = False
    fields: list[KBFrpFieldReview] = []


class KBTxnFieldReview(BaseModel):
    id: str
    name: Optional[str] = None


class KBTxnCardReview(BaseModel):
    approved: bool = False
    fields: list[KBTxnFieldReview] = []


# ── Migration project (mig flow) ──────────────────────────────
class ProjectStateOut(BaseModel):
    selected_tables: list[str] = []
    approved_cards: list[str] = []
    mapping_seeded: bool = False


class ProjectTablesUpdate(BaseModel):
    tables: list[str] = []


class ProjectMappingOut(BaseModel):
    id: str
    domain_id: Optional[str] = None
    src_table: str
    src_field: str
    frp: str                      # effective Frp record label
    tgt: str                       # effective target display
    txn: Optional[str] = None      # effective T-code (None = unassigned)
    confidence: int = 0
    mapping_type: Optional[str] = None
    note: Optional[str] = None
    is_multi: bool = False
    approved: bool = False
    frp_modified: bool = False
    tgt_modified: bool = False
    txn_modified: bool = False


class ProjectMappingPatch(BaseModel):
    approved: Optional[bool] = None
    frp_override: Optional[str] = None
    tgt_override: Optional[str] = None
    txn_override: Optional[str] = None   # "" = explicitly unassigned


class ProjectCardFieldOut(BaseModel):
    col_range: Optional[str] = None
    length: Optional[int] = None
    frp_name: str
    relius_source: str
    field_type: Optional[str] = None
    note: Optional[str] = None


class ProjectCardOut(BaseModel):
    code: str
    name: Optional[str] = None
    has_layout: bool = False
    record_length: int = 110
    approved: bool = False
    fields: list[ProjectCardFieldOut] = []


class ProjectBatchResult(BaseModel):
    filename: str
    files_read: int = 0
    line_count: int = 0
    manifest: list[str] = []


# ── Schema upload ─────────────────────────────────────────────
class SchemaFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    engagement_id: str
    side: str
    filename: str
    file_type: Optional[str]
    size_bytes: Optional[int]
    parse_status: str
    parse_result: Optional[dict]
    parse_error: Optional[str] = None
    uploaded_at: datetime


class SchemaParseResult(BaseModel):
    """Result returned after parsing a schema file."""
    tables: int = 0
    fields: int = 0
    domains: int = 0
    fk_count: int = 0
    domain_breakdown: dict[str, int] = {}
    sample_tables: list[str] = []
    warnings: list[str] = []


# ── Domain review ─────────────────────────────────────────────
class DomainReviewCreate(BaseModel):
    domain_id: str
    side: str = "src"  # src | tgt
    approved: bool = False
    field_edits: list[dict] = []
    include_fields: list[str] = []
    exclude_fields: list[str] = []


class DomainReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    engagement_id: str
    domain_id: str
    side: str
    approved: bool
    completeness: Optional[int]
    field_edits: Optional[list[dict]] = []
    include_fields: Optional[list[str]] = []
    exclude_fields: Optional[list[str]] = []
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]


# ── Mapping ───────────────────────────────────────────────────
class MappingEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    domain_id: str
    src_table: str
    src_field: str
    src_display: Optional[str]
    tgt_table: str
    tgt_field: str
    tgt_display: Optional[str]
    confidence: int
    mapping_type: Optional[str]
    transform_rule: Optional[str]
    is_multi_source: bool
    multi_sources: Optional[list]
    is_udf: bool
    is_constant: bool
    constant_value: Optional[str]
    note: Optional[str]
    status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]


class MappingApproval(BaseModel):
    """Bulk approve/reject mapping entries."""
    mapping_ids: list[str]
    action: str = Field(..., pattern="^(confirm|reject|reset)$")
    note: Optional[str] = None


class MappingRunRequest(BaseModel):
    """Trigger the AI mapping pipeline for an engagement."""
    domain_ids: Optional[list[str]] = None  # None = all selected domains
    force_rerun: bool = False


class MappingRunStatus(BaseModel):
    engagement_id: str
    status: str  # pending | running | complete | failed
    total_mappings: int = 0
    auto_approved: int = 0
    needs_review: int = 0
    gaps: int = 0
    progress_pct: int = 0
    message: str = ""


# ── ETL generation ────────────────────────────────────────────
class ETLGenerateRequest(BaseModel):
    output_format: str = Field("fixed", pattern="^(fixed|csv|json)$")
    extraction_mode: str = Field("full", pattern="^(full|incremental|delta)$")
    encoding: str = "UTF-8"
    null_indicator: str = ""
    date_format: str = "YYYYMMDD"


class ETLArtefactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    engagement_id: str
    artefact_type: str
    filename: str
    s3_key: Optional[str]
    generated_at: datetime


# ── Reconciliation ────────────────────────────────────────────
class ReconRunRequest(BaseModel):
    checks: Optional[list[str]] = None  # None = run all checks


class ReconCheckResult(BaseModel):
    check_id: str
    check_name: str
    status: str  # pass | fail | warning
    expected: Optional[str]
    actual: Optional[str]
    delta: Optional[float]
    detail: Optional[dict]
    auto_resolved: bool = False
    resolution: Optional[str]


class ReconRunResult(BaseModel):
    run_id: str
    engagement_id: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    auto_resolved: int
    checks: list[ReconCheckResult]


# ── Audit ─────────────────────────────────────────────────────
class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    actor_type: str
    actor_id: Optional[str]
    summary: str
    detail: Optional[dict]
    created_at: datetime


# ── Health ────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    env: str
    db: str = "ok"
    ai: str = "ok"
