import type { RiskScores } from '../types'

function RiskBar({ label, score }: { label: string; score: number | undefined }) {
  const pct = score != null ? (score / 10) * 100 : 0
  const color =
    score == null ? 'bg-gray-300'
    : score >= 7 ? 'bg-red-500'
    : score >= 4 ? 'bg-amber-400'
    : 'bg-emerald-500'

  return (
    <div className="mb-4">
      <div className="mb-2 flex justify-between text-xs text-black/55">
        <span className="font-medium">{label}</span>
        <span>{score != null ? score.toFixed(1) : 'N/A'}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-black/10">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
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
      <RiskBar label="Timing Risk" score={riskScores.timing_risk ?? riskScores.timing} />
      <RiskBar label="Area Risk" score={riskScores.area_risk ?? riskScores.area} />
      <RiskBar label="Function Risk" score={riskScores.function_risk ?? riskScores.function} />
      {riskScores.summary && (
        <p className="mt-3 text-sm leading-relaxed text-black/60">{riskScores.summary}</p>
      )}
    </div>
  )
}
