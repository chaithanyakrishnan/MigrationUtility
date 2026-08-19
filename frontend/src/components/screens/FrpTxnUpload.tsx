// components/screens/FrpTxnUpload.tsx — FRP KB step 3: upload transaction card layouts.
import { useState } from 'react'
import { useStore } from '@/store'
import { useStagedProgress, ProgressPhase } from '@/hooks/useStagedProgress'

const TXN_PHASES: ProgressPhase[] = [
  { at: 0,  message: 'Uploading transaction card layouts…' },
  { at: 14, message: 'Extracting text from the layout documents…' },
  { at: 32, message: 'Running OCR on layout screenshots…' },
  { at: 55, message: 'Detecting T-codes & column specifications…' },
  { at: 78, message: 'Grouping cards by domain & building the catalogue…' },
]

export default function FrpTxnUpload() {
  const analyzeFrpTxn = useStore(s => s.analyzeFrpTxn)
  const analyzing      = useStore(s => s.frpTxnAnalyzing)
  const catalog        = useStore(s => s.frpTxnCatalog)
  const go             = useStore(s => s.go)
  const notify         = useStore(s => s.notify)
  const [files, setFiles] = useState<File[]>([])
  const progress = useStagedProgress(analyzing, TXN_PHASES)

  const analysed = !!catalog && catalog.cards.length > 0
  const txnFields = catalog?.cards.reduce((n, c) => n + c.fields.length, 0) ?? 0

  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    if (picked.length) {
      setFiles(prev => {
        const seen = new Set(prev.map(f => f.name + f.size))
        return [...prev, ...picked.filter(f => !seen.has(f.name + f.size))]
      })
      notify(`${picked.length} layout file${picked.length > 1 ? 's' : ''} added — click Analyse`, 'teal')
    }
    e.target.value = ''
  }
  const removeFile = (name: string, size: number) =>
    setFiles(prev => prev.filter(f => !(f.name === name && f.size === size)))
  const clearFiles = () => setFiles([])
  const fmtSize = (b: number) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

  return (
    <>
      <div className="notice nt">
        <span className="nicon">ℹ️</span>
        <span>Upload one or more FRP transaction card layout documents — screenshots, PDFs or exported help pages showing the fixed-width column spec (Tran-Code, Seq-Code and card-specific fields) per T-code. The engine reads every file (OCR included) and catalogues each card.</span>
      </div>

      <div className="conn-card" style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 16 }}>🧾</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>FRP transaction card layouts</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--tx3)' }}>Screenshots, PDFs or DOCX of T-code layout specs</div>
          </div>
          <div className={`conn-dot${files.length || analysed ? ' on' : ''}`} />
          <span style={{ fontSize: 11, color: files.length || analysed ? 'var(--teal)' : 'var(--tx3)' }}>
            {analysed ? 'Analysed ✓' : files.length ? `${files.length} file${files.length > 1 ? 's' : ''} ready` : 'No files uploaded'}
          </span>
        </div>
        <label className="upzone" style={{ marginBottom: 10, padding: 12 }}>
          <input type="file" multiple accept=".pdf,.docx,.png,.jpg,.jpeg,.txt" onChange={onFiles} />
          <span style={{ fontSize: 20 }}>⬆️</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500 }}>Drop transaction layout files or click to browse</div>
            <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 2 }}>Select multiple files · PDF · DOCX · PNG · JPG · TXT — one per T-code or a combined document</div>
          </div>
        </label>

        {files.length > 0 && (
          <div style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <div style={{ fontSize: 10, color: 'var(--tx3)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
                {files.length} file{files.length > 1 ? 's' : ''} queued
              </div>
              <button className="btn btn-ghost btn-xs" onClick={clearFiles}>Clear all</button>
            </div>
            {files.map(f => (
              <div key={f.name + f.size} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', background: 'var(--bg3)', borderRadius: 4, marginBottom: 4 }}>
                <span style={{ fontSize: 12 }}>📄</span>
                <span style={{ flex: 1, fontSize: 11, color: 'var(--teal)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                <span style={{ fontSize: 10, color: 'var(--tx3)', fontFamily: 'var(--mono)' }}>{fmtSize(f.size)}</span>
                <button className="btn btn-ghost btn-xs" onClick={() => removeFile(f.name, f.size)} title="Remove">✕</button>
              </div>
            ))}
          </div>
        )}

        <div className="g2" style={{ gap: 8, marginTop: 10 }}>
          <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Transaction cards detected</div><div className="sval t" style={{ fontSize: 18 }}>{catalog?.cards.length ?? '—'}</div></div>
          <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Fields catalogued</div><div className="sval t" style={{ fontSize: 18 }}>{txnFields || '—'}</div></div>
        </div>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 500 }}>
            {analysed ? 'Transaction layout analysis complete' : 'Analyse the uploaded transaction layouts'}
          </div>
          <button className="btn btn-primary btn-sm" disabled={analyzing} onClick={() => analyzeFrpTxn(files)}>
            {analyzing ? `Analysing… ${progress.pct}%` : analysed ? '✓ Re-analyse' : `▶ Analyse Transaction Cards${files.length > 1 ? ` (${files.length} files)` : ''}`}
          </button>
        </div>
        <div className="progress-bar-wrap">
          <div className="progress-bar-fill" style={{ width: progress.visible ? `${progress.pct}%` : analysed ? '100%' : '0%' }} />
        </div>
        <div className="log-out">
          {progress.visible
            ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: 'var(--teal)', fontFamily: 'var(--mono)', minWidth: 42 }}>{progress.pct}%</span>
                <span style={{ color: 'var(--tx2)' }}>{progress.message}</span>
              </span>
            )
            : analysed
            ? <span style={{ color: 'var(--green)' }}>✓ {catalog?.cards.length} transaction cards recognised · {txnFields} fields catalogued.</span>
            : <span style={{ color: 'var(--tx3)' }}>Upload one or more layout files, then click Analyse Transaction Cards…</span>}
        </div>
      </div>

      {analysed && (
        <div className="card" style={{ textAlign: 'center', padding: 20 }}>
          <button className="btn btn-primary" style={{ padding: '8px 22px' }} onClick={() => go('s5')}>
            Continue to Transaction Review →
          </button>
        </div>
      )}
    </>
  )
}
