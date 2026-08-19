// nav.ts
// v5 Knowledge-Base architecture navigation model.
// Three flows (Relius KB, FRP KB, Migration Project) plus Home + Observability,
// mirroring the prototype's SCREEN_META. Replaces the old linear 1–8 step model.

export type FlowId = 'home' | 'rkb' | 'okb' | 'mig' | 'obs'

export type ScreenId =
  | 'home'
  | 's1' | 's2'                                            // rkb
  | 's3' | 's4' | 's-okb-txn' | 's5' | 's-okb-summary'     // okb
  | 'mig-tables' | 's6' | 'mig-cards' | 'mig-batch'        // mig
  | 's-obs'

export interface ScreenMeta {
  flow: Exclude<FlowId, 'home' | 'obs'>
  idx: number
  total: number
  title: string
  subtitle: string
  navId: string
  next: ScreenId | null
  prev: ScreenId | null
  label: string
}

// Only flow screens live here (home + obs are handled specially in App).
export const SCREEN_META: Record<Exclude<ScreenId, 'home' | 's-obs'>, ScreenMeta> = {
  's1':        { flow: 'rkb', idx: 1, total: 2, title: 'Relius Schema Mapper',    subtitle: 'Upload Relius schema export files — SQL DDL, JSON, XLSX, PDF or DOCX',           navId: 'nav-rkb',  next: 's2',            prev: 'home', label: 'Upload Schema' },
  's2':        { flow: 'rkb', idx: 2, total: 2, title: 'Relius Schema Review',    subtitle: 'AI-identified business domains — review, approve and correct field definitions', navId: 'nav-rkb',  next: null,            prev: 's1',   label: 'Review & Save' },

  's3':            { flow: 'okb', idx: 1, total: 5, title: 'FRP Schema Mapper',       subtitle: 'Upload FRP data dictionary files — record definitions and field catalogue', navId: 'nav-okb', next: 's4',             prev: 'home', label: 'Upload Schema' },
  's4':            { flow: 'okb', idx: 2, total: 5, title: 'FRP Schema Review',       subtitle: 'AI-catalogued FRP records — review target field definitions and confirm scope',    navId: 'nav-okb', next: 's-okb-txn',      prev: 's3',   label: 'Review Schema' },
  's-okb-txn':     { flow: 'okb', idx: 3, total: 5, title: 'FRP Transaction Layouts', subtitle: 'Upload transaction card layout specs — fixed-width column definitions per T-code',   navId: 'nav-okb', next: 's5',             prev: 's4',   label: 'Upload Transaction Cards' },
  's5':            { flow: 'okb', idx: 4, total: 5, title: 'FRP Transaction Review',  subtitle: 'Review and confirm transaction card layouts before saving to the Knowledge Base',     navId: 'nav-okb', next: 's-okb-summary',  prev: 's-okb-txn', label: 'Review Transactions' },
  's-okb-summary': { flow: 'okb', idx: 5, total: 5, title: 'Summary & Save',           subtitle: 'Review everything catalogued so far, then save the completed FRP Knowledge Base',    navId: 'nav-okb', next: null,             prev: 's5',   label: 'Summary & Save' },

  'mig-tables': { flow: 'mig', idx: 1, total: 4, title: 'Select Relius Tables', subtitle: 'Choose which Relius KB tables to include in this migration project',                navId: 'nav-mig1', next: 's6',        prev: 'home',       label: 'Select Tables' },
  's6':         { flow: 'mig', idx: 2, total: 4, title: 'AI Field Mapping',     subtitle: 'Review AI-proposed field + transaction mappings — edits saved to mapping registry',  navId: 'nav-mig2', next: 'mig-cards', prev: 'mig-tables', label: 'AI Mapping' },
  'mig-cards':  { flow: 'mig', idx: 3, total: 4, title: 'Transaction Cards',    subtitle: 'Review the FRP transaction card layouts populated from your approved field mappings', navId: 'nav-mig3', next: 'mig-batch', prev: 's6',         label: 'Transaction Cards' },
  'mig-batch':  { flow: 'mig', idx: 4, total: 4, title: 'Batch Run',            subtitle: 'Run the batch process that reads Relius extracts and writes transaction card files',   navId: 'nav-mig4', next: null,        prev: 'mig-cards',  label: 'Batch Run' },
}

export function flowLabel(f: FlowId): string {
  return f === 'rkb' ? 'Relius KB Setup'
    : f === 'okb' ? 'FRP KB Setup'
    : f === 'mig' ? 'Migration Project'
    : f
}

// Screens belonging to a flow, ordered by idx — used to render the step bar.
export function flowScreens(flow: Exclude<FlowId, 'home' | 'obs'>): ScreenId[] {
  return (Object.keys(SCREEN_META) as Array<Exclude<ScreenId, 'home' | 's-obs'>>)
    .filter(id => SCREEN_META[id].flow === flow)
    .sort((a, b) => SCREEN_META[a].idx - SCREEN_META[b].idx)
}
