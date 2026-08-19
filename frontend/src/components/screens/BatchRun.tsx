// components/screens/BatchRun.tsx — mig step 4: run batch + download fixed-width output.
import { useStore } from '@/store'
import { api } from '@/services/api'

export default function BatchRun() {
  const engagement    = useStore(s => s.engagement)
  const batch         = useStore(s => s.projectBatch)
  const runBatch      = useStore(s => s.runProjectBatch)

  const done = !!batch

  return (
    <>
      <div className="notice nt">
        <span className="nicon">⚙️</span>
        <span>Run the batch process to read Relius extraction files and write the FRP transaction card output files, using the mapping and layout config from the previous steps.</span>
      </div>

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--tx1)' }}>Batch extraction &amp; card generation</div>
            <div style={{ fontSize: 11, color: 'var(--tx3)', marginTop: 2 }}>
              {done ? `Complete — ${batch!.files_read} file(s) read, ${batch!.line_count} card line(s) written.` : 'Not started — click Run to begin.'}
            </div>
          </div>
          <button className="btn btn-primary" style={{ padding: '8px 22px' }} onClick={() => void runBatch()}>
            ▶ Run Batch Process
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 12, marginBottom: 12 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="slabel">Relius extraction files read</div>
          <div className="sval t" style={{ fontSize: 26 }}>{batch?.files_read ?? 0}</div>
        </div>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="slabel">Transaction cards written</div>
          <div className="sval g" style={{ fontSize: 26 }}>{batch?.line_count ?? 0}</div>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '10px 14px', background: 'var(--bg1)', borderBottom: '1px solid var(--bd)', fontSize: 12, fontWeight: 500 }}>Batch process log</div>
        <div style={{ maxHeight: 260, overflowY: 'auto', padding: '8px 14px' }}>
          {done
            ? batch!.manifest.map((m, i) => (
                <div key={i} className="batch-logline">Wrote transaction card → <span style={{ color: 'var(--green)' }}>{m}</span></div>
              ))
            : <span style={{ fontSize: 10, color: 'var(--tx3)' }}>Awaiting batch run…</span>}
        </div>
      </div>

      {done && engagement && (
        <div className="card" style={{ textAlign: 'center', padding: 20, borderColor: 'var(--green)' }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--green)', marginBottom: 6 }}>✓ Batch process complete</div>
          <div style={{ fontSize: 11, color: 'var(--tx3)', marginBottom: 14 }}>
            {batch!.files_read} Relius extraction file(s) processed · {batch!.line_count} transaction card line(s) written.
          </div>
          <a className="btn btn-primary" style={{ padding: '8px 22px', textDecoration: 'none' }}
            href={api.project.downloadUrl(engagement.id)} target="_blank" rel="noreferrer">
            ⬇ Download transaction card file (.txt)
          </a>
        </div>
      )}
    </>
  )
}
