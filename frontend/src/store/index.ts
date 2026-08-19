// store/index.ts
// Zustand store for MigrateIQ v5 (Knowledge-Base architecture).
// Slices: navigation, knowledge bases (Relius + FRP), migration project,
// engagement, notifications.

import { create } from 'zustand'
import { api } from '@/services/api'
import type { ScreenId } from '@/nav'
import type {
  Engagement, Notification,
  KnowledgeBasesStatus, KBReliusCatalog, KBReliusDomainReview,
  KBFrpCatalog, KBFrpRecordReview, KBFrpTxnCatalog, KBTxnCardReview,
  ProjectState, ProjectMapping, ProjectCard, ProjectMappingPatch, ProjectBatchResult,
  ObservabilityData,
} from '@/types'

let _notifId = 0
const notifId = () => String(++_notifId)

// Pull a human-readable message out of an axios error, handling FastAPI's
// string detail, its array-of-validation-errors detail, and network failures.
function errText(e: any, fallback: string): string {
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && d.trim()) return d
  if (Array.isArray(d) && d.length) return d.map((x: any) => x?.msg ?? JSON.stringify(x)).join('; ')
  if (e?.response?.status) return `${fallback} (HTTP ${e.response.status})`
  if (e?.message === 'Network Error' || e?.code === 'ERR_NETWORK') {
    return `${fallback} — backend not reachable. Is it running on :8000?`
  }
  return fallback
}

interface MigrateIQState {
  // ── Navigation ────────────────────────────────────────────
  currentScreen: ScreenId
  obsOpen: boolean
  obsPrevScreen: ScreenId
  go: (id: ScreenId) => void
  openObs: () => void
  closeObs: () => void
  obsData: ObservabilityData | null
  loadObs: () => Promise<void>

  // ── Knowledge Bases ───────────────────────────────────────
  kbStatus: KnowledgeBasesStatus | null
  loadKBStatus: () => Promise<void>

  reliusCatalog: KBReliusCatalog | null
  reliusAnalyzing: boolean
  loadReliusCatalog: () => Promise<void>
  analyzeRelius: (file?: File) => Promise<void>
  reviewReliusDomain: (domainId: string, payload: KBReliusDomainReview) => Promise<void>
  saveReliusKB: () => Promise<void>

  frpCatalog: KBFrpCatalog | null
  frpTxnCatalog: KBFrpTxnCatalog | null
  frpAnalyzing: boolean
  frpTxnAnalyzing: boolean
  loadFrpCatalog: () => Promise<void>
  analyzeFrp: (files?: File[]) => Promise<void>
  reviewFrpRecord: (recordId: string, payload: KBFrpRecordReview) => Promise<void>
  loadFrpTxn: () => Promise<void>
  analyzeFrpTxn: (files?: File[]) => Promise<void>
  reviewTxnCard: (code: string, payload: KBTxnCardReview) => Promise<void>
  saveFrpKB: () => Promise<void>

  // ── Migration project ─────────────────────────────────────
  projectState: ProjectState | null
  projectMappings: ProjectMapping[]
  projectCards: ProjectCard[]
  projectBatch: ProjectBatchResult | null
  mappingRunning: boolean
  loadProjectState: () => Promise<void>
  setSelectedTables: (tables: string[]) => Promise<void>
  loadProjectMappings: () => Promise<void>
  runProjectMapping: () => Promise<void>
  patchProjectMapping: (id: string, patch: ProjectMappingPatch) => Promise<void>
  approveAllMappings: () => Promise<void>
  loadProjectCards: () => Promise<void>
  approveProjectCard: (code: string) => Promise<void>
  runProjectBatch: () => Promise<void>

  // ── Engagement (= migration project) ──────────────────────
  engagement: Engagement | null
  engagementList: Engagement[]
  loadEngagements: () => Promise<void>
  createEngagement: (name: string, client: string) => Promise<Engagement>
  selectEngagement: (id: string) => Promise<void>
  clearEngagement: () => void

  // ── Notifications ─────────────────────────────────────────
  notifications: Notification[]
  notify: (message: string, type?: Notification['type']) => void
  dismissNotif: (id: string) => void

  isLoading: boolean
  setLoading: (v: boolean) => void
}

const resetProject = {
  projectState: null,
  projectMappings: [] as ProjectMapping[],
  projectCards: [] as ProjectCard[],
  projectBatch: null,
  mappingRunning: false,
}

export const useStore = create<MigrateIQState>()((set, get) => ({

  // ── Navigation ──────────────────────────────────────────────
  currentScreen: 'home',
  obsOpen: false,
  obsPrevScreen: 'home',

  go: (id) => { set({ currentScreen: id, obsOpen: false }); window.scrollTo(0, 0) },
  openObs: () => set(state => ({
    obsOpen: true,
    obsPrevScreen: state.currentScreen === 's-obs' ? state.obsPrevScreen : state.currentScreen,
    currentScreen: 's-obs',
  })),
  closeObs: () => set(state => ({ obsOpen: false, currentScreen: state.obsPrevScreen })),
  obsData: null,
  loadObs: async () => {
    try { set({ obsData: await api.observability.get() }) }
    catch { set({ obsData: null }) }
  },

  // ── Knowledge Bases ─────────────────────────────────────────
  kbStatus: null,
  loadKBStatus: async () => {
    try { set({ kbStatus: await api.knowledgeBases.status() }) }
    catch { set({ kbStatus: null }) }
  },

  // Relius KB
  reliusCatalog: null,
  reliusAnalyzing: false,
  loadReliusCatalog: async () => {
    try { set({ reliusCatalog: await api.knowledgeBases.relius.get() }) }
    catch { set({ reliusCatalog: null }) }
  },
  analyzeRelius: async (file) => {
    set({ reliusAnalyzing: true })
    try {
      const cat = await api.knowledgeBases.relius.analyze(file)
      const fields = cat.domains.reduce((n, d) => n + d.fields.length, 0)
      set({ reliusCatalog: cat })
      get().notify(
        file ? `Parsed ${file.name} — ${cat.domains.length} domains · ${fields} fields`
             : `Relius schema seeded — ${cat.domains.length} domains`,
        'teal',
      )
    } catch (e: any) {
      get().notify(errText(e, 'Failed to analyse Relius schema'), 'red')
    } finally { set({ reliusAnalyzing: false }) }
  },
  reviewReliusDomain: async (domainId, payload) => {
    try {
      const updated = await api.knowledgeBases.relius.reviewDomain(domainId, payload)
      set(state => ({
        reliusCatalog: state.reliusCatalog && {
          ...state.reliusCatalog,
          domains: state.reliusCatalog.domains.map(d => d.domain_id === domainId ? updated : d),
        },
      }))
      const n = payload.fields.filter(f => f.approved).length
      get().notify(`Domain review saved — ${n}/${payload.fields.length} fields approved`, 'green')
    } catch { get().notify('Failed to save domain review', 'red') }
  },
  saveReliusKB: async () => {
    try {
      await api.knowledgeBases.relius.save()
      await get().loadKBStatus()
      get().notify('Relius Knowledge Base saved ✓', 'green')
      get().go('home')
    } catch { get().notify('Failed to save Relius KB', 'red') }
  },

  // FRP KB
  frpCatalog: null,
  frpTxnCatalog: null,
  frpAnalyzing: false,
  frpTxnAnalyzing: false,
  loadFrpCatalog: async () => {
    try { set({ frpCatalog: await api.knowledgeBases.frp.get() }) }
    catch { set({ frpCatalog: null }) }
  },
  analyzeFrp: async (files) => {
    set({ frpAnalyzing: true })
    try {
      const cat = await api.knowledgeBases.frp.analyze(files)
      const fields = cat.records.reduce((n, r) => n + r.fields.length, 0)
      set({ frpCatalog: cat })
      const n = files?.length ?? 0
      get().notify(
        n ? `Parsed ${n} file${n > 1 ? 's' : ''} — ${cat.records.length} records · ${fields} data elements`
          : `FRP schema seeded — ${cat.records.length} record groups`,
        'teal',
      )
    } catch (e: any) {
      get().notify(errText(e, 'Failed to analyse FRP schema'), 'red')
    } finally { set({ frpAnalyzing: false }) }
  },
  reviewFrpRecord: async (recordId, payload) => {
    try {
      const updated = await api.knowledgeBases.frp.reviewRecord(recordId, payload)
      set(state => ({
        frpCatalog: state.frpCatalog && {
          ...state.frpCatalog,
          records: state.frpCatalog.records.map(r => r.record_id === recordId ? updated : r),
        },
      }))
      const n = payload.fields.filter(f => f.approved).length
      get().notify(`Record saved — ${n}/${payload.fields.length} fields approved`, 'green')
    } catch { get().notify('Failed to save record review', 'red') }
  },
  loadFrpTxn: async () => {
    try { set({ frpTxnCatalog: await api.knowledgeBases.frp.txnGet() }) }
    catch { set({ frpTxnCatalog: null }) }
  },
  analyzeFrpTxn: async (files) => {
    set({ frpTxnAnalyzing: true })
    try {
      const cat = await api.knowledgeBases.frp.txnAnalyze(files)
      const fields = cat.cards.reduce((n, c) => n + c.fields.length, 0)
      set({ frpTxnCatalog: cat })
      const n = files?.length ?? 0
      get().notify(
        n ? `Parsed ${n} file${n > 1 ? 's' : ''} — ${cat.cards.length} transaction cards · ${fields} fields`
          : `Transaction layouts seeded — ${cat.cards.length} cards`,
        'teal',
      )
    } catch (e: any) { get().notify(errText(e, 'Failed to analyse transaction layouts'), 'red') }
    finally { set({ frpTxnAnalyzing: false }) }
  },
  reviewTxnCard: async (code, payload) => {
    try {
      const updated = await api.knowledgeBases.frp.reviewCard(code, payload)
      set(state => ({
        frpTxnCatalog: state.frpTxnCatalog && {
          ...state.frpTxnCatalog,
          cards: state.frpTxnCatalog.cards.map(c => c.code === code ? updated : c),
        },
      }))
      get().notify(`Transaction card ${code} approved ✓`, 'green')
    } catch { get().notify('Failed to save card review', 'red') }
  },
  saveFrpKB: async () => {
    try {
      await api.knowledgeBases.frp.save()
      await get().loadKBStatus()
      get().notify('FRP Knowledge Base saved ✓', 'green')
      get().go('home')
    } catch { get().notify('Failed to save FRP KB', 'red') }
  },

  // ── Migration project ───────────────────────────────────────
  ...resetProject,

  loadProjectState: async () => {
    const { engagement } = get()
    if (!engagement) return
    try { set({ projectState: await api.project.getState(engagement.id) }) }
    catch { /* non-critical */ }
  },
  setSelectedTables: async (tables) => {
    const { engagement } = get()
    if (!engagement) return
    try { set({ projectState: await api.project.setTables(engagement.id, tables) }) }
    catch { get().notify('Failed to save table selection', 'red') }
  },
  loadProjectMappings: async () => {
    const { engagement } = get()
    if (!engagement) return
    try { set({ projectMappings: await api.project.listMappings(engagement.id) }) }
    catch { /* non-critical */ }
  },
  runProjectMapping: async () => {
    const { engagement } = get()
    if (!engagement) return
    set({ mappingRunning: true })
    try {
      const ms = await api.project.runMapping(engagement.id)
      set({ projectMappings: ms })
      await get().loadProjectState()
      get().notify(`AI mapping complete — ${ms.length} field mappings proposed`, 'teal')
    } catch { get().notify('Failed to run AI mapping', 'red') }
    finally { set({ mappingRunning: false }) }
  },
  patchProjectMapping: async (id, patch) => {
    const { engagement } = get()
    if (!engagement) return
    try {
      const updated = await api.project.patchMapping(engagement.id, id, patch)
      set(state => ({ projectMappings: state.projectMappings.map(m => m.id === id ? updated : m) }))
    } catch { get().notify('Failed to update mapping', 'red') }
  },
  approveAllMappings: async () => {
    const { engagement } = get()
    if (!engagement) return
    try {
      set({ projectMappings: await api.project.approveAll(engagement.id) })
      get().notify('All mappings confirmed ✓', 'green')
    } catch { get().notify('Failed to approve mappings', 'red') }
  },
  loadProjectCards: async () => {
    const { engagement } = get()
    if (!engagement) return
    try { set({ projectCards: await api.project.getCards(engagement.id) }) }
    catch { /* non-critical */ }
  },
  approveProjectCard: async (code) => {
    const { engagement } = get()
    if (!engagement) return
    try {
      const updated = await api.project.approveCard(engagement.id, code)
      set(state => ({ projectCards: state.projectCards.map(c => c.code === code ? updated : c) }))
      get().notify(`Transaction card ${code} approved ✓`, 'green')
    } catch { get().notify('Failed to approve card', 'red') }
  },
  runProjectBatch: async () => {
    const { engagement } = get()
    if (!engagement) return
    try {
      const res = await api.project.runBatch(engagement.id)
      set({ projectBatch: res })
      get().notify(`Batch complete — ${res.line_count} transaction card line(s) written`, 'green')
    } catch (e: any) {
      get().notify(e?.response?.data?.detail ?? 'Batch run failed', 'red')
    }
  },

  // ── Engagement ──────────────────────────────────────────────
  engagement: null,
  engagementList: [],

  loadEngagements: async () => {
    try { set({ engagementList: await api.engagements.list() }) }
    catch { get().notify('Failed to load projects', 'red') }
  },

  createEngagement: async (name, client) => {
    const eng = await api.engagements.create({ name, client_name: client })
    set({ engagement: eng, engagementList: [eng, ...get().engagementList], ...resetProject })
    get().notify(`Project "${name}" created`, 'teal')
    return eng
  },

  selectEngagement: async (id) => {
    try {
      const eng = await api.engagements.get(id)
      set({ engagement: eng, ...resetProject })
      await get().loadProjectState()
    } catch { get().notify('Failed to load project', 'red') }
  },

  clearEngagement: () => set({ engagement: null, ...resetProject }),

  // ── Notifications ───────────────────────────────────────────
  notifications: [],
  notify: (message, type = 'teal') => {
    const notif: Notification = { id: notifId(), message, type, timestamp: Date.now() }
    set(state => ({ notifications: [...state.notifications, notif] }))
    setTimeout(() => get().dismissNotif(notif.id), type === 'red' ? 6000 : 4000)
  },
  dismissNotif: (id) =>
    set(state => ({ notifications: state.notifications.filter(n => n.id !== id) })),

  isLoading: false,
  setLoading: (v) => set({ isLoading: v }),
}))
