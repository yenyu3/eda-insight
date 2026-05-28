import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import type { HistoryData } from '../types'

function dotClass(status: string) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'error') return 'bg-red-500'
  return 'bg-gray-400'
}

export default function History() {
  const { data, isLoading } = useQuery<HistoryData>({
    queryKey: ['history'],
    queryFn: () => fetch('/api/history').then((r) => r.json() as Promise<HistoryData>),
  })

  const runs = data?.runs ?? []

  return (
    <div className="eda-container">
      <div className="mb-10">
        <span className="section-kicker">Run Archive</span>
        <h1 className="page-title">History</h1>
        <p className="page-subtitle">
          Reopen previous Verilog analysis runs and compare their status, timestamps, and synthesis
          footprint.
        </p>
      </div>

      <div className="surface-card overflow-hidden">
        {isLoading && <p className="p-6 text-sm text-black/45">Loading...</p>}

        {!isLoading && !runs.length && (
          <p className="p-6 text-sm text-black/45">No runs yet.</p>
        )}

        {!isLoading && runs.map((run) => (
          <Link key={run.run_id} to={`/analysis/${run.run_id}`} className="history-row">
            <span className={`status-dot ${dotClass(run.status)}`} />
            <span className="min-w-0 truncate font-mono text-sm text-[var(--heading-color)]">
              {run.filename}
            </span>
            {run.ppa_cell_count != null && (
              <span className="tag">{run.ppa_cell_count} cells</span>
            )}
            <span className="text-xs text-black/45">
              {new Date(run.created_at).toLocaleString('zh-TW')}
            </span>
            <span className="tag">{run.status}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
