// components/screens/ReliusReview.tsx — Relius KB step 2: review domains + save.
import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import type { KBReliusDomain, KBReliusFieldReview } from '@/types'

type EditMap = Record<string, KBReliusFieldReview>

export default function ReliusReview() {
  const catalog            = useStore(s => s.reliusCatalog)
  const loadReliusCatalog  = useStore(s => s.loadReliusCatalog)
  const reviewReliusDomain = useStore(s => s.reviewReliusDomain)
  const saveReliusKB       = useStore(s => s.saveReliusKB)
  const notify             = useStore(s => s.notify)

  const [openId, setOpenId] = useState<string | null>(null)
  const [edits, setEdits]   = useState<EditMap>({})

  useEffect(() => { if (!catalog) void loadReliusCatalog() }, [catalog, loadReliusCatalog])

  const domains = catalog?.domains ?? []
  const totalFields = domains.reduce((n, d) => n + d.fields.length, 0)

  // Review completeness = % of a domain's fields the SME has approved.
  // For the open domain it reflects the live (unsaved) ticks; for the rest it
  // reflects the saved catalogue. 100% ⇒ fully reviewed.
  const domainPct = (d: KBReliusDomain) => {
    const total = d.fields.length || 1
    const approved = openId === d.domain_id
      ? d.fields.filter(f => edits[f.id]?.approved).length
      : d.fields.filter(f => f.approved).length
    return Math.round((approved / total) * 100)
  }
  const pctTag = (pct: number) => (pct === 100 ? 'tg' : pct >= 60 ? 'tt' : 'ta')
  const pctBorder = (pct: number) => (pct === 100 ? ' dom-resolved' : pct < 60 ? ' dom-review' : '')

  const approvedCount = domains.filter(d => domainPct(d) === 100).length

  const openDomain = (d: KBReliusDomain) => {
    const m: EditMap = {}
    d.fields.forEach(f => {
      m[f.id] = { id: f.id, data_type: f.data_type, description: f.description, included: f.included, approved: f.approved }
    })
    setEdits(m)
    setOpenId(d.domain_id)
  }

  const patch = (id: string, upd: Partial<KBReliusFieldReview>) =>
    setEdits(prev => ({ ...prev, [id]: { ...prev[id], ...upd } }))

  const openDom = domains.find(d => d.domain_id === openId) ?? null

  const approveAllFields = () => {
    if (!openDom) return
    setEdits(prev => {
      const next = { ...prev }
      openDom.fields.forEach(f => { next[f.id] = { ...next[f.id], approved: true } })
      return next
    })
  }

  const saveDomain = async () => {
    if (!openDom) return
    const fields = openDom.fields.map(f => edits[f.id])
    await reviewReliusDomain(openDom.domain_id, { approved: fields.every(f => f.approved), fields })
    setOpenId(null)
  }

  return (
    <>
      <div className="notice nt">
        <span className="nicon">🤖</span>
        <span>AI has classified the Relius schema into <strong>{domains.length} business domains</strong>. Click any domain to inspect and approve its fields.</span>
      </div>

      <div className="statrow g4" style={{ marginBottom: 14 }}>
        <div className="scard"><div className="slabel">Domains found</div><div className="sval t">{domains.length}</div></div>
        <div className="scard"><div className="slabel">Total fields</div><div className="sval t">{totalFields}</div></div>
        <div className="scard"><div className="slabel">Tables</div><div className="sval g">{catalog?.stats?.tables ?? domains.reduce((n, d) => n + d.table_count, 0)}</div></div>
        <div className="scard"><div className="slabel">Domains approved</div><div className="sval t">{approvedCount} / {domains.length}</div></div>
      </div>

      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--tx1)', marginBottom: 8 }}>
        Business domains <span style={{ fontSize: 10, color: 'var(--tx3)', fontWeight: 400 }}>— click to inspect fields</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
        {domains.map(d => {
          const pct = domainPct(d)
          return (
            <div key={d.domain_id} className={`dcard${pctBorder(pct)}`} onClick={() => openDomain(d)}>
              {pct === 100
                ? <div style={{ position: 'absolute', top: 8, right: 8 }}><span className="tag tg" style={{ fontSize: 9 }}>✓ Reviewed</span></div>
                : pct < 60 ? <div style={{ position: 'absolute', top: 8, right: 8 }}><span className="review-badge">Review</span></div> : null}
              <div className="dicon">{d.icon}</div>
              <div className="dname">{d.name}</div>
              <div className="dmeta">{d.table_count} tables · {d.fields.length} fields{d.row_estimate ? ` · ${d.row_estimate} rows` : ''}</div>
              <div style={{ marginTop: 5 }}>
                <span className={`tag ${pctTag(pct)}`} style={{ fontSize: 9 }}>{pct}% reviewed</span>
              </div>
            </div>
          )
        })}
      </div>

      {openDom && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: 'var(--bg2)', border: '1px solid var(--bd)', borderRadius: '8px 8px 0 0' }}>
            <span style={{ fontSize: 18 }}>{openDom.icon}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)' }}>{openDom.name}</div>
              <div style={{ fontSize: 10, color: 'var(--tx3)' }}>{openDom.table_count} tables · {openDom.fields.length} fields</div>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <button className="btn btn-ghost btn-xs" onClick={approveAllFields}>✓ Approve all fields</button>
              <button className="btn btn-ghost btn-xs" onClick={() => setOpenId(null)}>✕ Close</button>
            </div>
          </div>
          <div style={{ border: '1px solid var(--bd)', borderRadius: '0 0 8px 8px', overflow: 'hidden' }}>
            <div style={{ maxHeight: 460, overflowY: 'auto' }}>
              <table className="dt" style={{ width: '100%' }}>
                <thead style={{ position: 'sticky', top: 0 }}>
                  <tr>
                    <th>Table</th><th>Field</th><th>Name</th>
                    <th style={{ minWidth: 100 }}>Type</th>
                    <th style={{ minWidth: 320, width: '40%' }}>Description</th>
                    <th style={{ textAlign: 'center' }}>Include</th>
                    <th style={{ textAlign: 'center' }}>✓</th>
                  </tr>
                </thead>
                <tbody>
                  {openDom.fields.map(f => {
                    const e = edits[f.id]
                    return (
                      <tr key={f.id}>
                        <td className="mono" style={{ color: 'var(--teal)' }}>{f.table_name}</td>
                        <td className="mono" style={{ color: 'var(--tx2)' }}>{f.field_name}{f.is_key && <span style={{ fontSize: 8, color: 'var(--teal)', marginLeft: 4 }}>key</span>}</td>
                        <td style={{ color: 'var(--tx1)', fontWeight: 500 }}>{f.display_name}</td>
                        <td><input className="inp" value={e?.data_type ?? ''} onChange={ev => patch(f.id, { data_type: ev.target.value })} /></td>
                        <td style={{ verticalAlign: 'top' }}><textarea className="inp-area" rows={2} value={e?.description ?? ''} onChange={ev => patch(f.id, { description: ev.target.value })} /></td>
                        <td style={{ textAlign: 'center' }}>
                          <input type="checkbox" checked={!!e?.included} onChange={ev => patch(f.id, { included: ev.target.checked })} style={{ accentColor: 'var(--teal)' }} />
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button className={`tick-btn${e?.approved ? ' saved' : ''}`} onClick={() => patch(f.id, { approved: !e?.approved })}>✓</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8, padding: '10px 14px', background: 'var(--bg2)', borderTop: '1px solid var(--bd)' }}>
              <button className="btn btn-primary btn-sm" onClick={() => void saveDomain()}>Save &amp; close</button>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginTop: 16, borderColor: 'var(--teal)', textAlign: 'center', padding: 20 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)', marginBottom: 6 }}>Save to Relius Knowledge Base</div>
        <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 14 }}>
          Once saved, every migration project can select tables straight from this catalogue.
        </div>
        <button
          className="btn btn-primary"
          style={{ padding: '8px 22px' }}
          onClick={() => domains.length ? void saveReliusKB() : notify('Analyse the schema first', 'amber')}
        >
          ✓ Save Schema to Knowledge Base
        </button>
      </div>
    </>
  )
}
