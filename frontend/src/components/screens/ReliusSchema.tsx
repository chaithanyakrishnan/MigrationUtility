// components/screens/ReliusSchema.tsx — Relius KB step 1: upload + analyse schema.
import { useState } from 'react'
import { useStore } from '@/store'
import { useStagedProgress, ProgressPhase } from '@/hooks/useStagedProgress'

const RELIUS_PHASES: ProgressPhase[] = [
  { at: 0,  message: 'Uploading the schema export…' },
  { at: 15, message: 'Extracting text & tables from the document…' },
  { at: 40, message: 'Identifying tables, fields & relationships…' },
  { at: 65, message: 'Grouping fields into business domains…' },
  { at: 85, message: 'Building the Relius catalogue…' },
]

export default function ReliusSchema() {
  const analyzeRelius   = useStore(s => s.analyzeRelius)
  const analyzing       = useStore(s => s.reliusAnalyzing)
  const reliusCatalog   = useStore(s => s.reliusCatalog)
  const kbStatus        = useStore(s => s.kbStatus)
  const go              = useStore(s => s.go)
  const notify          = useStore(s => s.notify)
  const [file, setFile] = useState<File | null>(null)
  const [rebuild, setRebuild] = useState(false)
  const progress = useStagedProgress(analyzing, RELIUS_PHASES)

  const analysed = !!reliusCatalog && reliusCatalog.domains.length > 0
  const stats = reliusCatalog?.stats ?? {}

  // KB already built from a previous session?
  const kb = kbStatus?.relius
  const built = !!kb?.built
  const kbStats = kb?.stats ?? {}
  const builtAt = kb?.built_at ? new Date(kb.built_at).toLocaleString() : null

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); notify(`${f.name} ready — click Analyse Relius Schema`, 'teal') }
  }

  // When the KB is already available and the user hasn't chosen to rebuild,
  // show a friendly status panel with Review + Re-upload options instead of
  // dropping them straight onto an empty upload box.
  const showBuildFlow = !built || rebuild

  return (
    <>
      {built && !rebuild && (
        <>
          <div className="notice ng">
            <span className="nicon">✅</span>
            <span>
              A Relius Knowledge Base is already available — you don't need to upload the schema again
              unless it has changed.
            </span>
          </div>

          <div className="card" style={{ borderColor: 'var(--green)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <span style={{ fontSize: 20 }}>🗂️</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)' }}>Relius Knowledge Base is built</div>
                <div style={{ fontSize: 11, color: 'var(--tx3)', marginTop: 2 }}>
                  {builtAt ? `Last built ${builtAt}` : 'Ready to use'}
                </div>
              </div>
              <span className="tag tg" style={{ fontSize: 9 }}>✓ Available</span>
            </div>

            <div className="g3" style={{ gap: 8, marginBottom: 14 }}>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Tables</div><div className="sval t" style={{ fontSize: 18 }}>{kbStats.tables ?? '—'}</div></div>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Domains</div><div className="sval t" style={{ fontSize: 18 }}>{kbStats.domains ?? '—'}</div></div>
              <div className="scard" style={{ marginBottom: 0 }}><div className="slabel">Total fields</div><div className="sval t" style={{ fontSize: 18 }}>{kbStats.fields ?? '—'}</div></div>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-primary btn-sm" onClick={() => go('s2')}>Review Knowledge Base →</button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setRebuild(true); setFile(null) }}>
                ⬆️ Re-upload schema (rebuild)
              </button>
            </div>
            <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 10 }}>
              Rebuilding re-parses a fresh schema export and replaces the current catalogue.
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
                ? 'Upload a fresh Relius schema export to re-parse and rebuild the Knowledge Base. This replaces the current catalogue.'
                : 'Upload Relius schema export files. The engine parses and catalogues all tables, fields and relationships into the Relius Knowledge Base.'}
            </span>
          </div>

          {rebuild && (
            <div style={{ marginBottom: 10 }}>
              <button className="btn btn-ghost btn-xs" onClick={() => { setRebuild(false); setFile(null) }}>← Cancel rebuild</button>
            </div>
          )}

          <div className="conn-card" style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 16 }}>🗂️</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>Source — Relius schema</div>
                <div className="mono" style={{ fontSize: 10, color: 'var(--tx3)' }}>SQL DDL · JSON · XLSX · CSV · TXT · PDF · DOCX</div>
              </div>
              <div className={`conn-dot${file || analysed ? ' on' : ''}`} />
              <span style={{ fontSize: 11, color: file || analysed ? 'var(--teal)' : 'var(--tx3)' }}>
                {analysed ? 'Parsed ✓' : file ? `✓ ${file.name}` : 'No file uploaded'}
              </span>
            </div>
            <label className="upzone" style={{ marginBottom: 10, padding: 12 }}>
              <input type="file" accept=".sql,.json,.xlsx,.csv,.txt,.ddl,.pdf,.docx" onChange={onFile} />
              <span style={{ fontSize: 20 }}>⬆️</span>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500 }}>Drop Relius schema export or click to browse</div>
                <div style={{ fontSize: 10, color: 'var(--tx3)', marginTop: 2 }}>SQL DDL · JSON · XLSX · CSV · TXT · PDF · DOCX</div>
              </div>
            </label>

            <div className="g4" style={{ gap: 8 }}>
              {[
                ['Tables found', stats.tables], ['Domains', stats.domains],
                ['Total fields', stats.fields], ['Domains', reliusCatalog?.domains.length],
              ].map(([label, val], i) => (
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
                {analysed ? 'Relius schema analysis complete' : 'Analyse the Relius schema to build the catalogue'}
              </div>
              <button
                className="btn btn-primary btn-sm"
                disabled={analyzing || !file}
                title={file ? '' : 'Upload a schema file first'}
                onClick={() => analyzeRelius(file ?? undefined)}
              >
                {analyzing ? `Analysing… ${progress.pct}%` : analysed ? '✓ Re-analyse' : '▶ Analyse Relius Schema'}
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
                ? <span style={{ color: 'var(--green)' }}>✓ {stats.tables} tables · {stats.fields} fields · {stats.domains} domains catalogued into the Relius KB.</span>
                : <span style={{ color: 'var(--tx3)' }}>Upload a schema file, then click Analyse Relius Schema…</span>}
            </div>
          </div>

          {analysed && (
            <div className="card" style={{ borderColor: 'var(--teal)', textAlign: 'center', padding: 20 }}>
              <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 14 }}>
                Schema catalogued. Continue to review and approve each domain before saving to the Knowledge Base.
              </div>
              <button className="btn btn-primary" style={{ padding: '8px 22px' }} onClick={() => go('s2')}>
                Continue to Review →
              </button>
            </div>
          )}
        </>
      )}
    </>
  )
}
