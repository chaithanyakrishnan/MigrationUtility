// services/api.ts
// Typed HTTP client for all MigrateIQ backend endpoints.
// All functions throw on non-2xx — caller handles errors.

import axios from 'axios'
import type {
  Engagement, EngagementCreate, EngagementStepUpdate,
  SchemaFile, SchemaParseResult,
  DomainReview, DomainReviewCreate,
  MappingEntry, MappingApproval, MappingRunRequest, MappingRunStatus,
  ETLGenerateRequest, ETLArtefact, ETLArtefactContent, ETLGenerateStatus,
  ReconRunResult, ReconRunStatus, ReconCheckResult,
  CutoverStatus, AuditEvent,
} from '@/types'

const BASE = import.meta.env.VITE_API_URL ?? ''
const V1   = `${BASE}/api/v1`

export const http = axios.create({
  baseURL: V1,
  headers: { 'Content-Type': 'application/json' },
})

// ── Engagements ───────────────────────────────────────────────
export const api = {

  engagements: {
    list: () =>
      http.get<Engagement[]>('/engagements').then(r => r.data),

    get: (id: string) =>
      http.get<Engagement>(`/engagements/${id}`).then(r => r.data),

    create: (payload: EngagementCreate) =>
      http.post<Engagement>('/engagements', payload).then(r => r.data),

    updateStep: (id: string, payload: EngagementStepUpdate) =>
      http.patch<Engagement>(`/engagements/${id}/step`, payload).then(r => r.data),

    archive: (id: string) =>
      http.delete(`/engagements/${id}`),
  },

  // ── Knowledge Bases (v5) ───────────────────────────────────
  knowledgeBases: {
    status: () =>
      http.get<import('@/types').KnowledgeBasesStatus>('/knowledge-bases').then(r => r.data),

    relius: {
      analyze: (file?: File) => {
        if (!file) {
          return http.post<import('@/types').KBReliusCatalog>('/knowledge-bases/relius/analyze')
            .then(r => r.data)
        }
        const form = new FormData()
        form.append('file', file)
        return http.post<import('@/types').KBReliusCatalog>('/knowledge-bases/relius/analyze', form,
          { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
      },
      get: () =>
        http.get<import('@/types').KBReliusCatalog>('/knowledge-bases/relius').then(r => r.data),
      reviewDomain: (domainId: string, payload: import('@/types').KBReliusDomainReview) =>
        http.patch<import('@/types').KBReliusDomain>(
          `/knowledge-bases/relius/domains/${domainId}`, payload,
        ).then(r => r.data),
      save: () =>
        http.post<import('@/types').KnowledgeBaseSummary>('/knowledge-bases/relius/save')
          .then(r => r.data),
    },

    frp: {
      analyze: (files?: File[]) => {
        if (!files || files.length === 0) {
          return http.post<import('@/types').KBFrpCatalog>('/knowledge-bases/frp/analyze').then(r => r.data)
        }
        const form = new FormData()
        files.forEach(f => form.append('files', f))
        return http.post<import('@/types').KBFrpCatalog>('/knowledge-bases/frp/analyze', form,
          { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
      },
      get: () =>
        http.get<import('@/types').KBFrpCatalog>('/knowledge-bases/frp').then(r => r.data),
      reviewRecord: (recordId: string, payload: import('@/types').KBFrpRecordReview) =>
        http.patch<import('@/types').KBFrpRecord>(
          `/knowledge-bases/frp/records/${recordId}`, payload,
        ).then(r => r.data),
      txnAnalyze: (files?: File[]) => {
        if (!files || files.length === 0) {
          return http.post<import('@/types').KBFrpTxnCatalog>('/knowledge-bases/frp/txn/analyze').then(r => r.data)
        }
        const form = new FormData()
        files.forEach(f => form.append('files', f))
        return http.post<import('@/types').KBFrpTxnCatalog>('/knowledge-bases/frp/txn/analyze', form,
          { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
      },
      txnGet: () =>
        http.get<import('@/types').KBFrpTxnCatalog>('/knowledge-bases/frp/txn').then(r => r.data),
      reviewCard: (code: string, payload: import('@/types').KBTxnCardReview) =>
        http.patch<import('@/types').KBTxnCard>(
          `/knowledge-bases/frp/txn/cards/${code}`, payload,
        ).then(r => r.data),
      save: () =>
        http.post<import('@/types').KnowledgeBaseSummary>('/knowledge-bases/frp/save').then(r => r.data),
    },
  },

  // ── Migration project (mig flow) ───────────────────────────
  project: {
    getState: (eid: string) =>
      http.get<import('@/types').ProjectState>(`/engagements/${eid}/project`).then(r => r.data),
    setTables: (eid: string, tables: string[]) =>
      http.put<import('@/types').ProjectState>(`/engagements/${eid}/project/tables`, { tables }).then(r => r.data),
    runMapping: (eid: string) =>
      http.post<import('@/types').ProjectMapping[]>(`/engagements/${eid}/project/mapping/run`).then(r => r.data),
    listMappings: (eid: string) =>
      http.get<import('@/types').ProjectMapping[]>(`/engagements/${eid}/project/mappings`).then(r => r.data),
    patchMapping: (eid: string, id: string, patch: import('@/types').ProjectMappingPatch) =>
      http.patch<import('@/types').ProjectMapping>(`/engagements/${eid}/project/mappings/${id}`, patch).then(r => r.data),
    approveAll: (eid: string) =>
      http.post<import('@/types').ProjectMapping[]>(`/engagements/${eid}/project/mappings/approve-all`).then(r => r.data),
    getCards: (eid: string) =>
      http.get<import('@/types').ProjectCard[]>(`/engagements/${eid}/project/cards`).then(r => r.data),
    approveCard: (eid: string, code: string) =>
      http.patch<import('@/types').ProjectCard>(`/engagements/${eid}/project/cards/${code}`, {}).then(r => r.data),
    runBatch: (eid: string) =>
      http.post<import('@/types').ProjectBatchResult>(`/engagements/${eid}/project/batch/run`).then(r => r.data),
    downloadUrl: (eid: string) => `${V1}/engagements/${eid}/project/export/download`,
  },

  // ── Observability ──────────────────────────────────────────
  observability: {
    get: () =>
      http.get<import('@/types').ObservabilityData>('/observability').then(r => r.data),
  },

  // ── Schema ─────────────────────────────────────────────────
  schema: {
    upload: (engagementId: string, side: 'src' | 'tgt', file: File) => {
      const form = new FormData()
      form.append('file', file)
      return http.post<SchemaFile>(
        `/engagements/${engagementId}/schema/upload/${side}`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      ).then(r => r.data)
    },

    listFiles: (engagementId: string) =>
      http.get<SchemaFile[]>(`/engagements/${engagementId}/schema/files`)
        .then(r => r.data),

    fileStatus: (engagementId: string, fileId: string) =>
      http.get<SchemaFile>(
        `/engagements/${engagementId}/schema/files/${fileId}/status`,
      ).then(r => r.data),

    deleteFile: (engagementId: string, fileId: string) =>
      http.delete(`/engagements/${engagementId}/schema/files/${fileId}`),

    // Persistent cross-engagement schema understanding
    knowledge: (engagementId: string, side: 'src' | 'tgt') =>
      http.get<import('@/types').SchemaKnowledgeSummary>(
        `/engagements/${engagementId}/schema/knowledge`, { params: { side } },
      ).then(r => r.data),

    useKnowledge: (engagementId: string, side: 'src' | 'tgt') =>
      http.post<SchemaFile>(
        `/engagements/${engagementId}/schema/knowledge/use`, null, { params: { side } },
      ).then(r => r.data),

    knowledgeTables: (engagementId: string, side: 'src' | 'tgt') =>
      http.get<import('@/types').SchemaKnowledgeCatalog>(
        `/engagements/${engagementId}/schema/knowledge/tables`, { params: { side } },
      ).then(r => r.data),

    parseResult: (engagementId: string, fileId: string) =>
      http.get<SchemaParseResult>(
        `/engagements/${engagementId}/schema/files/${fileId}/parse-result`,
      ).then(r => r.data),
  },

  // ── Mapping ────────────────────────────────────────────────
  mapping: {
    run: (engagementId: string, payload?: MappingRunRequest) =>
      http.post<MappingRunStatus>(
        `/engagements/${engagementId}/mapping/run`, payload ?? {},
      ).then(r => r.data),

    status: (engagementId: string) =>
      http.get<MappingRunStatus>(
        `/engagements/${engagementId}/mapping/status`,
      ).then(r => r.data),

    list: (engagementId: string, params?: {
      domain_id?: string
      status?: string
      page?: number
      per_page?: number
    }) =>
      http.get<MappingEntry[]>(
        `/engagements/${engagementId}/mapping`,
        { params },
      ).then(r => r.data),

    approve: (engagementId: string, payload: MappingApproval) =>
      http.patch<{ updated: number }>(
        `/engagements/${engagementId}/mapping/approve`, payload,
      ).then(r => r.data),
  },

  // ── ETL ────────────────────────────────────────────────────
  etl: {
    generate: (engagementId: string, payload?: ETLGenerateRequest, aiEnhanced = true) =>
      http.post(
        `/engagements/${engagementId}/etl/generate`,
        payload ?? {},
        { params: { ai_enhanced: aiEnhanced } },
      ).then(r => r.data),

    generateStatus: (engagementId: string) =>
      http.get<ETLGenerateStatus>(
        `/engagements/${engagementId}/etl/generate/status`,
      ).then(r => r.data),

    listArtefacts: (engagementId: string, artefactType?: string) =>
      http.get<ETLArtefact[]>(
        `/engagements/${engagementId}/etl/artefacts`,
        { params: artefactType ? { artefact_type: artefactType } : {} },
      ).then(r => r.data),

    getArtefact: (engagementId: string, artefactId: string) =>
      http.get<ETLArtefactContent>(
        `/engagements/${engagementId}/etl/artefacts/${artefactId}`,
      ).then(r => r.data),

    downloadUrl: (engagementId: string, artefactId: string) =>
      `${V1}/engagements/${engagementId}/etl/artefacts/${artefactId}/download`,

    clearArtefacts: (engagementId: string) =>
      http.delete(`/engagements/${engagementId}/etl/artefacts`),
  },

  // ── Recon ──────────────────────────────────────────────────
  recon: {
    run: (engagementId: string, checks?: string[]) =>
      http.post(
        `/engagements/${engagementId}/recon/run`,
        { checks: checks ?? null },
      ).then(r => r.data),

    runStatus: (engagementId: string) =>
      http.get<ReconRunStatus>(
        `/engagements/${engagementId}/recon/run/status`,
      ).then(r => r.data),

    results: (engagementId: string) =>
      http.get<ReconRunResult>(
        `/engagements/${engagementId}/recon/results`,
      ).then(r => r.data),

    counterSync: (engagementId: string) =>
      http.post<ReconCheckResult>(
        `/engagements/${engagementId}/recon/counter-sync`,
      ).then(r => r.data),

    auditLog: (engagementId: string, eventType?: string, limit = 100) =>
      http.get<AuditEvent[]>(
        `/engagements/${engagementId}/recon/audit`,
        { params: { event_type: eventType, limit } },
      ).then(r => r.data),

    cutoverStatus: (engagementId: string) =>
      http.get<CutoverStatus>(
        `/engagements/${engagementId}/recon/cutover`,
      ).then(r => r.data),

    submitCutover: (engagementId: string, role: string, name: string) =>
      http.post(
        `/engagements/${engagementId}/recon/cutover`,
        null,
        { params: { approver_role: role, approver_name: name } },
      ).then(r => r.data),
  },

  // ── Health ─────────────────────────────────────────────────
  health: {
    check: () =>
      http.get('/health').then(r => r.data),
  },
}

// ── Session / Reviews / UDFs / Control Files ─────────────────
// (appended to existing api object — these use the session router)
export const sessionApi = {
  // Domain reviews
  saveDomainReview: (engagementId: string, payload: import('@/types').DomainReviewCreate) =>
    http.post(`/engagements/${engagementId}/reviews`, payload).then(r => r.data),

  listDomainReviews: (engagementId: string, side?: 'src' | 'tgt') =>
    http.get(`/engagements/${engagementId}/reviews`, { params: side ? { side } : {} })
      .then(r => r.data as import('@/types').DomainReview[]),

  deleteDomainReview: (engagementId: string, domainId: string, side: 'src' | 'tgt') =>
    http.delete(`/engagements/${engagementId}/reviews/${domainId}`, { params: { side } }),

  // UDFs
  saveUDF: (engagementId: string, form: FormData) =>
    http.post(`/engagements/${engagementId}/udfs`, form,
      { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data),

  listUDFs: (engagementId: string) =>
    http.get(`/engagements/${engagementId}/udfs`).then(r => r.data),

  // Control files
  uploadControlFile: (engagementId: string, file: File) => {
    const form = new FormData(); form.append('file', file)
    return http.post(`/engagements/${engagementId}/control-files`, form,
      { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },

  listControlFiles: (engagementId: string) =>
    http.get(`/engagements/${engagementId}/control-files`).then(r => r.data),

  deleteControlFile: (engagementId: string, fileId: string) =>
    http.delete(`/engagements/${engagementId}/control-files/${fileId}`),

  // Constants
  seedConstants: (engagementId: string) =>
    http.post(`/engagements/${engagementId}/constants/seed`).then(r => r.data),
}
