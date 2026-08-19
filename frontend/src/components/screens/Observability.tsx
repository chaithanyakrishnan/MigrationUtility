// components/screens/Observability.tsx — real-time migration metrics + audit log.
import { useEffect } from 'react'
import { useStore } from '@/store'

const ATAG: Record<string, string> = { system: 'sys', ai: 'ai', sme: 'sme' }

export default function Observability() {
  const obsData  = useStore(s => s.obsData)
  const loadObs  = useStore(s => s.loadObs)
  const closeObs = useStore(s => s.closeObs)

  useEffect(() => { void loadObs() }, [loadObs])

  const counts = obsData?.counts
  const events = obsData?.events ?? []

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--tx1)' }}>Observability dashboard</div>
          <div style={{ fontSize: 11, color: 'var(--tx3)', marginTop: 2 }}>Migration metrics, AI decisions and the full session audit log</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => void loadObs()}>↻ Refresh</button>
          <button className="btn btn-ghost btn-sm" onClick={() => closeObs()}>✕ Close</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 14 }}>
        <div className="scard"><div className="slabel">Active projects</div><div className="sval t" style={{ fontSize: 22 }}>{counts?.active_projects ?? 0}</div></div>
        <div className="scard"><div className="slabel">Field mappings</div><div className="sval t" style={{ fontSize: 22 }}>{counts?.mappings ?? 0}</div></div>
        <div className="scard"><div className="slabel">Mappings confirmed</div><div className="sval g" style={{ fontSize: 22 }}>{counts?.mappings_approved ?? 0}</div></div>
        <div className="scard"><div className="slabel">Audit events</div><div className="sval p" style={{ fontSize: 22 }}>{counts?.audit_events ?? 0}</div></div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '10px 14px', background: 'var(--bg1)', borderBottom: '1px solid var(--bd)' }}>
          <div style={{ fontSize: 12, fontWeight: 500 }}>Session activity log</div>
          <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 1 }}>Every system, AI and SME action, newest first</div>
        </div>
        <div style={{ maxHeight: 460, overflowY: 'auto' }}>
          {events.length === 0
            ? <div style={{ padding: 24, textAlign: 'center', color: 'var(--tx3)', fontSize: 12 }}>No activity recorded yet.</div>
            : events.map(e => (
                <div key={e.id} className="alog-row">
                  <span className="mono" style={{ fontSize: 10, color: 'var(--tx3)', flexShrink: 0 }}>
                    {e.created_at ? new Date(e.created_at).toLocaleTimeString() : '—'}
                  </span>
                  <span className={`atag ${ATAG[e.actor_type] ?? 'sys'}`}>{e.actor_type.toUpperCase()}</span>
                  <span style={{ color: 'var(--tx2)', fontSize: 11 }}>{e.summary}</span>
                </div>
              ))}
        </div>
      </div>
    </>
  )
}
