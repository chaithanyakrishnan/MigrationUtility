// components/screens/SelectTables.tsx — mig step 1: pick Relius tables from the KB.
import { useEffect, useState } from 'react'
import { useStore } from '@/store'

export default function SelectTables() {
  const reliusCatalog     = useStore(s => s.reliusCatalog)
  const loadReliusCatalog = useStore(s => s.loadReliusCatalog)
  const projectState      = useStore(s => s.projectState)
  const loadProjectState  = useStore(s => s.loadProjectState)
  const setSelectedTables = useStore(s => s.setSelectedTables)
  const go                = useStore(s => s.go)
  const notify            = useStore(s => s.notify)

  const [sel, setSel]   = useState<Set<string>>(new Set())
  const [open, setOpen] = useState<Set<string>>(new Set())

  useEffect(() => { if (!reliusCatalog) void loadReliusCatalog() }, [reliusCatalog, loadReliusCatalog])
  useEffect(() => { void loadProjectState() }, [loadProjectState])
  useEffect(() => {
    if (projectState?.selected_tables?.length) setSel(new Set(projectState.selected_tables))
  }, [projectState])

  const domains = reliusCatalog?.domains ?? []
  const toggle = (t: string) => setSel(prev => { const n = new Set(prev); n.has(t) ? n.delete(t) : n.add(t); return n })
  const toggleOpen = (id: string) => setOpen(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  const selectAllIn = (tables: string[], on: boolean) =>
    setSel(prev => { const n = new Set(prev); tables.forEach(t => on ? n.add(t) : n.delete(t)); return n })

  const domsTouched = domains.filter(d => (d.tables || []).some(t => sel.has(t))).length

  const persistAnd = async (fn: () => void) => { await setSelectedTables(Array.from(sel)); fn() }

  return (
    <>
      <div className="notice nt">
        <span className="nicon">🗂️</span>
        <span>Choose which tables from the Relius Knowledge Base to include in this migration project. AI Mapping runs only against your selected tables.</span>
      </div>

      <div className="card">
        <div className="ctitle" style={{ marginBottom: 10 }}>Selection summary</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
          <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Tables selected</div><div className="sval t" style={{ fontSize: 18 }}>{sel.size}</div></div>
          <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Domains touched</div><div className="sval t" style={{ fontSize: 18 }}>{domsTouched}</div></div>
          <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Est. rows</div><div className="sval g" style={{ fontSize: 18 }}>{sel.size ? `${sel.size * 15}K` : '—'}</div></div>
        </div>
      </div>

      {domains.map(d => {
        const tables = d.tables || []
        const isOpen = open.has(d.domain_id)
        const selCount = tables.filter(t => sel.has(t)).length
        return (
          <div key={d.domain_id} className="txn-cat">
            <div className="txn-cat-hdr" onClick={() => toggleOpen(d.domain_id)}>
              <span style={{ fontSize: 16 }}>{d.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--tx1)' }}>{d.name}</div>
                <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 1 }}>{tables.length} tables</div>
              </div>
              {selCount > 0 && <span className="tag tt" style={{ fontSize: 9 }}>{selCount} selected</span>}
              <button className="btn btn-ghost btn-xs" style={{ marginLeft: 6 }} onClick={e => { e.stopPropagation(); selectAllIn(tables, true) }}>Select all</button>
              <button className="btn btn-ghost btn-xs" onClick={e => { e.stopPropagation(); selectAllIn(tables, false) }}>Clear</button>
              <span style={{ color: 'var(--tx3)', fontSize: 12, transform: isOpen ? 'rotate(180deg)' : '' }}>⌄</span>
            </div>
            {isOpen && (
              <div style={{ padding: '12px 14px', background: 'var(--bg1)', display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 8 }}>
                {tables.map(t => (
                  <div key={t} className={`tbl-chip${sel.has(t) ? ' sel' : ''}`} onClick={() => toggle(t)}>
                    <div className="tbl-chip-check">✓</div>
                    <div className="txn-chip-code">{t}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      <div className="card" style={{ marginTop: 16, textAlign: 'center', padding: 20 }}>
        <button
          className="btn btn-primary"
          style={{ padding: '8px 22px' }}
          onClick={() => sel.size ? void persistAnd(() => go('s6')) : notify('Select at least one table', 'amber')}
        >
          Continue to AI Mapping →
        </button>
      </div>
    </>
  )
}
