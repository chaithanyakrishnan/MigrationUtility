// types/index.ts
// Mirrors backend app/schemas/schemas.py exactly.
// Update both when adding new fields.

// ── Engagement ────────────────────────────────────────────────
export type EngagementStatus = 'active' | 'paused' | 'complete' | 'archived'

export interface Engagement {
  id: string
  name: string
  client_name: string
  status: EngagementStatus
  current_step: number   // 1–8
  max_unlocked: number   // 1–8
  relius_version: string | null
  frp_version: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface EngagementCreate {
  name: string
  client_name: string
  relius_version?: string
  frp_version?: string
}

export interface EngagementStepUpdate {
  current_step: number
  max_unlocked: number
}

// ── Knowledge Bases (v5 KB architecture) ──────────────────────
export type KBKind = 'relius' | 'frp'

export interface KnowledgeBaseSummary {
  kind: KBKind
  status: 'draft' | 'built'
  built: boolean
  version: string
  stats: Record<string, number>
  built_at: string | null
}

export interface KnowledgeBasesStatus {
  relius: KnowledgeBaseSummary
  frp: KnowledgeBaseSummary
  both_built: boolean
}

// ── Relius KB ─────────────────────────────────────────────────
export interface KBReliusField {
  id: string
  table_name: string
  field_name: string
  display_name: string | null
  data_type: string | null
  description: string | null
  is_key: boolean
  included: boolean
  approved: boolean
}

export interface KBReliusDomain {
  id: string
  domain_id: string
  name: string
  icon: string | null
  table_count: number
  row_estimate: string | null
  completeness: number
  tables: string[]
  approved: boolean
  fields: KBReliusField[]
}

export interface KBReliusCatalog {
  kind: 'relius'
  status: 'draft' | 'built'
  stats: Record<string, number>
  domains: KBReliusDomain[]
}

export interface KBReliusFieldReview {
  id: string
  data_type?: string | null
  description?: string | null
  included: boolean
  approved: boolean
}

export interface KBReliusDomainReview {
  approved: boolean
  fields: KBReliusFieldReview[]
}

// ── FRP KB ───────────────────────────────────────────────────
export interface KBLegalValue { v: string; l: string }

export interface KBFrpField {
  id: string
  code: string
  name: string
  description: string | null
  is_key: boolean
  legal_values: KBLegalValue[] | null
  included: boolean
  approved: boolean
  confidence: number          // 0–100 extraction confidence
  confidence_flags: string[]  // reasons the score was docked
}

export interface KBFrpRecord {
  id: string
  record_id: string
  prefix: string | null
  name: string
  icon: string | null
  category: string | null
  category_color: string | null
  description: string | null
  approved: boolean
  fields: KBFrpField[]
  low_conf_count: number
  avg_confidence: number
}

export interface KBFrpCatalog {
  kind: 'frp'
  status: 'draft' | 'built'
  stats: Record<string, number>
  records: KBFrpRecord[]
}

export interface KBFrpFieldReview {
  id: string
  description?: string | null
  included: boolean
  approved: boolean
}

export interface KBFrpRecordReview {
  approved: boolean
  fields: KBFrpFieldReview[]
}

export interface KBTxnField {
  id: string
  sub_card: string
  code: string
  name: string | null
  col_range: string | null
  picture: string | null
  req_opt: string | null
  src_guess: string | null
  confidence: number | null
  field_type: string | null
  note: string | null
}

export interface KBTxnCard {
  id: string
  code: string
  name: string | null
  category: string | null
  icon: string | null
  has_layout: boolean
  record_length: number
  note: string | null
  approved: boolean
  selected: boolean
  fields: KBTxnField[]
}

export interface KBLoadOrderRow { seq: number; record: string; type: string; reason: string }
export interface KBConstant { code: string; record: string; required_value: string; status: string }

export interface KBFrpTxnCatalog {
  status: 'draft' | 'built'
  cards: KBTxnCard[]
  load_order: KBLoadOrderRow[]
  constants: KBConstant[]
}

export interface KBTxnCardReview {
  approved: boolean
  fields: { id: string; name?: string | null }[]
}

// ── Migration project (mig flow) ──────────────────────────────
export interface ProjectState {
  selected_tables: string[]
  approved_cards: string[]
  mapping_seeded: boolean
}

export interface ProjectMapping {
  id: string
  domain_id: string | null
  src_table: string
  src_field: string
  frp: string
  tgt: string
  txn: string | null
  confidence: number
  mapping_type: string | null
  note: string | null
  is_multi: boolean
  approved: boolean
  frp_modified: boolean
  tgt_modified: boolean
  txn_modified: boolean
}

export interface ProjectMappingPatch {
  approved?: boolean
  frp_override?: string
  tgt_override?: string
  txn_override?: string
}

export interface ProjectCardField {
  col_range: string | null
  length: number | null
  frp_name: string
  relius_source: string
  field_type: string | null
  note: string | null
}

export interface ProjectCard {
  code: string
  name: string | null
  has_layout: boolean
  record_length: number
  approved: boolean
  fields: ProjectCardField[]
}

export interface ProjectBatchResult {
  filename: string
  files_read: number
  line_count: number
  manifest: string[]
}

// ── Observability ─────────────────────────────────────────────
export interface ObsEvent {
  id: number
  event_type: string
  actor_type: 'system' | 'ai' | 'sme'
  actor_id: string | null
  summary: string
  created_at: string | null
}

export interface ObservabilityData {
  counts: {
    active_projects: number
    mappings: number
    mappings_approved: number
    audit_events: number
  }
  events: ObsEvent[]
}

// ── Schema ────────────────────────────────────────────────────
export type SchemaParseStatus = 'pending' | 'parsing' | 'complete' | 'failed'
export type SchemaSide = 'src' | 'tgt'

export interface SchemaFile {
  id: string
  engagement_id: string
  side: SchemaSide
  filename: string
  file_type: string | null
  size_bytes: number | null
  parse_status: SchemaParseStatus
  parse_result: SchemaParseResult | null
  parse_error: string | null
  uploaded_at: string
}

export interface SchemaParseResult {
  tables: number
  fields: number
  domains: number
  fk_count: number
  domain_breakdown: Record<string, number>
  sample_tables: string[]
  warnings: string[]
}

// ── Persistent schema understanding library ───────────────────
export interface SchemaKnowledgeSummary {
  exists: boolean
  product?: 'relius' | 'frp'
  version?: string
  table_count?: number
  field_count?: number
  domain_count?: number
  contributor_count?: number
  updated_at?: string | null
}

export interface SchemaKnowledgeField {
  field: string
  type: string
  description: string
  is_pk: boolean
  is_fk: boolean
  occurrences: number
}

export interface SchemaKnowledgeCatalog {
  exists: boolean
  product?: 'relius' | 'frp'
  version?: string
  table_count?: number
  field_count?: number
  domain_count?: number
  tables: { name: string; domain_id: string | null; fields: SchemaKnowledgeField[] }[]
}

// ── Domain review ─────────────────────────────────────────────
export interface DomainReview {
  id: string
  engagement_id: string
  domain_id: string
  side: SchemaSide
  approved: boolean
  completeness: number | null
  field_edits?: FieldEdit[]
  include_fields?: string[]
  exclude_fields?: string[]
  reviewed_by: string | null
  reviewed_at: string | null
}

export interface DomainReviewCreate {
  domain_id: string
  side?: SchemaSide
  approved?: boolean
  field_edits?: FieldEdit[]
  include_fields?: string[]
  exclude_fields?: string[]
}

// One SME-corrected field within a domain. Keyed by table + field.
export interface FieldEdit {
  table: string
  field: string
  type: string
  is_pk: boolean
  is_fk: boolean
  description: string
}

// ── Mapping ───────────────────────────────────────────────────
export type MappingStatus =
  | 'pending' | 'auto_approved' | 'review'
  | 'confirmed' | 'rejected' | 'gap'

export type MappingType =
  | 'direct' | 'transform' | 'crosswalk' | 'composite'
  | 'constant' | 'gap'

export interface MappingEntry {
  id: string
  domain_id: string
  src_table: string
  src_field: string
  src_display: string | null
  tgt_table: string
  tgt_field: string
  tgt_display: string | null
  confidence: number          // 0–100
  mapping_type: MappingType | null
  transform_rule: string | null
  is_multi_source: boolean
  multi_sources: Array<{ table: string; field: string }> | null
  is_udf: boolean
  is_constant: boolean
  constant_value: string | null
  note: string | null
  status: MappingStatus
  approved_by: string | null
  approved_at: string | null
}

export interface MappingApproval {
  mapping_ids: string[]
  action: 'confirm' | 'reject' | 'reset'
  note?: string
}

export interface MappingRunRequest {
  domain_ids?: string[]
  force_rerun?: boolean
}

export interface MappingRunStatus {
  engagement_id: string
  status: 'idle' | 'running' | 'complete' | 'failed'
  total_mappings: number
  auto_approved: number
  needs_review: number
  gaps: number
  progress_pct: number
  message: string
}

// ── ETL ───────────────────────────────────────────────────────
export interface ETLGenerateRequest {
  output_format?: 'fixed' | 'csv' | 'json'
  extraction_mode?: 'full' | 'incremental' | 'delta'
  encoding?: string
  null_indicator?: string
  date_format?: string
}

export interface ETLArtefact {
  id: string
  engagement_id: string
  artefact_type: string
  filename: string
  s3_key: string | null
  generated_at: string
}

export interface ETLArtefactContent extends ETLArtefact {
  content: string
}

export interface ETLGenerateStatus {
  engagement_id: string
  status: 'idle' | 'running' | 'complete' | 'failed'
  progress: number
  message: string
  artefact_count: number
}

// ── Reconciliation ────────────────────────────────────────────
export type ReconStatus = 'pass' | 'fail' | 'warning'
export type ReconCategory = 'A' | 'B' | 'C' | 'D'

export interface ReconCheckResult {
  check_id: string
  check_name: string
  status: ReconStatus
  expected: string | null
  actual: string | null
  delta: number | null
  detail: Record<string, unknown> | null
  auto_resolved: boolean
  resolution: string | null
}

export interface ReconRunResult {
  run_id: string
  engagement_id: string
  total_checks: number
  passed: number
  failed: number
  warnings: number
  auto_resolved: number
  checks: ReconCheckResult[]
}

export interface ReconRunStatus {
  engagement_id: string
  run_id?: string
  status: 'idle' | 'running' | 'complete' | 'failed'
  progress: number
  message: string
  passed?: number
  failed?: number
  warnings?: number
  cutover_ready?: boolean
}

// ── Cutover approval ──────────────────────────────────────────
export interface CutoverApproval {
  approver_name: string
  timestamp: string
  signature: string
}

export interface CutoverStatus {
  engagement_id: string
  approvals_received: Record<string, CutoverApproval>
  pending_approvals: Record<string, string>
  cutover_approved: boolean
}

// ── Audit ─────────────────────────────────────────────────────
export type ActorType = 'system' | 'ai' | 'sme'

export interface AuditEvent {
  id: number
  event_type: string
  actor_type: ActorType
  actor_id: string | null
  summary: string
  detail: Record<string, unknown> | null
  created_at: string
}

// ── UI state types (not from backend) ─────────────────────────
export interface Notification {
  id: string
  message: string
  type: 'teal' | 'green' | 'amber' | 'red'
  timestamp: number
}

export interface StepDef {
  id: number
  label: string
  description: string
}

export const STEPS: StepDef[] = [
  { id: 1, label: 'Relius Schema',    description: 'Upload Relius schema export files' },
  { id: 2, label: 'Relius Review',    description: 'Review and approve Relius domain fields' },
  { id: 3, label: 'FRP Schema',      description: 'Upload FRP data dictionary files' },
  { id: 4, label: 'FRP Review',      description: 'Review FRP target records and field definitions' },
  { id: 5, label: 'Select Domains',   description: 'Choose migration scope and confirm load order' },
  { id: 6, label: 'AI Mapping',       description: 'Review and approve AI field mappings' },
  { id: 7, label: 'ETL Generation',   description: 'Generate ETL scripts and format spec' },
  { id: 8, label: 'Audit & Recon',    description: 'Validate, reconcile and approve cutover' },
]
