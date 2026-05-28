import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import MetricCard from '../components/MetricCard'
import type { CompareResult, DiffEntry, HistoryData, RunRecord } from '../types'

function DeltaBadge({ diff }: { diff: DiffEntry | undefined }) {
  if (!diff || diff.delta == null) return <span className="text-xs text-black/40">N/A</span>
  return (
    <span className={`tag ${diff.better ? 'text-emerald-700' : 'text-red-600'}`}>
      {diff.delta > 0 ? '+' : ''}{diff.delta}
      {diff.pct != null && ` (${diff.pct > 0 ? '+' : ''}${diff.pct}%)`}
    </span>
  )
}

function statusDotClass(status: string) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'error') return 'bg-red-500'
  if (status === 'running') return 'bg-blue-500'
  return 'bg-gray-400'
}

function RunSelect({
  label,
  value,
  runs,
  onChange,
}: {
  label: string
  value: string
  runs: RunRecord[]
  onChange: (runId: string) => void
}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = runs.find((run) => run.run_id === value)

  useEffect(() => {
    if (!open) return

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div className="run-select" ref={rootRef}>
      <button
        type="button"
        className={`run-select-trigger ${open ? 'open' : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="run-select-copy">
          <span className="run-select-label">{label}</span>
          {selected ? (
            <>
              <span className="run-select-title">{selected.filename}</span>
              <span className="run-select-meta">
                {new Date(selected.created_at).toLocaleString('zh-TW')}
              </span>
            </>
          ) : (
            <span className="run-select-placeholder">Choose a completed run</span>
          )}
        </span>
        <span className="run-select-chevron" aria-hidden="true" />
      </button>

      {open && (
        <div className="run-select-menu" role="listbox" aria-label={label}>
          {runs.length === 0 && (
            <div className="run-select-empty">No completed runs available.</div>
          )}

          {runs.map((run) => (
            <button
              key={run.run_id}
              type="button"
              role="option"
              aria-selected={run.run_id === value}
              className={`run-select-option ${run.run_id === value ? 'selected' : ''}`}
              onClick={() => {
                onChange(run.run_id)
                setOpen(false)
              }}
            >
              <span className={`status-dot ${statusDotClass(run.status)}`} />
              <span className="min-w-0 flex-1">
                <span className="run-option-title">{run.filename}</span>
                <span className="run-option-meta">
                  {new Date(run.created_at).toLocaleString('zh-TW')}
                  {run.ppa_cell_count != null && ` · ${run.ppa_cell_count} cells`}
                </span>
              </span>
              <span className="tag">{run.status}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Compare() {
  const [runIdA, setRunIdA] = useState('')
  const [runIdB, setRunIdB] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const { data: history } = useQuery<HistoryData>({
    queryKey: ['history'],
    queryFn: () => fetch('/api/history').then((r) => r.json() as Promise<HistoryData>),
  })

  const { data: cmp, isLoading } = useQuery<CompareResult>({
    queryKey: ['compare', runIdA, runIdB],
    queryFn: () =>
      fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id_a: runIdA, run_id_b: runIdB }),
      }).then((r) => r.json() as Promise<CompareResult>),
    enabled: !!submitted && !!runIdA && !!runIdB,
  })

  const runs = history?.runs?.filter((r) => r.status !== 'pending') ?? []

  return (
    <div className="eda-container">
      <div className="mb-10">
        <span className="section-kicker">Design Diff</span>
        <h1 className="page-title">Compare Runs</h1>
        <p className="page-subtitle">
          Select two completed runs and review the movement in cell count, timing, slack, and AI
          tradeoff notes.
        </p>
      </div>

      <section className="surface-card panel mb-5">
        <h2 className="panel-title">Select Versions</h2>
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <RunSelect
            label="Version A"
            value={runIdA}
            runs={runs}
            onChange={(id) => {
              setSubmitted(false)
              setRunIdA(id)
            }}
          />
          <RunSelect
            label="Version B"
            value={runIdB}
            runs={runs}
            onChange={(id) => {
              setSubmitted(false)
              setRunIdB(id)
            }}
          />
          <div className="flex items-center md:self-stretch">
            <button
              onClick={() => setSubmitted(true)}
              disabled={!runIdA || !runIdB || runIdA === runIdB}
              className="btn-primary h-11 px-8"
            >
              Compare
            </button>
          </div>
        </div>
      </section>

      {isLoading && <p className="text-sm text-black/45">Comparing...</p>}

      {cmp && !cmp.error && (
        <section className="surface-card panel space-y-5">
          <div className="grid grid-cols-3 gap-4 border-b border-black/10 pb-4 text-center text-xs font-medium text-black/45">
            <span className="truncate">{cmp.version_a?.filename}</span>
            <span>Delta</span>
            <span className="truncate">{cmp.version_b?.filename}</span>
          </div>

          {(['cell_count', 'critical_path_ns', 'slack_ns'] as const).map((key) => (
            <div key={key} className="grid grid-cols-3 items-center gap-4">
              <MetricCard label={key} value={cmp.version_a?.[key]} unit={key.includes('ns') ? 'ns' : ''} />
              <div className="text-center"><DeltaBadge diff={cmp.diff?.[key]} /></div>
              <MetricCard label={key} value={cmp.version_b?.[key]} unit={key.includes('ns') ? 'ns' : ''} />
            </div>
          ))}

          {cmp.ai_tradeoff && (
            <p className="border-t border-black/10 pt-4 text-sm leading-relaxed text-black/60">
              {cmp.ai_tradeoff}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
