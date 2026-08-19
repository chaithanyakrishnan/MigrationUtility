// components/layout/StepBar.tsx
// Renders the step bar for the current screen's flow (rkb / okb / mig).
import { useStore } from '@/store'
import { SCREEN_META, flowScreens, type ScreenId } from '@/nav'

export default function StepBar() {
  const currentScreen = useStore(s => s.currentScreen)
  if (currentScreen === 'home' || currentScreen === 's-obs') return null

  const meta = SCREEN_META[currentScreen as Exclude<ScreenId, 'home' | 's-obs'>]
  if (!meta) return null

  const screens = flowScreens(meta.flow)

  return (
    <div className="stepbar">
      {screens.map((sid, i) => {
        const m = SCREEN_META[sid as Exclude<ScreenId, 'home' | 's-obs'>]
        const done = m.idx < meta.idx
        const active = m.idx === meta.idx
        return (
          <div key={sid} style={{ display: 'flex', alignItems: 'center' }}>
            <div className={`si${active ? ' act' : ''}${done ? ' done' : ''}`}>
              <div className="sinum">{done ? '✓' : m.idx}</div>
              <div className="silabel">{m.label}</div>
            </div>
            {i < screens.length - 1 && <div className="sisep" />}
          </div>
        )
      })}
    </div>
  )
}
