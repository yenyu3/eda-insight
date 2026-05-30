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
import LogViewer from '../components/LogViewer'
import LogicFlowchart from '../components/LogicFlowchart'
import AIFormattedText from '../components/AIFormattedText'
import type { AnalysisResult, StageLog, StageStatus } from '../types'

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
  const [shareCopied, setShareCopied] = useState(false)

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
    queryFn: () => fetch(`/api/result/${runId}`).then((r) => { if (!r.ok) throw new Error(`result fetch failed: ${r.status}`); return r.json() as Promise<AnalysisResult> }),
    enabled: !!runId && isDone,
  })

  const { data: logsData, error: logsError, isLoading: logsLoading } = useQuery<{ logs: StageLog[] }>({
    queryKey: ['logs', runId],
    queryFn: () => fetch(`/api/logs/${runId}`).then((r) => {
      if (!r.ok) throw new Error(`logs fetch failed: ${r.status}`)
      return r.json() as Promise<{ logs: StageLog[] }>
    }),
    enabled: !!runId,
    refetchInterval: isDone ? false : 2000,
  })

  const synth: Partial<AnalysisResult['synthesis']> = result?.synthesis ?? {}
  const stages = status?.stages ?? []
  const overallStatus = status?.overall as StageStatus | undefined
  const warnings = result?.lint_issues?.length ?? 0
  const hasError = status?.overall === 'error'
  const doneStages = stages.filter((stage) => stage.status === 'done').length
  const progressPct = stages.length ? Math.round((doneStages / stages.length) * 100) : 0
  async function shareRun() {
    if (!runId) return
    await navigator.clipboard?.writeText(window.location.href)
    setShareCopied(true)
    window.setTimeout(() => setShareCopied(false), 1600)
  }

  if (statusError) {
    return (
      <div className="eda-container eda-narrow">
        <div className="surface-card panel">
          <span className="section-kicker">Run Analysis</span>
          <h1 className="page-title">Analysis run not found.</h1>
          <p className="page-subtitle">
            This run may have been removed or the backend database may have been reset.
          </p>
          <Link to="/" className="btn-primary mt-5 inline-flex">
            Back to upload
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
            <button type="button" className="analysis-share-button" onClick={() => void shareRun()}>
              {shareCopied ? 'Link copied' : 'Share'}
            </button>
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

      <div className="analysis-layout">
        <aside className="analysis-sidebar" aria-label="Pipeline progress">
          <div className={`surface-card panel pipeline-card ${isDone ? 'settled' : 'running'}`}>
            <div className="pipeline-card-head">
              <div>
                <h2 className="panel-title mb-0">Pipeline</h2>
                <p className="pipeline-subtitle">EDA workflow progress</p>
              </div>
              <span className="pipeline-percent">{progressPct}%</span>
            </div>
            <div className="pipeline-progress" aria-label={`${progressPct}% complete`}>
              <div className="pipeline-progress-fill" style={{ width: `${progressPct}%` }} />
            </div>
            <div className="pipeline-meta">
              <span>{doneStages} / {stages.length || 0} complete</span>
              <span>{status?.overall ?? 'pending'}</span>
            </div>
            <WorkflowPipeline stages={stages} />
          </div>
        </aside>

        <div className="analysis-content">
          <section className="surface-card panel">
            <h2 className="panel-title">Run Summary</h2>
            <div className="grid-metrics">
              <MetricCard label="Simulation" value={hasError ? 'Check logs' : isDone ? 'Passed' : 'Running'} />
              <MetricCard label="Warnings" value={warnings} />
              <MetricCard label="Errors" value={hasError ? 1 : 0} />
            </div>
          </section>

          <section className="surface-card panel">
            <h2 className="panel-title">Live Log</h2>
            <LogViewer
              stages={logsData?.logs ?? []}
              loading={logsLoading}
              error={logsError instanceof Error ? logsError.message : null}
            />
          </section>

          {view === 'ai' && (
            <section className="surface-card panel">
              <h2 className="panel-title">AI Log Interpretation</h2>
              <AIInsightPanel runId={runId} enabled={true} />
            </section>
          )}

          {view === 'tech' && (
            <>
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

              {isDone && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Logic Flowchart</h2>
                  {result?.flowchart
                    ? <LogicFlowchart data={result.flowchart} />
                    : <p className="text-sm text-black/45">No flowchart data available for this design.</p>
                  }
                </section>
              )}

              {result?.waveform?.signals?.length ? (
                <section className="surface-card panel">
                  <h2 className="panel-title">Waveform</h2>
                  <WaveformChart waveform={result.waveform} />
                </section>
              ) : isDone && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Waveform</h2>
                  <p className="text-sm text-black/45">No waveform data was produced for this run.</p>
                </section>
              )}

              {(result?.dependency_graph?.nodes?.length ?? 0) > 0 ? (
                <section className="surface-card panel">
                  <h2 className="panel-title">Dependency Graph</h2>
                  <DependencyGraph data={result?.dependency_graph} />
                </section>
              ) : isDone && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Dependency Graph</h2>
                  <p className="text-sm text-black/45">No module dependency graph is available.</p>
                </section>
              )}
            </>
          )}

          {view === 'ai' && (
            <>
              {result?.risk_scores && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Risk Scores</h2>
                  <RiskPanel riskScores={result.risk_scores} />
                </section>
              )}

              {result?.bottleneck_analysis && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Bottleneck Analysis</h2>
                  <div className="ai-box ai-box-plain min-h-0 space-y-4">
                    <div className="ai-section">
                      <h3>Nodes</h3>
                      <p>
                        {result.bottleneck_analysis.bottlenecks.length
                          ? result.bottleneck_analysis.bottlenecks.join(', ')
                          : 'None'}
                      </p>
                    </div>
                    <div className="ai-section">
                      <h3>Impact</h3>
                      <AIFormattedText text={result.bottleneck_analysis.impact || 'No impact details available.'} />
                    </div>
                    <div className="ai-section">
                      <h3>Suggestions</h3>
                      <AIFormattedText text={result.bottleneck_analysis.suggestions || 'No suggestions available.'} />
                    </div>
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
