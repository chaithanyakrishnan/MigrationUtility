// components/screens/TransactionCards.tsx — mig step 3: review + approve card layouts.
import { useEffect, useState } from 'react'
import { useStore } from '@/store'

export default function TransactionCards() {
  const cards            = useStore(s => s.projectCards)
  const loadProjectCards = useStore(s => s.loadProjectCards)
  const approveCard      = useStore(s => s.approveProjectCard)
  const go               = useStore(s => s.go)
  const notify           = useStore(s => s.notify)
  const [active, setActive] = useState<string | null>(null)

  useEffect(() => { void loadProjectCards() }, [loadProjectCards])
  useEffect(() => { if (!active && cards.length) setActive(cards[0].code) }, [cards, active])

  const cur = cards.find(c => c.code === active) ?? null
  const approvedCount = cards.filter(c => c.approved).length
  const allApproved = cards.length > 0 && approvedCount === cards.length

  const approveAll = async () => { for (const c of cards) if (!c.approved) await approveCard(c.code) }

  if (!cards.length) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: 40 }}>
        <div style={{ fontSize: 12, color: 'var(--tx3)' }}>
          No approved mappings yet — go back to AI Mapping and confirm at least one field.
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="notice nt">
        <span className="nicon">🗂️</span>
        <span>Approved field mappings are grouped by FRP transaction card. Each tab shows the fixed-width card layout — review, then approve each card.</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {cards.map(c => {
            const isActive = c.code === active
            const cls = isActive ? { borderColor: 'var(--teal)', background: 'var(--tealdim)', color: 'var(--teal)' }
              : c.approved ? { borderColor: 'var(--green)', background: 'var(--greendim)', color: 'var(--green)' } : {}
            return (
              <button key={c.code} className="btn btn-ghost btn-xs" style={{ fontFamily: 'var(--mono)', ...cls }} onClick={() => setActive(c.code)}>
                {c.approved ? '✓ ' : ''}{c.code}{c.has_layout ? '' : ' ⚠'}
              </button>
            )
          })}
        </div>
        <button className="btn btn-primary btn-xs" onClick={() => void approveAll()}>✓ Approve all cards</button>
      </div>

      {cur && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: 'var(--bg1)', borderBottom: '1px solid var(--bd)' }}>
            <span style={{ fontSize: 12, fontWeight: 500 }}>Card:</span>
            <span className="tag tt" style={{ fontSize: 10, fontFamily: 'var(--mono)' }}>{cur.code}</span>
            <span className="tag tgr" style={{ fontSize: 9 }}>Record length: {cur.record_length} chars · {cur.has_layout ? 'layout confirmed' : 'header shell only'}</span>
            <button className="btn btn-ghost btn-xs" style={{ marginLeft: 'auto' }} onClick={() => void approveCard(cur.code)}>✓ Approve this card</button>
          </div>
          <div className="mrow" style={{ gridTemplateColumns: '70px 70px 1fr 1fr 90px', background: 'var(--bg1)' }}>
            {['Columns', 'Length', 'FRP field name', 'Relius mapped field', 'Type'].map(h => (
              <div key={h} className="mcell" style={{ fontSize: 10, color: 'var(--tx3)', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 500 }}>{h}</div>
            ))}
          </div>
          {cur.fields.map((f, i) => (
            <div key={i} className="mrow" style={{ gridTemplateColumns: '70px 70px 1fr 1fr 90px' }}>
              <div className="mcell mono" style={{ color: 'var(--tx2)' }}>{f.col_range}</div>
              <div className="mcell mono" style={{ color: 'var(--gold)' }}>{f.length ?? '—'}</div>
              <div className="mcell">
                <div className="fcode" style={{ color: 'var(--tx1)' }}>{f.frp_name}</div>
                {f.note && <div className="fnote">{f.note}</div>}
              </div>
              <div className="mcell mono" style={{ color: 'var(--tx2)', fontSize: 10 }}>{f.relius_source}</div>
              <div className="mcell"><span className={`tag ${f.field_type === 'direct' ? 'tt' : ['transform', 'crosswalk', 'derived'].includes(f.field_type ?? '') ? 'ta' : 'tr'}`}>{f.field_type}</span></div>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginTop: 16, borderColor: 'var(--teal)', textAlign: 'center', padding: 20 }}>
        <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 14 }}>
          {allApproved ? `${cards.length} transaction card(s) approved — ready for the batch run.` : `${approvedCount} of ${cards.length} cards approved — approve every card before running the batch.`}
        </div>
        <button className="btn btn-primary" style={{ padding: '8px 22px' }}
          onClick={() => allApproved ? go('mig-batch') : notify('Approve all cards before continuing', 'amber')}>
          Continue to Batch Run →
        </button>
      </div>
    </>
  )
}
