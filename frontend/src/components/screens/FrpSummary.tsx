// components/screens/FrpSummary.tsx — FRP KB step 5: final summary + save.
import { useEffect } from 'react'
import { useStore } from '@/store'

export default function FrpSummary() {
  const frpCatalog    = useStore(s => s.frpCatalog)
  const frpTxnCatalog = useStore(s => s.frpTxnCatalog)
  const loadFrpCatalog = useStore(s => s.loadFrpCatalog)
  const loadFrpTxn    = useStore(s => s.loadFrpTxn)
  const saveFrpKB     = useStore(s => s.saveFrpKB)

  useEffect(() => { if (!frpCatalog) void loadFrpCatalog() }, [frpCatalog, loadFrpCatalog])
  useEffect(() => { if (!frpTxnCatalog) void loadFrpTxn() }, [frpTxnCatalog, loadFrpTxn])

  const records = frpCatalog?.records ?? []
  const cards = frpTxnCatalog?.cards ?? []
  const elements = records.reduce((n, r) => n + r.fields.length, 0)
  const recApproved = records.filter(r => r.approved).length
  const txnConfirmed = cards.filter(c => c.has_layout).length
  const txnFields = cards.reduce((n, c) => n + c.fields.length, 0)
  const withLegal = records.reduce((n, r) => n + r.fields.filter(f => f.legal_values?.length).length, 0)

  return (
    <>
      <div className="notice nt">
        <span className="nicon">📋</span>
        <span>Final review — everything below will be saved into the FRP Knowledge Base. Go back to any earlier step if something needs correcting.</span>
      </div>

      <div className="card">
        <div className="ctitle">Schema summary</div>
        <div className="statrow g4">
          <div className="scard"><div className="slabel">Record groups</div><div className="sval t">{records.length}</div></div>
          <div className="scard"><div className="slabel">Data elements</div><div className="sval t">{elements}</div></div>
          <div className="scard"><div className="slabel">Records approved</div><div className="sval g">{recApproved} / {records.length}</div></div>
          <div className="scard"><div className="slabel">With legal values</div><div className="sval a">{withLegal}</div></div>
        </div>
      </div>

      <div className="card">
        <div className="ctitle">Transaction card summary</div>
        <div className="statrow g4">
          <div className="scard"><div className="slabel">Transactions confirmed</div><div className="sval t">{cards.length}</div></div>
          <div className="scard"><div className="slabel">Layout confirmed</div><div className="sval g">{txnConfirmed} / {cards.length}</div></div>
          <div className="scard"><div className="slabel">Fields catalogued</div><div className="sval a">{txnFields}</div></div>
          <div className="scard"><div className="slabel">Load order rows</div><div className="sval t">{frpTxnCatalog?.load_order.length ?? 0}</div></div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
          {cards.map(c => (
            <span key={c.code} className={`tag ${c.has_layout ? 'tg' : 'tgr'}`} style={{ fontFamily: 'var(--mono)' }}>
              {c.code}{c.has_layout ? ' ✓' : ' ⚠'}
            </span>
          ))}
        </div>
      </div>

      <div className="card" style={{ textAlign: 'center', padding: 24, borderColor: 'var(--teal)' }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)', marginBottom: 6 }}>Ready to save</div>
        <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 16 }}>
          This completes the one-time FRP Knowledge Base setup. Every migration project will draw on this catalogue.
        </div>
        <button className="btn btn-primary" style={{ padding: '9px 26px', fontSize: 13 }} onClick={() => void saveFrpKB()}>
          ✓ Save FRP Knowledge Base
        </button>
      </div>
    </>
  )
}
