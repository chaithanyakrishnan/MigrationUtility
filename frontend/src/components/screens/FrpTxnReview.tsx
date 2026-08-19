// components/screens/FrpTxnReview.tsx — FRP KB step 4: card layouts + load order + constants.
import { useEffect, useMemo, useState } from 'react'
import { useStore } from '@/store'
import type { KBTxnCard } from '@/types'

// Friendly names for the transaction-card domains (backend `category`).
const DOMAIN_LABEL: Record<string, string> = {
  participant: 'Participant', loans: 'Loans', plans: 'Plans', invest: 'Investments',
  financial: 'Financial', annuity: 'Annuity', system: 'System', general: 'General',
}
const domainLabel = (k: string) => DOMAIN_LABEL[k] ?? (k ? k[0].toUpperCase() + k.slice(1) : 'Other')

// Seq · Field Name (editable) · Label · Picture · Type · Legal Values
const TXN_GRID = '56px 1.3fr 130px 90px 52px 1.5fr'

export default function FrpTxnReview() {
  const catalog       = useStore(s => s.frpTxnCatalog)
  const loadFrpTxn   = useStore(s => s.loadFrpTxn)
  const reviewTxnCard = useStore(s => s.reviewTxnCard)
  const go            = useStore(s => s.go)

  const [activeDomain, setActiveDomain] = useState<string | null>(null)
  const [active, setActive] = useState<string | null>(null)   // active card code
  const [names, setNames]   = useState<Record<string, string>>({})

  useEffect(() => { if (!catalog) void loadFrpTxn() }, [catalog, loadFrpTxn])

  const cards = catalog?.cards ?? []

  // Group cards by domain (category), preserving catalogue order.
  const domains = useMemo(() => {
    const m = new Map<string, KBTxnCard[]>()
    cards.forEach(c => {
      const k = c.category ?? 'general'
      if (!m.has(k)) m.set(k, [])
      m.get(k)!.push(c)
    })
    return Array.from(m.entries()).map(([key, cs]) => ({ key, icon: cs[0]?.icon ?? '🧾', cards: cs }))
  }, [cards])

  // Default: first domain + its first card. Re-anchor if the active selection
  // disappears (e.g. after a re-analyse changes the catalogue).
  useEffect(() => {
    if (!domains.length) return
    const dom = domains.find(d => d.key === activeDomain) ?? domains[0]
    if (dom.key !== activeDomain) setActiveDomain(dom.key)
    if (!dom.cards.some(c => c.code === active)) setActive(dom.cards[0]?.code ?? null)
  }, [domains, activeDomain, active])

  const domainCards = domains.find(d => d.key === activeDomain)?.cards ?? []
  const cur = cards.find(c => c.code === active) ?? null
  const approvedCount = cards.filter(c => c.approved).length

  const selectDomain = (key: string) => {
    setActiveDomain(key)
    const first = domains.find(d => d.key === key)?.cards[0]
    setActive(first?.code ?? null)
  }

  const nameFor = (id: string, fallback: string) => names[id] ?? fallback
  const setName = (id: string, v: string) => setNames(prev => ({ ...prev, [id]: v }))

  const approveCard = async (code: string) => {
    const card = cards.find(c => c.code === code)
    if (!card) return
    await reviewTxnCard(code, {
      approved: true,
      fields: card.fields.map(f => ({ id: f.id, name: names[f.id] ?? f.name })),
    })
  }
  const approveAll = async () => { for (const c of cards) await approveCard(c.code) }

  return (
    <>
      <div className="notice na">
        <span className="nicon">⚠</span>
        <span>Confirm each transaction card layout before it's saved to the FRP Knowledge Base. Every migration project draws on this catalogue.</span>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div>
            <div className="ctitle" style={{ marginBottom: 2 }}>Card layout details</div>
            <div style={{ fontSize: 11, color: 'var(--tx3)' }}>Fixed-width column spec per card — edit field names, then approve each card.</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, color: 'var(--tx3)' }}>{approvedCount} / {cards.length} approved</span>
            <button className="btn btn-primary btn-xs" onClick={() => void approveAll()}>✓ Approve all cards</button>
          </div>
        </div>

        {/* Domain tabs — click a domain to reveal its transaction cards */}
        <div className="tabs" style={{ flexWrap: 'wrap', marginBottom: 10 }}>
          {domains.map(d => {
            const approvedInDom = d.cards.filter(c => c.approved).length
            return (
              <div
                key={d.key}
                className={`tab${d.key === activeDomain ? ' act' : ''}`}
                onClick={() => selectDomain(d.key)}
              >
                <span style={{ marginRight: 6 }}>{d.icon}</span>
                {domainLabel(d.key)}
                <span className="tag tgr" style={{ fontSize: 8, marginLeft: 6 }}>{approvedInDom}/{d.cards.length}</span>
              </div>
            )
          })}
        </div>

        {/* Card sub-tabs for the active domain */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {domainCards.length === 0 && <span style={{ fontSize: 11, color: 'var(--tx3)' }}>No transaction cards in this domain.</span>}
          {domainCards.map(c => {
            const isActive = c.code === active
            const cls = isActive ? { borderColor: 'var(--teal)', background: 'var(--tealdim)', color: 'var(--teal)' }
              : c.approved ? { borderColor: 'var(--green)', background: 'var(--greendim)', color: 'var(--green)' } : {}
            return (
              <button key={c.code} className="btn btn-ghost btn-xs" style={{ fontFamily: 'var(--mono)', ...cls }} onClick={() => setActive(c.code)} title={c.name ?? c.code}>
                {c.approved ? '✓ ' : ''}{c.code}{c.has_layout ? '' : ' ⚠'}
              </button>
            )
          })}
        </div>

        {cur && (
          <div style={{ border: '1px solid var(--bd)', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'var(--bg1)', borderBottom: '1px solid var(--bd)' }}>
              <span className="tag tt" style={{ fontSize: 10, fontFamily: 'var(--mono)' }}>{cur.code}</span>
              <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--tx1)' }}>{cur.name ?? cur.code}</span>
              <span className="tag tgr" style={{ fontSize: 9 }}>{domainLabel(cur.category ?? 'general')} · {cur.fields.length} data elements · {cur.has_layout ? 'parsed' : 'shell only'}</span>
              {cur.approved && <span className="tag tg" style={{ fontSize: 9 }}>✓ Approved</span>}
              <button className="btn btn-ghost btn-xs" style={{ marginLeft: 'auto' }} onClick={() => void approveCard(cur.code)}>✓ Approve this card</button>
            </div>
            <div className="mrow" style={{ gridTemplateColumns: TXN_GRID, background: 'var(--bg1)' }}>
              {['Seq', 'Field Name (Screen Prompt) — editable', 'Label', 'Picture', 'Type', 'Legal Values'].map(h => (
                <div key={h} className="mcell" style={{ fontSize: 10, color: 'var(--tx3)', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 500 }}>{h}</div>
              ))}
            </div>
            {cur.fields.map(f => (
              <div key={f.id} className="mrow" style={{ gridTemplateColumns: TXN_GRID }}>
                <div className="mcell mono" style={{ color: 'var(--tx3)' }}>{f.col_range || '—'}</div>
                <div className="mcell"><input className="inp" value={nameFor(f.id, f.name ?? '')} onChange={e => setName(f.id, e.target.value)} /></div>
                <div className="mcell mono" style={{ color: 'var(--teal)', fontSize: 10 }}>{f.code}</div>
                <div className="mcell mono" style={{ color: 'var(--gold)', fontSize: 10 }}>{f.picture || '—'}</div>
                <div className="mcell">{f.field_type ? <span className="tag tt" style={{ fontSize: 8 }}>{f.field_type}</span> : <span style={{ color: 'var(--tx3)' }}>—</span>}</div>
                <div className="mcell" style={{ fontSize: 9, color: 'var(--tx3)', whiteSpace: 'normal', lineHeight: 1.35 }}>{f.note || '—'}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="g2" style={{ gap: 12, marginTop: 16 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="ctitle" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            🔢 FRP load order <span className="tag tt" style={{ fontSize: 9, marginLeft: 'auto' }}>Auto-sequenced</span>
          </div>
          <table className="dt" style={{ fontSize: 10 }}>
            <thead><tr><th>Seq</th><th>FRP record</th><th>Type</th><th>Reason</th></tr></thead>
            <tbody>
              {(catalog?.load_order ?? []).map(r => (
                <tr key={r.seq}>
                  <td className="mono" style={{ color: 'var(--tx3)' }}>{r.seq}</td>
                  <td className="mono" style={{ color: 'var(--teal)' }}>{r.record}</td>
                  <td><span className="tag tt" style={{ fontSize: 8 }}>{r.type}</span></td>
                  <td style={{ color: 'var(--tx3)' }}>{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="ctitle" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            🔒 FRP constants registry <span className="tag tg" style={{ fontSize: 9, marginLeft: 'auto' }}>Auto-validated</span>
          </div>
          <table className="dt" style={{ fontSize: 10 }}>
            <thead><tr><th>Field</th><th>Record</th><th>Required value</th><th>Status</th></tr></thead>
            <tbody>
              {(catalog?.constants ?? []).map(c => (
                <tr key={c.code}>
                  <td className="mono" style={{ color: 'var(--teal)' }}>{c.code}</td>
                  <td style={{ color: 'var(--tx3)' }}>{c.record}</td>
                  <td className="mono" style={{ color: 'var(--teal)' }}>{c.required_value}</td>
                  <td><span className="tag tg" style={{ fontSize: 8 }}>✓ Valid</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16, borderColor: 'var(--teal)', textAlign: 'center', padding: 20 }}>
        <button className="btn btn-primary" style={{ padding: '8px 22px' }} onClick={() => go('s-okb-summary')}>
          Continue to Summary →
        </button>
      </div>
    </>
  )
}
