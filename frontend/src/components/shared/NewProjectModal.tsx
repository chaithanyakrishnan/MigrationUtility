// components/shared/NewProjectModal.tsx
// Friendly dialog for creating a new migration project (replaces window.prompt).
import { useState } from 'react'

interface Props {
  onClose: () => void
  onCreate: (name: string, client: string) => Promise<void> | void
}

export default function NewProjectModal({ onClose, onCreate }: Props) {
  const [name, setName]     = useState('')
  const [client, setClient] = useState('')
  const [error, setError]   = useState('')
  const [busy, setBusy]     = useState(false)

  const submit = async () => {
    if (name.trim().length < 3) { setError('Project name must be at least 3 characters.'); return }
    setBusy(true)
    try {
      await onCreate(name.trim(), client.trim() || 'Client')
      onClose()
    } catch {
      setError('Could not create the project. Is the backend running?')
      setBusy(false)
    }
  }

  const field: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box', marginTop: 4,
    background: 'var(--bg0)', border: '1px solid var(--bd)', borderRadius: 6,
    color: 'var(--tx1)', fontSize: 13, padding: '8px 10px',
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      }}
    >
      <div onClick={e => e.stopPropagation()} className="card" style={{ width: 'min(440px, 92vw)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 18 }}>📁</span>
          <h2 style={{ margin: 0, fontSize: 15 }}>Create a new migration project</h2>
        </div>
        <p style={{ fontSize: 12, color: 'var(--tx3)', marginTop: 0, marginBottom: 16 }}>
          Give your Relius → FRP migration a name. Any saved schema understanding for this
          product is reused automatically — you'll be prompted on the next screen.
        </p>

        <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--tx2)' }}>
          Project name
          <input
            autoFocus
            style={field}
            value={name}
            placeholder="e.g. Acme 401(k) Migration"
            onChange={e => { setName(e.target.value); setError('') }}
            onKeyDown={e => { if (e.key === 'Enter') void submit() }}
          />
        </label>

        <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--tx2)', display: 'block', marginTop: 12 }}>
          Client name <span style={{ color: 'var(--tx3)', fontWeight: 400 }}>(optional)</span>
          <input
            style={field}
            value={client}
            placeholder="e.g. Acme Corp"
            onChange={e => setClient(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') void submit() }}
          />
        </label>

        {error && (
          <div style={{ fontSize: 12, color: 'var(--red)', marginTop: 10 }}>{error}</div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button className="btn btn-ghost btn-sm" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary btn-sm" onClick={() => void submit()} disabled={busy}>
            {busy ? 'Creating…' : 'Create project'}
          </button>
        </div>
      </div>
    </div>
  )
}
