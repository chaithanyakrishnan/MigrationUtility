// components/screens/AIMapping.tsx — mig step 2: AI field mapping + T-code assignment.
import { useEffect, useState } from 'react'
import { useStore } from '@/store'

type Filter = 'all' | 'high' | 'review' | 'low'

export default function AIMapping() {
  const projectState        = useStore(s => s.projectState)
  const loadProjectState    = useStore(s => s.loadProjectState)
  const mappings            = useStore(s => s.projectMappings)
  const loadProjectMappings = useStore(s => s.loadProjectMappings)
  const runMapping          = useStore(s => s.runProjectMapping)
  const running             = useStore(s => s.mappingRunning)
  const patchMapping        = useStore(s => s.patchProjectMapping)
  const approveAll          = useStore(s => s.approveAllMappings)
  const go                  = useStore(s => s.go)
  const [filter, setFilter] = useState<Filter>('all')

  // Seed on first visit; otherwise load existing (preserves approvals).
  useEffect(() => {
    (async () => {
      await loadProjectState()
      const st = useStore.getState().projectState
      if (st?.mapping_seeded) await loadProjectMappings()
      else await runMapping()
    })()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const inScope = (m: typeof mappings[number]) =>
    filter === 'all' ? true
    : filter === 'high' ? m.confidence >= 85
    : filter === 'review' ? m.confidence >= 60 && m.confidence < 85
    : m.confidence < 60
  const visible = mappings.filter(inScope)

  const autoApproved = mappings.filter(m => m.confidence >= 85).length
  const needsReview = mappings.filter(m => m.confidence >= 60 && m.confidence < 85).length
  const confirmed = mappings.filter(m => m.approved).length

  const confColor = (c: number) => c >= 85 ? 'var(--green)' : c >= 60 ? 'var(--gold)' : 'var(--red)'

  if (running || (!mappings.length && !projectState?.mapping_seeded)) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0' }}>
        <div className="spin-sm" style={{ width: 40, height: 40, margin: '0 auto' }} />
        <div className="mono" style={{ fontSize: 12, color: 'var(--teal)', marginTop: 14 }}>Running AI mapping engine…</div>
        <div style={{ fontSize: 11, color: 'var(--tx3)', marginTop: 4 }}>Querying knowledge base and RAG store</div>
      </div>
    )
  }

  return (
    <>
      <div className="notice nt">
        <span className="nicon">🤖</span>
        <span>AI has proposed field mappings for your selected tables, plus a best-guess FRP transaction card for each field. Review, edit and confirm below.</span>
      </div>

      <div className="statrow g4">
        <div className="scard"><div className="slabel">Tables in scope</div><div className="sval t">{projectState?.selected_tables.length ?? 0}</div></div>
        <div className="scard"><div className="slabel">Auto-approved</div><div className="sval g">{autoApproved}</div><div className="ssub">≥ 85% confidence</div></div>
        <div className="scard"><div className="slabel">Needs review</div><div className="sval a">{needsReview}</div><div className="ssub">60–84%</div></div>
        <div className="scard"><div className="slabel">Confirmed</div><div className="sval p">{confirmed}</div><div className="ssub">To mapping registry</div></div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--bg1)', borderBottom: '1px solid var(--bd)' }}>
          <div style={{ display: 'flex', gap: 7 }}>
            {(['all', 'high', 'review', 'low'] as Filter[]).map(f => (
              <button key={f} className={`btn btn-ghost btn-xs${filter === f ? ' act' : ''}`} onClick={() => setFilter(f)}>
                {f === 'all' ? 'All' : f === 'high' ? 'High ≥85%' : f === 'review' ? 'Review 60-84%' : 'Gaps <60%'}
              </button>
            ))}
          </div>
          <button className="btn btn-ghost btn-xs" onClick={() => void approveAll()}>✓ Approve all mappings</button>
        </div>

        <div className="mrow" style={{ gridTemplateColumns: '1fr 24px 1fr 95px 100px 75px 60px', background: 'var(--bg1)' }}>
          {['Relius table.field', '', 'FRP table.field', 'Txn Card', 'Confidence', 'Type', 'Confirm'].map((h, i) => (
            <div key={i} className="mcell" style={{ fontSize: 10, color: 'var(--tx3)', textTransform: 'uppercase', letterSpacing: '.06em', fontWeight: 500 }}>{h}</div>
          ))}
        </div>

        {visible.map(m => (
          <div key={m.id} className="mrow" style={{ gridTemplateColumns: '1fr 24px 1fr 95px 100px 75px 60px' }}>
            <div className="mcell">
              <div className="fcode">{m.src_table}.{m.src_field}</div>
              {m.note && <div className="fnote">{m.note}</div>}
            </div>
            <div className="arrcol">→</div>
            <div className="mcell">
              <input className={`inp${m.frp_modified ? ' mod' : ''}`} style={{ color: 'var(--tx1)', fontWeight: 500, marginBottom: 2 }}
                defaultValue={m.frp} onBlur={e => e.target.value !== m.frp && patchMapping(m.id, { frp_override: e.target.value })} />
              <input className={`inp${m.tgt_modified ? ' mod' : ''}`} style={{ marginTop: 2 }}
                defaultValue={m.tgt} onBlur={e => e.target.value !== m.tgt && patchMapping(m.id, { tgt_override: e.target.value })} />
            </div>
            <div className="mcell">
              <input className={`inp${m.txn_modified ? ' mod' : ''}`} placeholder="Unassigned" style={{ fontFamily: 'var(--mono)', textAlign: 'center' }}
                defaultValue={m.txn ?? ''} onBlur={e => (e.target.value || '') !== (m.txn ?? '') && patchMapping(m.id, { txn_override: e.target.value })} />
            </div>
            <div className="mcell">
              <div className="cbwrap" style={{ minWidth: 0, gap: 5 }}>
                <div className="cbbg"><div className="cbfill" style={{ width: `${m.confidence}%`, background: confColor(m.confidence) }} /></div>
                <span className="cbval" style={{ color: confColor(m.confidence), minWidth: 26, fontSize: 10 }}>{m.confidence}%</span>
              </div>
            </div>
            <div className="mcell"><span className={`tag ${m.mapping_type === 'direct' ? 'tt' : ['transform', 'crosswalk', 'derived'].includes(m.mapping_type ?? '') ? 'ta' : 'tr'}`}>{m.mapping_type}</span></div>
            <div className="mcell">
              <button className={`tick-btn${m.approved ? ' saved' : ''}`} onClick={() => patchMapping(m.id, { approved: !m.approved })}>✓</button>
            </div>
          </div>
        ))}
        <div className="pager"><span className="pager-info">{visible.length} mapping{visible.length === 1 ? '' : 's'} shown</span></div>
      </div>

      <div className="card" style={{ marginTop: 16, textAlign: 'center', padding: 20 }}>
        <button className="btn btn-primary" style={{ padding: '8px 22px' }}
          onClick={() => confirmed ? go('mig-cards') : useStore.getState().notify('Confirm at least one mapping first', 'amber')}>
          Continue to Transaction Cards →
        </button>
      </div>
    </>
  )
}
