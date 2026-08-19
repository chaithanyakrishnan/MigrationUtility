// components/screens/FrpReview.tsx — FRP KB step 2: record accordion review.
import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import type { KBFrpRecord, KBFrpFieldReview } from '@/types'

type EditMap = Record<string, KBFrpFieldReview>

// Extraction-confidence buckets (mirror backend CONF_HIGH / CONF_LOW).
const CONF_HIGH = 80
const CONF_LOW = 55
const confMeta = (c: number) =>
  c >= CONF_HIGH ? { cls: 'tg', label: 'High' }
  : c >= CONF_LOW ? { cls: 'ta', label: 'Med' }
  : { cls: 'tr', label: 'Low' }

export default function FrpReview() {
  const catalog          = useStore(s => s.frpCatalog)
  const loadFrpCatalog  = useStore(s => s.loadFrpCatalog)
  const reviewFrpRecord = useStore(s => s.reviewFrpRecord)
  const go               = useStore(s => s.go)

  const [openId, setOpenId] = useState<string | null>(null)
  const [edits, setEdits]   = useState<EditMap>({})
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved'>('all')
  const [focusLow, setFocusLow] = useState(false)

  useEffect(() => { if (!catalog) void loadFrpCatalog() }, [catalog, loadFrpCatalog])

  const records = catalog?.records ?? []
  const approved = records.filter(r => r.approved).length
  const totalFields = records.reduce((n, r) => n + r.fields.length, 0)
  const withLegal = records.reduce((n, r) => n + r.fields.filter(f => f.legal_values?.length).length, 0)
  const lowConfTotal = records.reduce((n, r) => n + (r.low_conf_count ?? 0), 0)

  const visible = records
    .filter(r => filter === 'all' ? true : filter === 'approved' ? r.approved : !r.approved)
    .filter(r => !focusLow || (r.low_conf_count ?? 0) > 0)

  const toggle = (r: KBFrpRecord) => {
    if (openId === r.record_id) { setOpenId(null); return }
    const m: EditMap = {}
    r.fields.forEach(f => { m[f.id] = { id: f.id, description: f.description, included: f.included, approved: f.approved } })
    setEdits(m)
    setOpenId(r.record_id)
  }
  const patch = (id: string, upd: Partial<KBFrpFieldReview>) =>
    setEdits(prev => ({ ...prev, [id]: { ...prev[id], ...upd } }))

  const approveAll = (r: KBFrpRecord) =>
    setEdits(prev => { const n = { ...prev }; r.fields.forEach(f => n[f.id] = { ...n[f.id], approved: true }); return n })

  const save = async (r: KBFrpRecord) => {
    const fields = r.fields.map(f => edits[f.id])
    await reviewFrpRecord(r.record_id, { approved: fields.every(f => f.approved), fields })
    setOpenId(null)
  }

  return (
    <>
      <div className="notice nt">
        <span className="nicon">🤖</span>
        <span>FRP schema catalogued — <strong>{records.length} record groups · {totalFields} data elements</strong>. Each element carries an <strong>extraction-confidence</strong> score — use <em>Focus low-confidence</em> to review the uncertain ones first.</span>
      </div>

      <div className="statrow" style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 8, marginBottom: 14 }}>
        <div className="scard"><div className="slabel">Record groups</div><div className="sval t">{records.length}</div></div>
        <div className="scard"><div className="slabel">Total data elements</div><div className="sval t">{totalFields}</div></div>
        <div className="scard"><div className="slabel">With legal values</div><div className="sval g">{withLegal}</div></div>
        <div className="scard"><div className="slabel">Fields to review</div><div className={`sval ${lowConfTotal ? 'a' : 'g'}`}>{lowConfTotal}</div></div>
        <div className="scard"><div className="slabel">Records reviewed</div><div className="sval t">{approved} / {records.length}</div></div>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
        <select className="sel" value={filter} onChange={e => setFilter(e.target.value as any)}>
          <option value="all">All records</option>
          <option value="pending">Pending review</option>
          <option value="approved">Approved</option>
        </select>
        <button
          className={`btn btn-ghost btn-sm${focusLow ? ' act' : ''}`}
          onClick={() => setFocusLow(v => !v)}
          title="Show only records with fields the extractor was unsure about, lowest-confidence rows first"
        >
          {focusLow ? '✓ Focusing fields to review' : '⚠ Focus fields to review'}{lowConfTotal ? ` (${lowConfTotal})` : ''}
        </button>
      </div>

      {focusLow && visible.length === 0 && (
        <div className="notice ng">
          <span className="nicon">✅</span>
          <span>No fields need review — every data element was extracted with high confidence.</span>
        </div>
      )}

      {visible.map(r => {
        const isOpen = openId === r.record_id
        return (
          <div key={r.record_id} style={{ border: `1px solid ${r.approved ? 'var(--green)' : 'var(--bd)'}`, borderRadius: 8, marginBottom: 8, overflow: 'hidden' }}>
            <div onClick={() => toggle(r)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: isOpen ? 'var(--bg3)' : 'var(--bg2)', cursor: 'pointer' }}>
              <span style={{ fontSize: 16 }}>{r.icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--teal)', fontWeight: 600 }}>{r.prefix}</span>
                  <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--tx1)' }}>{r.name}</span>
                  <span className={`tag t${r.category_color ?? 't'}`} style={{ fontSize: 8 }}>{r.category}</span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 2 }}>{r.fields.length} data elements · {(r.description ?? '').slice(0, 80)}</div>
              </div>
              {(r.low_conf_count ?? 0) > 0 && (
                <span className="tag ta" style={{ fontSize: 9 }} title={`${r.low_conf_count} field(s) the extractor was unsure about`}>⚠ {r.low_conf_count} to review</span>
              )}
              <span className={`tag ${confMeta(r.avg_confidence ?? 100).cls}`} style={{ fontSize: 9 }} title="Average extraction confidence for this record">
                {r.avg_confidence ?? 100}% conf
              </span>
              <span className={`tag ${r.approved ? 'tg' : 'tgr'}`} style={{ fontSize: 9 }}>{r.approved ? '✓ Reviewed' : 'Pending'}</span>
            </div>

            {isOpen && (
              <div style={{ borderTop: '1px solid var(--bd)' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, padding: '8px 14px', background: 'var(--bg1)', borderBottom: '1px solid var(--bd)' }}>
                  <button className="btn btn-ghost btn-xs" onClick={() => approveAll(r)}>✓ Approve all fields</button>
                  <button className="btn btn-primary btn-xs" onClick={() => void save(r)}>Save &amp; close</button>
                </div>
                <div style={{ maxHeight: 440, overflowY: 'auto' }}>
                  <table className="dt" style={{ width: '100%' }}>
                    <thead style={{ position: 'sticky', top: 0 }}>
                      <tr><th>Code</th><th>Name</th><th style={{ minWidth: 340, width: '42%' }}>Description</th><th>Legal Values</th><th style={{ textAlign: 'center' }}>Confidence</th><th style={{ textAlign: 'center' }}>Key</th><th style={{ textAlign: 'center' }}>Incl</th><th style={{ textAlign: 'center' }}>✓</th></tr>
                    </thead>
                    <tbody>
                      {(focusLow ? [...r.fields].sort((a, b) => a.confidence - b.confidence) : r.fields).map(f => {
                        const e = edits[f.id]
                        const cm = confMeta(f.confidence)
                        const rowBg = f.confidence < CONF_LOW ? 'var(--reddim)'
                          : f.confidence < CONF_HIGH ? 'var(--golddim)' : undefined
                        return (
                          <tr key={f.id} style={rowBg ? { background: rowBg } : undefined}>
                            <td className="mono" style={{ color: 'var(--teal)' }}>{f.code}</td>
                            <td style={{ color: 'var(--tx1)', fontWeight: 500 }}>{f.name}</td>
                            <td style={{ verticalAlign: 'top' }}><textarea className="inp-area" rows={2} value={e?.description ?? ''} onChange={ev => patch(f.id, { description: ev.target.value })} /></td>
                            <td style={{ fontSize: 9 }}>
                              {f.legal_values?.length
                                ? f.legal_values.map(lv => <span key={lv.v} style={{ marginRight: 4 }}><span className="mono" style={{ color: 'var(--teal)' }}>{lv.v}</span> {lv.l}</span>)
                                : <span style={{ color: 'var(--tx3)' }}>—</span>}
                            </td>
                            <td style={{ textAlign: 'center', whiteSpace: 'nowrap' }}
                                title={f.confidence_flags?.length ? `Low confidence: ${f.confidence_flags.join('; ')}` : 'High-confidence extraction'}>
                              <span className={`tag ${cm.cls}`} style={{ fontSize: 8 }}>{f.confidence}%</span>
                              {f.confidence_flags?.length > 0 && (
                                <div style={{ fontSize: 8, color: 'var(--tx3)', marginTop: 2, maxWidth: 120, whiteSpace: 'normal', lineHeight: 1.3 }}>
                                  {f.confidence_flags[0]}
                                </div>
                              )}
                            </td>
                            <td style={{ textAlign: 'center' }}>{f.is_key && <span className="tag tt" style={{ fontSize: 8 }}>key</span>}</td>
                            <td style={{ textAlign: 'center' }}><input type="checkbox" checked={!!e?.included} onChange={ev => patch(f.id, { included: ev.target.checked })} style={{ accentColor: 'var(--teal)' }} /></td>
                            <td style={{ textAlign: 'center' }}><button className={`tick-btn${e?.approved ? ' saved' : ''}`} onClick={() => patch(f.id, { approved: !e?.approved })}>✓</button></td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )
      })}

      <div className="card" style={{ marginTop: 16, borderColor: 'var(--teal)', textAlign: 'center', padding: 20 }}>
        <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 14 }}>
          Next, upload the FRP transaction card layout specs to complete the Knowledge Base.
        </div>
        <button className="btn btn-primary" style={{ padding: '8px 22px' }} onClick={() => go('s-okb-txn')}>
          Continue to Transaction Layouts →
        </button>
      </div>
    </>
  )
}
