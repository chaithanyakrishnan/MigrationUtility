// components/layout/Sidebar.tsx
// v5 KB architecture sidebar: Home · Knowledge Bases (one-time) · Migration Project.
import { useState } from 'react'
import { useStore } from '@/store'
import { SCREEN_META, type ScreenId } from '@/nav'
import NewProjectModal from '@/components/shared/NewProjectModal'

export default function Sidebar() {
  const currentScreen = useStore(s => s.currentScreen)
  const go            = useStore(s => s.go)
  const openObs       = useStore(s => s.openObs)
  const kbStatus      = useStore(s => s.kbStatus)
  const engagement    = useStore(s => s.engagement)
  const notify        = useStore(s => s.notify)
  const clearEngage   = useStore(s => s.clearEngagement)
  const createEngage  = useStore(s => s.createEngagement)
  const [showNewProject, setShowNewProject] = useState(false)

  const reliusBuilt = !!kbStatus?.relius.built
  const frpBuilt   = !!kbStatus?.frp.built
  const bothBuilt   = reliusBuilt && frpBuilt

  // Which nav item is highlighted for the active screen.
  const activeNav =
    currentScreen === 'home' ? 'nav-home'
    : currentScreen === 's-obs' ? 'nav-obs'
    : SCREEN_META[currentScreen as Exclude<ScreenId, 'home' | 's-obs'>]?.navId

  const openKB = (kind: 'relius' | 'frp') => go(kind === 'relius' ? 's1' : 's3')

  const migSteps: { navId: string; screen: ScreenId; num: number; label: string }[] = [
    { navId: 'nav-mig1', screen: 'mig-tables', num: 1, label: 'Select Tables' },
    { navId: 'nav-mig2', screen: 's6',         num: 2, label: 'AI Mapping' },
    { navId: 'nav-mig3', screen: 'mig-cards',  num: 3, label: 'Transaction Cards' },
    { navId: 'nav-mig4', screen: 'mig-batch',  num: 4, label: 'Batch Run' },
  ]

  const handleNewProject = () => {
    if (!bothBuilt) {
      notify('Build both the FRP and Relius Knowledge Bases before starting a project', 'amber')
      return
    }
    setShowNewProject(true)
  }

  const handleCreateProject = async (name: string, client: string) => {
    clearEngage()
    await createEngage(name, client)
    go('mig-tables')
  }

  const migLocked = !bothBuilt || !engagement

  return (
    <div className="sidebar">
      <div className="brand">
        <div className="brand-name">MigrateIQ</div>
        <div className="brand-sub">Relius → FRP Utility</div>
      </div>

      <div className="snav">
        <div className={`ni${activeNav === 'nav-home' ? ' act' : ''}`} onClick={() => go('home')}>
          <span style={{ fontSize: 13 }}>🏠</span>Home
        </div>

        <div className="nlabel" style={{ marginTop: 10 }}>
          Knowledge Bases <span style={{ opacity: .55 }}>· one-time</span>
        </div>
        <div className={`ni${activeNav === 'nav-okb' ? ' act' : ''}`} onClick={() => openKB('frp')}>
          <span style={{ fontSize: 13 }}>🗂️</span>FRP KB
          {frpBuilt && <span className="nbadge g">✓</span>}
        </div>
        <div className={`ni${activeNav === 'nav-rkb' ? ' act' : ''}`} onClick={() => openKB('relius')}>
          <span style={{ fontSize: 13 }}>🗂️</span>Relius KB
          {reliusBuilt && <span className="nbadge g">✓</span>}
        </div>

        <div className="nlabel" style={{ marginTop: 10 }}>Migration Project</div>
        <div
          className="ni"
          onClick={handleNewProject}
          style={{
            border: '1px solid rgba(15,212,184,.3)', background: 'rgba(15,212,184,.07)',
            marginBottom: 4, justifyContent: 'center', gap: 7,
            opacity: bothBuilt ? 1 : .5, cursor: bothBuilt ? 'pointer' : 'not-allowed',
          }}
        >
          <span style={{ fontSize: 13 }}>＋</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--teal)' }}>New Project</span>
        </div>
        {migSteps.map(step => (
          <div
            key={step.navId}
            className={`ni${activeNav === step.navId ? ' act' : ''}${migLocked ? ' locked' : ''}`}
            onClick={() => !migLocked && go(step.screen)}
            title={migLocked ? 'Start a migration project first' : step.label}
          >
            <div className="snum">{step.num}</div>{step.label}
          </div>
        ))}

        <div className="nlabel" style={{ marginTop: 10 }}>Project</div>
        <div className="ni">
          <span style={{ fontSize: 13 }}>📁</span>
          <span>{engagement?.name ?? 'No active project'}</span>
        </div>
      </div>

      <div
        className={`ni${activeNav === 'nav-obs' ? ' act' : ''}`}
        style={{ margin: '0 8px 6px' }}
        onClick={() => openObs()}
      >
        <span style={{ fontSize: 13 }}>📊</span>Observability
      </div>
      <div className="sfooter"><div className="dot6" />Session active · v5.0.0</div>

      {showNewProject && (
        <NewProjectModal
          onClose={() => setShowNewProject(false)}
          onCreate={handleCreateProject}
        />
      )}
    </div>
  )
}
