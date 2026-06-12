import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import LoadingState from '../components/LoadingState'
import type { HistoryData } from '../types'
import { formatTaipeiDateTime } from '../utils/dateTime'

function dotClass(status: string) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'error') return 'bg-red-500'
  if (status === 'running') return 'bg-blue-500'
  return 'bg-gray-400'
}

export default function History() {
  const [selected, setSelected] = useState<string[]>([])
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useQuery<HistoryData>({
    queryKey: ['history'],
    queryFn: () => fetch('/api/history').then((r) => { if (!r.ok) throw new Error(`history fetch failed: ${r.status}`); return r.json() as Promise<HistoryData> }),
  })

  const runs = data?.runs ?? []
  const canCompare = selected.length === 2
  const selectedSet = useMemo(() => new Set(selected), [selected])

  function toggleRun(runId: string) {
    setSelected((current) => {
      if (current.includes(runId)) return current.filter((id) => id !== runId)
      return [...current.slice(-1), runId]
    })
  }

  function openCompare() {
    if (!canCompare) return
    navigate(`/compare?a=${selected[0]}&b=${selected[1]}`)
  }

  return (
    <div className="eda-container">
      <div className="toolbar">
        <div>
          <span className="section-kicker">Run Archive</span>
          <h1 className="page-title">History</h1>
          <p className="page-subtitle">
            Reopen previous Verilog analysis runs or select two records to compare design metrics.
          </p>
        </div>
        <button className="btn-primary" type="button" disabled={!canCompare} onClick={openCompare}>
          Compare selected
        </button>
      </div>

      <div className="surface-card overflow-hidden">
        {isLoading && (
          <LoadingState
            title="Loading run history"
            description="Fetching previous analyses so you can reopen or compare them."
          />
        )}

        {isError && (
          <p className="p-6 text-sm text-red-600">
            Failed to load history: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        )}

        {!isLoading && !isError && !runs.length && (
          <div className="p-6">
            <p className="text-sm text-black/45">No runs yet.</p>
            <Link to="/" className="btn-primary mt-4 inline-flex">Open upload</Link>
          </div>
        )}

        {!isLoading && !isError && runs.map((run) => {
          const checked = selectedSet.has(run.run_id)
          return (
            <div key={run.run_id} className={`history-row ${checked ? 'selected' : ''}`}>
              <input
                className="history-checkbox"
                type="checkbox"
                checked={checked}
                onChange={() => toggleRun(run.run_id)}
                aria-label={`Select ${run.filename} for comparison`}
              />
              <span className={`status-dot ${dotClass(run.status)}`} />
              <Link to={`/analysis/${run.run_id}`} className="min-w-0 truncate font-mono text-sm text-[var(--heading-color)]">
                {run.filename}
              </Link>
              <span className="tag">{run.status}</span>
              <span className="tag">{run.cell_count ?? run.ppa_cell_count ?? 'N/A'} cells</span>
              <span className={run.warning_count ? 'text-xs text-amber-600' : 'text-xs text-black/45'}>
                {run.warning_count ?? 0} warnings
              </span>
              <span className="text-xs text-black/45">
                {formatTaipeiDateTime(run.created_at)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
