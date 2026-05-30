import type { RiskScores } from '../types'

function formatScore(score: number | undefined) {
  if (score == null) return 'N/A'
  return Number.isInteger(score) ? score.toFixed(0) : score.toFixed(1)
}

function RiskGauge({ label, score }: { label: string; score: number | undefined }) {
  const pct = score != null ? Math.max(0, Math.min(score, 10)) * 10 : 0
  const tone =
    score == null ? 'neutral'
    : score >= 7 ? 'high'
    : score >= 4 ? 'medium'
    : 'low'

  return (
    <div className={`risk-gauge-card ${tone}`}>
      <div
        className="risk-gauge"
        style={{ '--risk-progress': `${pct}%` } as React.CSSProperties}
        aria-label={`${label}: ${formatScore(score)} out of 10`}
      >
        <div className="risk-gauge-inner">
          <span>{formatScore(score)}</span>
        </div>
      </div>
      <p className="risk-gauge-label">{label}</p>
    </div>
  )
}

interface RiskPanelProps {
  riskScores?: RiskScores | null
}

export default function RiskPanel({ riskScores }: RiskPanelProps) {
  if (!riskScores) {
    return <p className="text-sm text-black/45">No risk scores available.</p>
  }

  return (
    <div>
      <div className="risk-gauge-grid">
        <RiskGauge label="Timing Risk" score={riskScores.timing_risk ?? riskScores.timing} />
        <RiskGauge label="Area Risk" score={riskScores.area_risk ?? riskScores.area} />
        <RiskGauge label="Function Risk" score={riskScores.function_risk ?? riskScores.function} />
      </div>
      {riskScores.summary && (
        <p className="risk-summary">{riskScores.summary}</p>
      )}
    </div>
  )
}
