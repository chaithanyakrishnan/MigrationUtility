// components/layout/Bottombar.tsx
// Flow-aware bottom navigation (Back / Continue) driven by SCREEN_META.
import { useStore } from '@/store'
import { SCREEN_META, flowLabel, type ScreenId } from '@/nav'

export default function Bottombar() {
  const currentScreen = useStore(s => s.currentScreen)
  const go            = useStore(s => s.go)
  if (currentScreen === 'home' || currentScreen === 's-obs') return null

  const meta = SCREEN_META[currentScreen as Exclude<ScreenId, 'home' | 's-obs'>]
  if (!meta) return null

  return (
    <div className="bottombar">
      <div className="phase-info">
        <strong>{flowLabel(meta.flow)} · step {meta.idx} of {meta.total}</strong> — {meta.label}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button className="btn btn-ghost btn-sm" onClick={() => go((meta.prev ?? 'home') as ScreenId)}>
          ← Back
        </button>
        {meta.next && (
          <button className="btn btn-primary btn-sm" onClick={() => go(meta.next as ScreenId)}>
            Continue →
          </button>
        )}
      </div>
    </div>
  )
}
