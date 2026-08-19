// components/screens/Home.tsx
// v5 launchpad: build both Knowledge Bases once, then launch migration projects.
import { useEffect, useState } from 'react'
import { useStore } from '@/store'
import NewProjectModal from '@/components/shared/NewProjectModal'

export default function Home() {
  const kbStatus     = useStore(s => s.kbStatus)
  const loadKBStatus = useStore(s => s.loadKBStatus)
  const go           = useStore(s => s.go)
  const notify       = useStore(s => s.notify)
  const clearEngage  = useStore(s => s.clearEngagement)
  const createEngage = useStore(s => s.createEngagement)
  const [showNewProject, setShowNewProject] = useState(false)

  useEffect(() => { void loadKBStatus() }, [loadKBStatus])

  const relius = kbStatus?.relius
  const frp   = kbStatus?.frp
  const reliusBuilt = !!relius?.built
  const frpBuilt   = !!frp?.built
  const bothBuilt   = reliusBuilt && frpBuilt

  const handleCreate = async (name: string, client: string) => {
    clearEngage()
    await createEngage(name, client)
    go('mig-tables')
  }

  return (
    <>
      <div className="notice nt">
        <span className="nicon">🚀</span>
        <span>Build both knowledge bases once, then launch as many migration projects as you need from here.</span>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        {/* FRP KB */}
        <div className={`kb-card${frpBuilt ? ' built' : ''}`}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)' }}>🗂️ FRP Knowledge Base</div>
            <span className={`tag ${frpBuilt ? 'tg' : 'tgr'}`} style={{ fontSize: 9 }}>
              {frpBuilt ? '✓ Built' : 'Not built'}
            </span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--tx3)', lineHeight: 1.7 }}>
            {frpBuilt
              ? <>FRP schema and transaction card layouts are catalogued and ready. <strong>{frp?.stats?.records ?? 0} record groups · {frp?.stats?.elements ?? 0} data elements · {frp?.stats?.txn_count ?? 0} transaction cards</strong> ({frp?.stats?.txn_fields ?? 0} fields).</>
              : 'No FRP schema or transaction card layouts loaded yet. Build the FRP KB once — it covers record definitions and transaction card specs used by every future migration project.'}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
            {frpBuilt
              ? <button className="btn btn-ghost btn-sm" onClick={() => go('s3')}>Review Knowledge Base</button>
              : <button className="btn btn-primary btn-sm" onClick={() => go('s3')}>Start FRP KB Setup →</button>}
          </div>
        </div>

        {/* Relius KB */}
        <div className={`kb-card${reliusBuilt ? ' built' : ''}`}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)' }}>🗂️ Relius Knowledge Base</div>
            <span className={`tag ${reliusBuilt ? 'tg' : 'tgr'}`} style={{ fontSize: 9 }}>
              {reliusBuilt ? '✓ Built' : 'Not built'}
            </span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--tx3)', lineHeight: 1.7 }}>
            {reliusBuilt
              ? <>Relius schema is catalogued and ready. <strong>{relius?.stats?.tables ?? 0} tables · {relius?.stats?.domains ?? 0} domains · {relius?.stats?.fields ?? 0} fields</strong>.</>
              : 'No Relius schema loaded yet. Build the Relius KB once — every migration project selects its source tables straight from this catalogue.'}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
            {reliusBuilt
              ? <button className="btn btn-ghost btn-sm" onClick={() => go('s1')}>Review Knowledge Base</button>
              : <button className="btn btn-primary btn-sm" onClick={() => go('s1')}>Start Relius KB Setup →</button>}
          </div>
        </div>
      </div>

      <div className="card" style={{ textAlign: 'center', padding: 26 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--tx1)', marginBottom: 6 }}>Ready to migrate?</div>
        <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 16 }}>
          {bothBuilt
            ? 'Both knowledge bases are ready — launch a new migration project.'
            : 'Build both knowledge bases above before starting a migration project.'}
        </div>
        <button
          className="btn btn-primary"
          disabled={!bothBuilt}
          style={{ padding: '9px 26px', fontSize: 13, opacity: bothBuilt ? 1 : .5 }}
          onClick={() => bothBuilt ? setShowNewProject(true) : notify('Build both knowledge bases first', 'amber')}
        >
          ＋ New Migration Project
        </button>
      </div>

      {showNewProject && (
        <NewProjectModal onClose={() => setShowNewProject(false)} onCreate={handleCreate} />
      )}
    </>
  )
}
