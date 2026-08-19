// components/screens/Placeholder.tsx
// Temporary screen for flows not yet rebuilt in the current phase.
export default function Placeholder({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: 40 }}>
      <div style={{ fontSize: 22, marginBottom: 10 }}>🚧</div>
      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--tx1)', marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 11, color: 'var(--tx3)' }}>Under construction — {phase}.</div>
    </div>
  )
}
