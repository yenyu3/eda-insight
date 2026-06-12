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
import LoadingState from '../components/LoadingState'
import type { AnalysisResult, Stage, StageLog, StageStatus } from '../types'

type ViewMode = 'tech' | 'decision'
type VerdictType = 'READY' | 'REVIEW NEEDED' | 'BLOCKED' | 'INSUFFICIENT DATA'

interface Verdict {
  verdict: VerdictType
  headline: string
  reasons: string[]
  confidence: 'high' | 'medium' | 'low'
}

// ── Computed decision helpers ──────────────────────────────────────

function computeReadinessScore(
  result: AnalysisResult | undefined,
  isDone: boolean,
  hasError: boolean,
  stages: Stage[]
): number {
  if (!isDone) return 0

  let score = 0

  // Pipeline completion (25 pts)
  score += hasError ? 5 : 25

  // Simulation quality (20 pts)
  const simStage = stages.find((s) => s.name === 'simulation')
  const hasWaveform = (result?.waveform?.signals?.length ?? 0) > 0
  if (simStage?.status === 'done' && hasWaveform) score += 20
  else if (simStage?.status === 'done') score += 10

  // Synthesis quality (20 pts)
  const synthStage = stages.find((s) => s.name === 'synthesis')
  const hasSynthData = (result?.synthesis?.cell_count ?? null) != null
  if (synthStage?.status === 'done' && hasSynthData) score += 20
  else if (synthStage?.status === 'done') score += 10

  // Lint cleanliness (15 pts)
  const lintCount = result?.lint_issues?.length ?? 0
  if (lintCount === 0) score += 15
  else if (lintCount <= 2) score += 10
  else if (lintCount <= 5) score += 5

  // Risk quality (20 pts)
  const risks = result?.risk_scores
  if (risks) {
    const maxRisk = Math.max(
      risks.timing_risk ?? risks.timing ?? 0,
      risks.area_risk ?? risks.area ?? 0,
      risks.function_risk ?? risks.function ?? 0
    )
    if (maxRisk < 3) score += 20
    else if (maxRisk < 5) score += 14
    else if (maxRisk < 7) score += 8
    else score += 2
  } else {
    score += 10 // partial credit when risk analysis not yet run
  }

  return Math.min(100, score)
}

function computeVerdict(
  result: AnalysisResult | undefined,
  isDone: boolean,
  hasError: boolean,
  stages: Stage[]
): Verdict {
  if (!isDone) {
    return {
      verdict: 'INSUFFICIENT DATA',
      headline: 'Pipeline has not completed yet.',
      reasons: ['Analysis is still running or pending.'],
      confidence: 'low',
    }
  }

  if (hasError) {
    const failedStages = stages
      .filter((s) => s.status === 'error' && s.name !== 'ai_report')
      .map((s) => s.name.replace(/_/g, ' '))
    return {
      verdict: 'BLOCKED',
      headline: 'One or more EDA stages failed. Review is required before continuing.',
      reasons: failedStages.length
        ? [`Stage failure: ${failedStages.join(', ')}`]
        : ['An EDA stage encountered an error.'],
      confidence: 'high',
    }
  }

  const reasons: string[] = []
  const lintCount = result?.lint_issues?.length ?? 0
  const hasWaveform = (result?.waveform?.signals?.length ?? 0) > 0
  const simStage = stages.find((s) => s.name === 'simulation')
  const simRan = simStage?.status === 'done'
  const risks = result?.risk_scores
  const maxRisk = risks
    ? Math.max(
        risks.timing_risk ?? risks.timing ?? 0,
        risks.area_risk ?? risks.area ?? 0,
        risks.function_risk ?? risks.function ?? 0
      )
    : 0

  if (!simRan) reasons.push('Simulation stage was not executed.')
  if (simRan && !hasWaveform) reasons.push('No waveform evidence was generated.')
  if (lintCount > 0) reasons.push(`${lintCount} lint issue${lintCount !== 1 ? 's' : ''} detected.`)
  if (maxRisk >= 7) reasons.push('High-severity risk detected.')
  else if (maxRisk >= 4) reasons.push('Medium-level risk detected.')

  if (reasons.length > 0) {
    return {
      verdict: 'REVIEW NEEDED',
      headline: 'Design ran successfully but has items requiring review.',
      reasons,
      confidence: maxRisk >= 7 ? 'high' : 'medium',
    }
  }

  return {
    verdict: 'READY',
    headline: 'Design passed all checks. Ready for the next stage.',
    reasons: [
      'Pipeline completed without errors',
      'No lint issues found',
      'Simulation passed with waveform captured',
      'Risk levels are low',
    ],
    confidence: 'high',
  }
}

function getStageNarrative(stage: Stage, result: AnalysisResult | undefined): string {
  if (stage.status === 'pending') return 'Pending.'
  if (stage.status === 'running') return 'Running...'

  switch (stage.name) {
    case 'verilog_parse': {
      if (stage.status === 'error') return 'Parse failed — check Verilog syntax.'
      const count = result?.parser_result?.modules?.length ?? 0
      return `Found ${count} module${count !== 1 ? 's' : ''}.`
    }
    case 'lint': {
      if (stage.status === 'error') return 'Lint check encountered an error.'
      const issues = result?.lint_issues?.length ?? 0
      return issues === 0 ? 'No lint issues found.' : `Found ${issues} lint issue${issues !== 1 ? 's' : ''} — review recommended.`
    }
    case 'simulation': {
      if (stage.status === 'error') return 'Simulation failed — check testbench and Verilog syntax.'
      const hasWaveform = (result?.waveform?.signals?.length ?? 0) > 0
      return hasWaveform
        ? 'Simulation passed with waveform data captured.'
        : 'Simulation ran, but no waveform was generated — testbench may lack $dumpfile.'
    }
    case 'synthesis': {
      if (stage.status === 'error') return 'Synthesis failed — check for unsynthesizable constructs.'
      const cells = result?.synthesis?.cell_count ?? null
      const ffs = result?.synthesis?.flip_flop_count ?? null
      if (cells != null) {
        return `Synthesized to ${cells} cells${ffs != null ? ` and ${ffs} flip-flop${ffs !== 1 ? 's' : ''}` : ''}.`
      }
      return 'Synthesis completed.'
    }
    case 'dep_analysis': {
      if (stage.status === 'error') return 'Dependency analysis encountered an error.'
      const nodes = result?.dependency_graph?.nodes?.length ?? 0
      return nodes > 1
        ? `Dependency graph built — ${nodes} modules identified.`
        : 'Single-module design, no multi-module hierarchy.'
    }
    case 'ai_report': {
      if (stage.status === 'error') return 'AI report generation failed — log data may be incomplete.'
      return 'AI analysis complete.'
    }
    default:
      return stage.status === 'done' ? 'Completed.' : stage.status
  }
}

function computeNextActions(
  result: AnalysisResult | undefined,
  verdict: VerdictType,
  stages: Stage[]
): string[] {
  const actions: string[] = []
  const hasWaveform = (result?.waveform?.signals?.length ?? 0) > 0
  const simStage = stages.find((s) => s.name === 'simulation')
  const lintCount = result?.lint_issues?.length ?? 0

  if (verdict === 'BLOCKED') {
    actions.push('Resolve EDA stage errors before continuing — check the Live Log in Technical View.')
  }
  if (simStage?.status === 'done' && !hasWaveform) {
    actions.push('Add $dumpfile and $dumpvars to the testbench to capture waveform evidence.')
  }
  if (lintCount > 0) {
    actions.push(`Fix ${lintCount} lint issue${lintCount !== 1 ? 's' : ''} to ensure design correctness before tapeout.`)
  }
  if (
    (result?.synthesis?.critical_path_ns ?? null) == null &&
    stages.find((s) => s.name === 'synthesis')?.status === 'done'
  ) {
    actions.push('Run a timing-aware flow (e.g., OpenROAD) for signoff-level timing analysis.')
  }
  if (verdict === 'READY') {
    actions.push('Compare this run against a previous version to track design evolution.')
  }

  return actions.slice(0, 3)
}

function computeLimitations(result: AnalysisResult | undefined, isDone: boolean): string[] {
  if (!isDone) return []
  const lims: string[] = []
  if ((result?.synthesis?.critical_path_ns ?? null) == null) {
    lims.push(
      'Timing data (critical path, slack) is unavailable — the Yosys-only flow does not provide full STA timing by default. Use OpenROAD or a commercial tool for signoff-level timing.'
    )
  }
  if (!(result?.waveform?.signals?.length)) {
    lims.push(
      'No waveform was captured — functional coverage cannot be confirmed without simulation output. Add $dumpfile/$dumpvars to the testbench.'
    )
  }
  return lims
}

// ── Style helpers ──────────────────────────────────────────────────

function statusClass(status: StageStatus | undefined) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'error') return 'bg-red-500'
  if (status === 'running') return 'bg-blue-500'
  return 'bg-gray-400'
}

const verdictConfig: Record<VerdictType, { badge: string; dot: string; scoreColor: string }> = {
  READY:              { badge: 'verdict-badge--ready',   dot: 'bg-emerald-500', scoreColor: '#10b981' },
  'REVIEW NEEDED':    { badge: 'verdict-badge--review',  dot: 'bg-amber-400',   scoreColor: '#f59e0b' },
  BLOCKED:            { badge: 'verdict-badge--blocked', dot: 'bg-red-500',     scoreColor: '#ef4444' },
  'INSUFFICIENT DATA':{ badge: 'verdict-badge--insuff',  dot: 'bg-gray-400',    scoreColor: '#9ca3af' },
}

function LinkIcon() {
  return (
    <svg className="analysis-action-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10.6 13.4a4.8 4.8 0 0 0 6.8 0l2-2a4.8 4.8 0 0 0-6.8-6.8l-1.1 1.1" />
      <path d="M13.4 10.6a4.8 4.8 0 0 0-6.8 0l-2 2a4.8 4.8 0 0 0 6.8 6.8l1.1-1.1" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="analysis-action-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

// ── Component ─────────────────────────────────────────────────────

export default function Analysis() {
  const { runId } = useParams<{ runId: string }>()
  const [view, setView] = useState<ViewMode>('tech')
  const [shareCopied, setShareCopied] = useState(false)

  const { data: status, isLoading: statusLoading, isError: statusError } = useRunStatus(runId)
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

  const { data: result, isLoading: resultLoading, isError: resultError, error: resultErrorData } = useQuery<AnalysisResult>({
    queryKey: ['result', runId],
    queryFn: () =>
      fetch(`/api/result/${runId}`).then((r) => {
        if (!r.ok) throw new Error(`result fetch failed: ${r.status}`)
        return r.json() as Promise<AnalysisResult>
      }),
    enabled: !!runId && isDone,
  })

  const { data: logsData, error: logsError, isLoading: logsLoading } = useQuery<{ logs: StageLog[] }>({
    queryKey: ['logs', runId],
    queryFn: () =>
      fetch(`/api/logs/${runId}`).then((r) => {
        if (!r.ok) throw new Error(`logs fetch failed: ${r.status}`)
        return r.json() as Promise<{ logs: StageLog[] }>
      }),
    enabled: !!runId,
    refetchInterval: isDone ? false : 2000,
  })

  const synth: Partial<NonNullable<AnalysisResult['synthesis']>> = result?.synthesis ?? {}
  const stages = status?.stages ?? []
  const overallStatus = status?.overall as StageStatus | undefined
  const warnings = result?.lint_issues?.length ?? 0
  const hasError = status?.overall === 'error'
  const doneStages = stages.filter((s) => s.status === 'done').length
  const progressPct = stages.length ? Math.round((doneStages / stages.length) * 100) : 0

  // Decision Review computed values
  const readinessScore = computeReadinessScore(result, isDone, hasError, stages)
  const verdict = computeVerdict(result, isDone, hasError, stages)
  const verdictStyle = verdictConfig[verdict.verdict]
  const nextActions = computeNextActions(result, verdict.verdict, stages)
  const limitations = computeLimitations(result, isDone)
  // ai_plan is a meta-stage; exclude from the narrative list
  const narrativeStages = stages.filter((s) => s.name !== 'ai_plan')

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
          <div className="analysis-run-actions mt-5">
            <span className={`status-dot ${statusClass(overallStatus)}`} />
            <span className="tag analysis-status-tag">{statusLoading ? 'loading status' : status?.overall ?? 'pending'}</span>
            <button
              type="button"
              className={`analysis-share-button analysis-share-button--run ${shareCopied ? 'copied' : ''}`}
              onClick={() => void shareRun()}
            >
              {shareCopied ? <CheckIcon /> : <LinkIcon />}
              {shareCopied ? 'Link copied' : 'Share Run'}
            </button>
          </div>
        </div>

        <div className="segmented">
          {(['tech', 'decision'] as ViewMode[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className={view === v ? 'active' : ''}
            >
              {v === 'tech' ? 'Technical' : 'Decision Review'}
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
              <span>{statusLoading ? 'Loading stages...' : `${doneStages} / ${stages.length || 0} complete`}</span>
              <span>{status?.overall ?? 'pending'}</span>
            </div>
            {statusLoading ? (
              <LoadingState
                compact
                title="Loading pipeline status"
                description="Connecting to the backend run tracker."
              />
            ) : (
              <WorkflowPipeline stages={stages} />
            )}
          </div>
        </aside>

        <div className="analysis-content">

          {/* ── Technical View ── */}
          {view === 'tech' && (
            <>
              <section className="surface-card panel">
                <h2 className="panel-title">Run Summary</h2>
                <div className="grid-metrics">
                  <MetricCard
                    label="Simulation"
                    value={hasError ? 'Check logs' : isDone ? 'Passed' : 'Running'}
                  />
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

              <section className="surface-card panel">
                <h2 className="panel-title">Synthesis Metrics</h2>
                {resultLoading ? (
                  <LoadingState
                    compact
                    title="Loading final metrics"
                    description="The pipeline finished; synthesis artifacts are being fetched."
                  />
                ) : resultError ? (
                  <p className="text-sm text-red-600">
                    Failed to load result metrics: {resultErrorData instanceof Error ? resultErrorData.message : 'Unknown error'}
                  </p>
                ) : !isDone ? (
                  <LoadingState
                    compact
                    title="Waiting for synthesis results"
                    description="Metrics will appear here after synthesis and analysis complete."
                  />
                ) : (
                  <div className="grid-metrics">
                    <MetricCard label="Cell Count" value={synth.cell_count} />
                    <MetricCard label="Wire Count" value={synth.wire_count} />
                    <MetricCard label="Flip-Flops" value={synth.flip_flop_count} />
                    <MetricCard label="Critical Path" value={synth.critical_path_ns} unit="ns" />
                    <MetricCard label="Slack" value={synth.slack_ns} unit="ns" />
                    <MetricCard label="Area" value={synth.area_estimate} />
                  </div>
                )}
              </section>

              {isDone && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Logic Flowchart</h2>
                  {result?.flowchart ? (
                    <LogicFlowchart data={result.flowchart} />
                  ) : (
                    <p className="text-sm text-black/45">No flowchart data available for this design.</p>
                  )}
                </section>
              )}

              {result?.waveform?.signals?.length ? (
                <section className="surface-card panel">
                  <h2 className="panel-title">Waveform</h2>
                  <WaveformChart waveform={result.waveform} />
                </section>
              ) : isDone ? (
                <section className="surface-card panel">
                  <h2 className="panel-title">Waveform</h2>
                  <p className="text-sm text-black/45">No waveform data was produced for this run.</p>
                </section>
              ) : null}

              {(result?.dependency_graph?.nodes?.length ?? 0) > 0 ? (
                <section className="surface-card panel">
                  <h2 className="panel-title">Dependency Graph</h2>
                  <DependencyGraph data={result?.dependency_graph} />
                </section>
              ) : isDone ? (
                <section className="surface-card panel">
                  <h2 className="panel-title">Dependency Graph</h2>
                  <p className="text-sm text-black/45">No module dependency graph is available.</p>
                </section>
              ) : null}
            </>
          )}

          {/* ── Decision Review ── */}
          {view === 'decision' && (
            <>
              {/* 1. Design Readiness Card */}
              <section className="surface-card panel">
                <h2 className="panel-title">Design Readiness</h2>
                <div className="readiness-card">
                  <div className="readiness-score-wrap">
                    <div
                      className="readiness-score-ring"
                      style={{
                        '--score-pct': `${readinessScore}%`,
                        '--score-color': verdictStyle.scoreColor,
                      } as React.CSSProperties}
                      aria-label={`Readiness score: ${readinessScore} out of 100`}
                    >
                      <div className="readiness-score-inner">
                        <span className="readiness-score-value">{isDone ? readinessScore : '—'}</span>
                        {isDone && <span className="readiness-score-unit">/100</span>}
                      </div>
                    </div>
                  </div>
                  <div className="readiness-copy">
                    <div className={`verdict-badge ${verdictStyle.badge}`}>
                      <span className={`status-dot ${verdictStyle.dot}`} />
                      {verdict.verdict}
                    </div>
                    <p className="readiness-headline">{verdict.headline}</p>
                    {verdict.reasons.length > 0 && (
                      <ul className="readiness-reasons">
                        {verdict.reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    )}
                    <p className="readiness-confidence">Confidence: {verdict.confidence}</p>
                  </div>
                </div>
              </section>

              {/* 2. Workflow Narrative */}
              {narrativeStages.length > 0 && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Workflow Narrative</h2>
                  <ul className="narrative-list">
                    {narrativeStages.map((stage) => (
                      <li key={stage.name} className="narrative-item">
                        <span className={`status-dot narrative-dot ${statusClass(stage.status as StageStatus)}`} />
                        <div className="narrative-body">
                          <span className="narrative-stage">{stage.name.replace(/_/g, ' ')}</span>
                          <span className="narrative-text">{getStageNarrative(stage, result)}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* 3. Risk Scores */}
              {!isDone && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Decision Evidence</h2>
                  <LoadingState
                    compact
                    title="Collecting decision evidence"
                    description="Readiness, risks, bottlenecks, and AI review will update after the run completes."
                  />
                </section>
              )}

              {resultLoading && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Final Results</h2>
                  <LoadingState
                    compact
                    title="Loading completed analysis"
                    description="Fetching risk scores, bottlenecks, and generated reports."
                  />
                </section>
              )}

              {result?.risk_scores && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Risk Scores</h2>
                  <RiskPanel riskScores={result.risk_scores} />
                </section>
              )}

              {/* 4. Evidence-based AI Review */}
              <section className="surface-card panel">
                <h2 className="panel-title">AI Review</h2>
                <AIInsightPanel runId={runId} enabled={isDone && !resultLoading} />
              </section>

              {/* 5. Bottleneck Analysis */}
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

              {/* 6. Recommended Next Actions */}
              {nextActions.length > 0 && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Recommended Next Actions</h2>
                  <ol className="actions-list">
                    {nextActions.map((action, i) => (
                      <li key={i} className="action-item">
                        <span className="action-num">{i + 1}</span>
                        <span className="action-text">{action}</span>
                      </li>
                    ))}
                  </ol>
                </section>
              )}

              {/* 7. Data Limitations */}
              {limitations.length > 0 && (
                <section className="surface-card panel">
                  <h2 className="panel-title">Data Limitations</h2>
                  <div className="limitations-box">
                    {limitations.map((lim, i) => (
                      <div key={i} className="limitation-item">
                        <span className="limitation-icon">!</span>
                        <p>{lim}</p>
                      </div>
                    ))}
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
