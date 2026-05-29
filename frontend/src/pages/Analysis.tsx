import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useRunStatus } from '../hooks/useRunStatus'
import WorkflowPipeline from '../components/WorkflowPipeline'
import AIInsightPanel from '../components/AIInsightPanel'
import MetricCard from '../components/MetricCard'
import RiskPanel from '../components/RiskPanel'
import WaveformChart from '../components/WaveformChart'
import DependencyGraph from '../components/DependencyGraph'
import type { AnalysisResult, StageStatus } from '../types'

type ViewMode = 'tech' | 'ai'

function statusClass(status: StageStatus | undefined) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'error') return 'bg-red-500'
  if (status === 'running') return 'bg-blue-500'
  return 'bg-gray-400'
}

export default function Analysis() {
  const { runId } = useParams<{ runId: string }>()
  const [view, setView] = useState<ViewMode>('tech')

  const { data: status, isError: statusError } = useRunStatus(runId)
  const isDone = status?.overall === 'done' || status?.overall === 'error'

  useEffect(() => {
    if (status?.run_id) {
      window.localStorage.setItem('eda-insight:last-run-id', status.run_id)
    }
  }, [status?.run_id])

  useEffect(() => {
    if (
      statusError &&
      runId &&
      window.localStorage.getItem('eda-insight:last-run-id') === runId
    ) {
      window.localStorage.removeItem('eda-insight:last-run-id')
    }
  }, [runId, statusError])

  const { data: result } = useQuery<AnalysisResult>({
    queryKey: ['result', runId],
    queryFn: () => fetch(`/api/result/${runId}`).then((r) => r.json() as Promise<AnalysisResult>),
    enabled: !!runId && isDone,
  })

  const synth: Partial<AnalysisResult['synthesis']> = result?.synthesis ?? {}
  const stages = status?.stages ?? []
  const overallStatus = status?.overall as StageStatus | undefined

  if (statusError) {
    return (
      <div className="eda-container eda-narrow">
        <div className="surface-card panel">
          <span className="section-kicker">Run Analysis</span>
          <h1 className="page-title">Analysis run not found.</h1>
          <p className="page-subtitle">
            This run may have been removed or the backend database may have been reset.
          </p>
          <Link to="/history" className="btn-primary mt-5 inline-flex">
            Open history
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="eda-container">
      <div className="toolbar">
        <div>
          <span className="section-kicker">Run Analysis</span>
          <h1 className="page-title">{result?.filename ?? 'Analyzing design...'}</h1>
          <p className="page-subtitle">
            Track each EDA stage, review synthesis metrics, inspect waveform output, and request
            AI-focused interpretation once the run completes.
          </p>
          <div className="mt-5 flex items-center gap-2">
            <span className={`status-dot ${statusClass(overallStatus)}`} />
            <span className="tag">{status?.overall ?? 'pending'}</span>
            {runId && <span className="tag font-mono">{runId.slice(0, 8)}</span>}
          </div>
        </div>

        <div className="segmented">
          {(['tech', 'ai'] as ViewMode[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={view === v ? 'active' : ''}
            >
              {v === 'tech' ? 'Technical' : 'AI Review'}
            </button>
          ))}
        </div>
      </div>

      <div className="surface-card panel mb-5">
        <h2 className="panel-title">Pipeline</h2>
        <WorkflowPipeline stages={stages} />
      </div>

      {view === 'tech' && (
        <div className="space-y-5">
          <section className="surface-card panel">
            <h2 className="panel-title">Synthesis Metrics</h2>
            <div className="grid-metrics">
              <MetricCard label="Cell Count" value={synth.cell_count} />
              <MetricCard label="Wire Count" value={synth.wire_count} />
              <MetricCard label="Flip-Flops" value={synth.flip_flop_count} />
              <MetricCard label="Critical Path" value={synth.critical_path_ns} unit="ns" />
              <MetricCard label="Slack" value={synth.slack_ns} unit="ns" />
              <MetricCard label="Area" value={synth.area_estimate} />
            </div>
          </section>

          {result?.waveform?.signals && (
            <section className="surface-card panel">
              <h2 className="panel-title">Waveform</h2>
              <WaveformChart waveform={result.waveform} />
            </section>
          )}

          {(result?.dependency_graph?.nodes?.length ?? 0) > 0 && (
            <section className="surface-card panel">
              <h2 className="panel-title">Dependency Graph</h2>
              <DependencyGraph data={result?.dependency_graph} />
            </section>
          )}
        </div>
      )}

      {view === 'ai' && (
        <div className="space-y-5">
          <section className="surface-card panel">
            <h2 className="panel-title">AI Insight</h2>
            <AIInsightPanel runId={runId} enabled={true} />
          </section>

          {result?.risk_scores && (
            <section className="surface-card panel">
              <h2 className="panel-title">Risk Scores</h2>
              <RiskPanel riskScores={result.risk_scores} />
            </section>
          )}
        </div>
      )}
    </div>
  )
}
