// components/screens/FrpSchema.tsx — FRP KB step 1: upload + analyse data dictionary.
import { useState } from 'react'
import { useStore } from '@/store'
import { useStagedProgress, ProgressPhase } from '@/hooks/useStagedProgress'

// FRP uploads can be image-heavy Word/PDF docs, so OCR is a real stage here.
const FRP_PHASES: ProgressPhase[] = [
  { at: 0,  message: 'Uploading files to the parser…' },
  { at: 12, message: 'Extracting text from the data dictionaries…' },
  { at: 28, message: 'Running OCR on embedded record images…' },
  { at: 50, message: 'Detecting FRP record layouts & field codes…' },
  { at: 70, message: 'Reading descriptions & legal values…' },
  { at: 86, message: 'Merging files & building the record catalogue…' },
]

export default function FrpSchema() {
  const analyzeFrp   = useStore(s => s.analyzeFrp)
  const analyzing     = useStore(s => s.frpAnalyzing)
  const catalog       = useStore(s => s.frpCatalog)
  const kbStatus      = useStore(s => s.kbStatus)
  const go            = useStore(s => s.go)
  const notify        = useStore(s => s.notify)
  const [files, setFiles] = useState<File[]>([])
  const [rebuild, setRebuild] = useState(false)
  const progress = useStagedProgress(analyzing, FRP_PHASES)

  const analysed = !!catalog && catalog.records.length > 0
  const stats = catalog?.stats ?? {}
  const totalFields = catalog?.records.reduce((n, r) => n + r.fields.length, 0) ?? 0

  // FRP KB already built from a previous session?
  const kb = kbStatus?.frp
  const built = !!kb?.built
  const kbStats = kb?.stats ?? {}
  const builtAt = kb?.built_at ? new Date(kb.built_at).toLocaleString() : null

  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    if (picked.length) {
      setFiles(prev => {
        const seen = new Set(prev.map(f => f.name + f.size))
        return [...prev, ...picked.filter(f => !seen.has(f.name + f.size))]
      })
      notify(`${picked.length} file${picked.length > 1 ? 's' : ''} added — click Analyse FRP Schema`, 'teal')
    }
    e.target.value = ''  // let the same file be re-picked later
  }
  const removeFile = (name: string, size: number) =>
    setFiles(prev => prev.filter(f => !(f.name === name && f.size === size)))
  const clearFiles = () => setFiles([])

  const showBuildFlow = !built || rebuild
  const fmtSize = (b: number) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

  return (
    <>
      {built && !rebuild && (
        <>
          <div className="notice ng">
            <span className="nicon">✅</span>
            <span>
              An FRP Knowledge Base is already available — you don't need to upload the schema again
              unless it has changed.
            </span>
          </div>

          <div className="card" style={{ borderColor: 'var(--green)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <span style={{ fontSize: 20 }}>🗂️</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)' }}>FRP Knowledge Base is built</div>
                <div style={{ fontSize: 11, color: 'var(--tx3)', marginTop: 2 }}>
                  {builtAt ? `Last built ${builtAt}` : 'Ready to use'}
                </div>
              </div>
              <span className="tag tg" style={{ fontSize: 9 }}>✓ Available</span>
            </div>

            <div className="g4" style={{ gap: 8, marginBottom: 14 }}>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Record groups</div><div className="sval t" style={{ fontSize: 18 }}>{kbStats.records ?? '—'}</div></div>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Data elements</div><div className="sval t" style={{ fontSize: 18 }}>{kbStats.elements ?? '—'}</div></div>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Transaction cards</div><div className="sval g" style={{ fontSize: 18 }}>{kbStats.txn_count ?? '—'}</div></div>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Card fields</div><div className="sval g" style={{ fontSize: 18 }}>{kbStats.txn_fields ?? '—'}</div></div>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-primary btn-sm" onClick={() => go('s4')}>Review Knowledge Base →</button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setRebuild(true); clearFiles() }}>
                ⬆️ Re-upload schema (rebuild)
              </button>
            </div>
            <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 10 }}>
              Rebuilding re-parses fresh data dictionaries and replaces the current record catalogue.
              Transaction-card layouts and constants are reviewed in the later steps.
            </div>
          </div>
        </>
      )}

      {showBuildFlow && (
        <>
          <div className="notice nt">
            <span className="nicon">ℹ️</span>
            <span>
              {rebuild
                ? 'Upload one or more fresh FRP data dictionaries to re-parse and rebuild the record catalogue. This replaces the current records.'
                : 'Upload one or more FRP data dictionary and record definition files. The engine parses every file and merges all target records, field definitions and relationships.'}
            </span>
          </div>

          {rebuild && (
            <div style={{ marginBottom: 10 }}>
              <button className="btn btn-ghost btn-xs" onClick={() => { setRebuild(false); clearFiles() }}>← Cancel rebuild</button>
            </div>
          )}

          <div className="conn-card" style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 16 }}>💾</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>Target — FRP schema</div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--tx3)' }}>Data dictionary · record definitions · field catalogue</div>
              </div>
              <div className={`conn-dot${files.length || analysed ? ' on' : ''}`} />
              <span style={{ fontSize: 11, color: files.length || analysed ? 'var(--teal)' : 'var(--tx3)' }}>
                {analysed ? 'Parsed ✓' : files.length ? `${files.length} file${files.length > 1 ? 's' : ''} ready` : 'No files uploaded'}
              </span>
            </div>
            <label className="upzone" style={{ marginBottom: 10, padding: 12 }}>
              <input type="file" multiple accept=".sql,.json,.xlsx,.csv,.txt,.ddl,.pdf,.docx" onChange={onFiles} />
              <span style={{ fontSize: 20 }}>⬆️</span>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500 }}>Drop FRP data dictionaries or click to browse</div>
                <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 2 }}>Select multiple files · SQL DDL · JSON · XLSX · CSV · TXT · PDF · DOCX</div>
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

            <div className="g4" style={{ gap: 8 }}>
              {[['Record groups', stats.records ?? catalog?.records.length], ['Data elements', totalFields || stats.elements],
                ['With legal values', catalog?.records.reduce((n, r) => n + r.fields.filter(f => f.legal_values?.length).length, 0)],
                ['Records', catalog?.records.length]].map(([label, val], i) => (
                <div className="scard" key={i} style={{ marginBottom: 0 }}>
                  <div className="slabel">{label}</div>
                  <div className="sval t" style={{ fontSize: 18 }}>{val ?? '—'}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 500 }}>
                {analysed ? 'FRP schema analysis complete' : 'Analyse the FRP schema to build the catalogue'}
              </div>
              <button
                className="btn btn-primary btn-sm"
                disabled={analyzing || files.length === 0}
                title={files.length ? '' : 'Upload one or more data dictionary files first'}
                onClick={() => analyzeFrp(files)}
              >
                {analyzing ? `Analysing… ${progress.pct}%` : analysed ? '✓ Re-analyse' : `▶ Analyse FRP Schema${files.length > 1 ? ` (${files.length} files)` : ''}`}
              </button>
            </div>
            <div className="progress-bar-wrap">
              <div
                className="progress-bar-fill"
                style={{ width: progress.visible ? `${progress.pct}%` : analysed ? '100%' : '0%' }}
              />
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
                ? <span style={{ color: 'var(--green)' }}>✓ {catalog?.records.length} record groups · {totalFields} data elements catalogued.</span>
                : <span style={{ color: 'var(--tx3)' }}>Upload one or more files, then click Analyse FRP Schema…</span>}
            </div>
          </div>

          {analysed && (
            <div className="card" style={{ borderColor: 'var(--teal)', textAlign: 'center', padding: 20 }}>
              <button className="btn btn-primary" style={{ padding: '8px 22px' }} onClick={() => go('s4')}>
                Continue to Review →
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}
