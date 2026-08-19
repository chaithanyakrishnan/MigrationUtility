// hooks/useStagedProgress.ts — friendly progress for long-running analyse calls.
//
// The backend analyse endpoints are single blocking requests (text extraction +
// OCR on embedded images can take several seconds), so there is no real server
// stream to read. This hook drives a believable, easing progress bar on the
// client: it climbs toward ~95% while the request is in flight, then snaps to
// 100% the moment the call resolves. The `phases` map a percentage to a
// human-readable message so the user always sees *what* is happening, not just
// a spinner.
import { useEffect, useRef, useState } from 'react'

export interface ProgressPhase {
  at: number       // show `message` once pct has reached this threshold
  message: string
}

export interface StagedProgress {
  pct: number      // 0–100, rounded
  message: string
  visible: boolean // true while running or during the brief 100% flourish
  done: boolean
}

export function useStagedProgress(active: boolean, phases: ProgressPhase[]): StagedProgress {
  const [pct, setPct] = useState(0)
  const wasActive = useRef(false)

  useEffect(() => {
    if (active) {
      wasActive.current = true
      setPct(p => (p < 4 ? 4 : p))
      // Ease toward 95% — fast at first, slowing as it approaches the ceiling.
      const id = setInterval(() => {
        setPct(p => (p >= 95 ? 95 : p + Math.max(0.4, (96 - p) * 0.045)))
      }, 180)
      return () => clearInterval(id)
    }
    // Request finished (or was never started). If we were showing progress,
    // snap to 100% for a beat, then reset.
    if (wasActive.current) {
      wasActive.current = false
      setPct(100)
      const t = setTimeout(() => setPct(0), 800)
      return () => clearTimeout(t)
    }
  }, [active])

  const rounded = Math.round(pct)
  const message =
    rounded >= 100
      ? 'Finalising catalogue…'
      : phases.slice().reverse().find(p => rounded >= p.at)?.message ?? phases[0]?.message ?? ''

  return { pct: rounded, message, visible: active || pct > 0, done: rounded >= 100 }
}
