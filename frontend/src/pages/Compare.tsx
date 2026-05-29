import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import type { CompareResult, DiffEntry, HistoryData, RunRecord } from '../types'
import { formatTaipeiDateTime } from '../utils/dateTime'

type ViewMode = 'table' | 'visual'
type MetricKey = 'cell_count' | 'wire_count' | 'flip_flop_count' | 'critical_path_ns' | 'slack_ns'

const METRIC_ROWS: Array<{ key: MetricKey; label: string; unit?: string }> = [
  { key: 'cell_count', label: 'Cell count' },
  { key: 'flip_flop_count', label: 'Flip-flops' },
  { key: 'wire_count', label: 'Wire count' },
  { key: 'critical_path_ns', label: 'Critical path', unit: 'ns' },
  { key: 'slack_ns', label: 'Slack', unit: 'ns' },
]

function DeltaBadge({ diff }: { diff: DiffEntry | null | undefined }) {
  if (!diff || diff.delta == null) return <span className="rounded-full border border-black/10 bg-black/[0.03] px-4 py-1 text-sm text-black/45">-</span>
  return (
    <span className={`rounded-full border px-4 py-1 text-sm font-medium ${
      diff.better
        ? 'border-emerald-300 bg-emerald-50 text-emerald-700'
        : 'border-red-300 bg-red-50 text-red-700'
    }`}>
      {diff.delta > 0 ? '+' : ''}{diff.delta}
      {diff.pct != null && ` (${diff.pct > 0 ? '+' : ''}${diff.pct}%)`}
    </span>
  )
}

function formatMetric(value: number | boolean | null | undefined, unit = '') {
  if (value == null) return 'N/A'
  if (typeof value === 'boolean') return value ? 'Passed' : 'Failed'
  return `${value}${unit}`
}

function valueTone(value: number | boolean | null | undefined, diff: DiffEntry | null | undefined, side: 'a' | 'b') {
  if (typeof value === 'boolean') return value ? 'text-emerald-700' : 'text-red-700'
  if (!diff || diff.better == null || diff.delta == null || side === 'a') return 'text-[var(--heading-color)]'
  return diff.better ? 'text-emerald-700' : 'text-red-700'
}

function SkeletonBlock() {
  return (
    <div className="surface-card panel space-y-4">
      {[0, 1, 2].map((row) => (
        <div key={row} className="h-12 animate-pulse rounded-lg bg-black/[0.04]" />
      ))}
    </div>
  )
}

function Gauge({ label, score, tone }: { label: string; score: number; tone: 'a' | 'b' }) {
  const radius = 34
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.max(0, Math.min(score, 10)) / 10) * circumference
  const color = tone === 'a' ? '#378ADD' : '#E24B4A'

  return (
    <div className="flex min-w-0 flex-col items-center gap-3 rounded-xl bg-black/[0.025] p-4 text-center">
      <svg width="86" height="86" viewBox="0 0 86 86" aria-label={`${label} complexity`}>
        <circle cx="43" cy="43" r={radius} fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth="7" />
        <circle
          cx="43"
          cy="43"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 43 43)"
        />
        <text x="43" y="48" textAnchor="middle" className="fill-black text-base font-medium">{score}</text>
      </svg>
      <div className="min-w-0">
        <p className="metric-label mb-1">{label}</p>
        <p className="text-sm text-black/55">{score}/10</p>
      </div>
    </div>
  )
}

function RadarChart({ cmp }: { cmp: CompareResult }) {
  const axes = [
    { label: 'Cell count', a: cmp.version_a.cell_count ?? 0, b: cmp.version_b.cell_count ?? 0 },
    { label: 'Flip-flops', a: cmp.version_a.flip_flop_count ?? 0, b: cmp.version_b.flip_flop_count ?? 0 },
    { label: 'Wire count', a: cmp.version_a.wire_count ?? 0, b: cmp.version_b.wire_count ?? 0 },
    { label: 'Warnings', a: cmp.version_a.warning_count ?? 0, b: cmp.version_b.warning_count ?? 0 },
    { label: 'Complexity', a: cmp.complexity_scores?.a ?? 0, b: cmp.complexity_scores?.b ?? 0 },
  ]
  const cx = 165
  const cy = 150
  const radius = 88
  const maxByAxis = axes.map((axis) => Math.max(axis.a, axis.b, 1))

  function point(index: number, ratio: number, scale = radius) {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / axes.length
    return [cx + Math.cos(angle) * scale * ratio, cy + Math.sin(angle) * scale * ratio]
  }

  function polygon(series: 'a' | 'b') {
    return axes
      .map((axis, index) => {
        const ratio = (series === 'a' ? axis.a : axis.b) / maxByAxis[index]
        return point(index, ratio).join(',')
      })
      .join(' ')
  }

  return (
    <div>
      <svg viewBox="0 0 330 300" className="mx-auto w-full max-w-[430px]" role="img" aria-label="Design profile radar">
        {[0.25, 0.5, 0.75, 1].map((level) => (
          <polygon
            key={level}
            points={axes.map((_, index) => point(index, level).join(',')).join(' ')}
            fill="none"
            stroke="rgba(0,0,0,0.08)"
            strokeWidth="1"
          />
        ))}
        {axes.map((axis, index) => {
          const [x, y] = point(index, 1.18)
          const [x2, y2] = point(index, 1)
          return (
            <g key={axis.label}>
              <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="rgba(0,0,0,0.08)" />
              <text x={x} y={y} textAnchor={x < cx - 10 ? 'end' : x > cx + 10 ? 'start' : 'middle'} className="fill-[#5B85D6] text-[13px]">
                {axis.label}
              </text>
            </g>
          )
        })}
        <polygon points={polygon('a')} fill="rgba(55,138,221,0.12)" stroke="#5B85D6" strokeWidth="3" />
        <polygon points={polygon('b')} fill="rgba(226,75,74,0.10)" stroke="#C95550" strokeWidth="3" />
        {axes.map((_, index) => {
          const [ax, ay] = point(index, axes[index].a / maxByAxis[index])
          const [bx, by] = point(index, axes[index].b / maxByAxis[index])
          return (
            <g key={index}>
              <circle cx={ax} cy={ay} r="4" fill="#5B85D6" />
              <circle cx={bx} cy={by} r="4" fill="#C95550" />
            </g>
          )
        })}
      </svg>
      <div className="mt-4 flex flex-wrap justify-center gap-6 text-sm text-black/60">
        <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 bg-[#5B85D6]" />{cmp.version_a.filename}</span>
        <span className="inline-flex items-center gap-2"><span className="h-0.5 w-5 bg-[#C95550]" />{cmp.version_b.filename}</span>
      </div>
    </div>
  )
}

function CorrectnessCard({ label, passed }: { label: string; passed: boolean | null | undefined }) {
  const isFailed = passed === false
  return (
    <div className={`rounded-xl border p-5 text-center ${isFailed ? 'border-red-200 bg-red-50' : 'border-emerald-200 bg-emerald-50'}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.12em] ${isFailed ? 'text-red-700' : 'text-emerald-700'}`}>
        {label}
      </p>
      <p className={`mt-2 text-lg font-semibold ${isFailed ? 'text-red-700' : 'text-emerald-700'}`}>
        {passed == null ? 'Unknown' : passed ? 'Sim passed' : 'Sim failed'}
      </p>
    </div>
  )
}

function VerdictIcon({ type }: { type: 'leaner' | 'capable' }) {
  return (
    <svg className="verdict-icon-svg" viewBox="0 0 24 24" aria-hidden="true">
      {type === 'leaner' ? (
        <>
          <path d="M5 7h14" />
          <path d="M5 12h10" />
          <path d="M5 17h6" />
        </>
      ) : (
        <>
          <path d="M5 17l5-5 3 3 6-7" />
          <path d="M15 8h4v4" />
        </>
      )}
    </svg>
  )
}

function VerdictCard({
  title,
  description,
  active,
  icon,
}: {
  title: string
  description: string
  active: boolean
  icon: 'leaner' | 'capable'
}) {
  return (
    <div className={`flex gap-4 rounded-xl border p-5 ${active ? 'border-emerald-300 bg-emerald-50' : 'border-black/15 bg-black/[0.025]'}`}>
      <span className={`verdict-icon ${active ? 'active' : ''}`}>
        <VerdictIcon type={icon} />
      </span>
      <div>
        <p className={`text-lg font-semibold ${active ? 'text-emerald-800' : 'text-[var(--heading-color)]'}`}>{title}</p>
        <p className={`mt-2 text-sm leading-relaxed ${active ? 'text-emerald-800/85' : 'text-black/60'}`}>{description}</p>
      </div>
    </div>
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
                {formatTaipeiDateTime(selected.created_at)}
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
                  {formatTaipeiDateTime(run.created_at)}
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
  const [searchParams] = useSearchParams()
  const [runIdA, setRunIdA] = useState(() => searchParams.get('a') ?? '')
  const [runIdB, setRunIdB] = useState(() => searchParams.get('b') ?? '')
  const [submitted, setSubmitted] = useState(() => !!searchParams.get('a') && !!searchParams.get('b'))
  const [view, setView] = useState<ViewMode>('table')

  const { data: history } = useQuery<HistoryData>({
    queryKey: ['history'],
    queryFn: () => fetch('/api/history').then((r) => { if (!r.ok) throw new Error(`history fetch failed: ${r.status}`); return r.json() as Promise<HistoryData> }),
  })

  const { data: cmp, isLoading } = useQuery<CompareResult>({
    queryKey: ['compare', runIdA, runIdB],
    queryFn: () =>
      fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id_a: runIdA, run_id_b: runIdB }),
      }).then((r) => { if (!r.ok) throw new Error(`compare fetch failed: ${r.status}`); return r.json() as Promise<CompareResult> }),
    enabled: !!submitted && !!runIdA && !!runIdB,
  })

  const runs = history?.runs?.filter((r) => r.status !== 'pending') ?? []
  const recommended = cmp?.recommended === 'a' ? cmp.version_a : cmp?.recommended === 'b' ? cmp.version_b : null

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

      {isLoading && <SkeletonBlock />}

      {cmp && !cmp.error && (
        <div className="space-y-5">
          <div className="flex justify-end">
            <div className="segmented">
              {(['table', 'visual'] as ViewMode[]).map((mode) => (
                <button key={mode} type="button" className={view === mode ? 'active' : ''} onClick={() => setView(mode)}>
                  {mode === 'table' ? 'Table' : 'Visual'}
                </button>
              ))}
            </div>
          </div>

          {view === 'table' && (
            <section className="surface-card panel overflow-hidden">
              <h2 className="panel-title mb-5">Metrics Diff</h2>
              <div className="grid grid-cols-[1.15fr_1fr_0.9fr_1fr] items-center gap-3 border-b border-black/15 pb-4 text-sm font-medium text-black/55">
                <span>Metric</span>
                <span className="truncate text-right md:text-left">Version A</span>
                <span className="text-center">Delta</span>
                <span className="truncate text-right">Version B</span>
              </div>

              <div className="divide-y divide-black/10">
                {METRIC_ROWS.map(({ key, label, unit }) => {
                  const valueA = cmp.version_a[key]
                  const valueB = cmp.version_b[key]
                  const diff = cmp.diff?.[key]
                  return (
                    <div key={key} className="grid grid-cols-[1.15fr_1fr_0.9fr_1fr] items-center gap-3 py-5">
                      <span className="text-sm font-medium text-black/65 md:text-base">{label}</span>
                      <span className={`truncate text-right text-xl font-semibold md:text-left md:text-2xl ${valueTone(valueA, diff, 'a')}`}>
                        {formatMetric(valueA, unit)}
                      </span>
                      <span className="text-center"><DeltaBadge diff={diff} /></span>
                      <span className={`truncate text-right text-xl font-semibold md:text-2xl ${valueTone(valueB, diff, 'b')}`}>
                        {formatMetric(valueB, unit)}
                      </span>
                    </div>
                  )
                })}

                <div className="grid grid-cols-[1.15fr_1fr_0.9fr_1fr] items-center gap-3 py-5">
                  <span className="text-sm font-medium text-black/65 md:text-base">Simulation</span>
                  <span className={`truncate text-right text-lg font-semibold md:text-left md:text-xl ${valueTone(cmp.version_a.sim_passed, null, 'a')}`}>
                    {formatMetric(cmp.version_a.sim_passed)}
                  </span>
                  <span className="text-center"><DeltaBadge diff={null} /></span>
                  <span className={`truncate text-right text-lg font-semibold md:text-xl ${valueTone(cmp.version_b.sim_passed, null, 'b')}`}>
                    {formatMetric(cmp.version_b.sim_passed)}
                  </span>
                </div>
              </div>
            </section>
          )}

          {view === 'visual' && (
            <section className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
              <div className="surface-card panel">
                <h2 className="panel-title">Design Profile — Radar</h2>
                <p className="mb-6 text-sm text-black/55">Smaller shape means a leaner design.</p>
                <RadarChart cmp={cmp} />
              </div>
              <div className="grid gap-5">
                <div className="surface-card panel">
                  <h2 className="panel-title">Complexity Score</h2>
                  <p className="mb-6 text-sm text-black/55">Lower is simpler design.</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Gauge label={cmp.version_a.filename} score={cmp.complexity_scores?.a ?? 0} tone="a" />
                    <Gauge label={cmp.version_b.filename} score={cmp.complexity_scores?.b ?? 0} tone="b" />
                  </div>
                </div>
                <div className="surface-card panel">
                  <h2 className="panel-title">Correctness</h2>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <CorrectnessCard label="Version A" passed={cmp.version_a.sim_passed} />
                    <CorrectnessCard label="Version B" passed={cmp.version_b.sim_passed} />
                  </div>
                </div>
              </div>
            </section>
          )}

          <section className="surface-card panel">
            <h2 className="panel-title mb-5">Which One to Pick?</h2>
            <div className="space-y-4">
              <VerdictCard
                title={`${cmp.version_a.filename} — leaner`}
                description={`Fewer cells (${formatMetric(cmp.version_a.cell_count)} vs ${formatMetric(cmp.version_b.cell_count)}), simpler structure. Choose this if resource efficiency matters.`}
                active={cmp.recommended === 'a'}
                icon="leaner"
              />
              <VerdictCard
                title={`${cmp.version_b.filename} — more capable`}
                description="Handles the larger design profile. Higher resource use can be expected when the design is doing more work."
                active={cmp.recommended === 'b'}
                icon="capable"
              />
              {!recommended && (
                <p className="text-sm text-black/55">No clear recommendation from the available metrics.</p>
              )}
            </div>
          </section>

          {cmp.ai_tradeoff && (
            <section className="surface-card panel">
              <h2 className="panel-title">AI Tradeoff Analysis</h2>
              <p className="text-sm leading-relaxed text-black/60">{cmp.ai_tradeoff}</p>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
