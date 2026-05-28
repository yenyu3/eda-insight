interface MetricCardProps {
  label: string
  value?: number | string | null
  unit?: string
  delta?: number | null
  better?: boolean
}

export default function MetricCard({ label, value, unit = '', delta, better }: MetricCardProps) {
  const hasChange = delta != null

  return (
    <div className="metric-card">
      <p className="metric-label">{label}</p>
      <p className="metric-value">
        {value ?? <span className="text-sm text-black/35">N/A</span>}
        {value != null && unit && (
          <span className="ml-1 text-xs font-normal text-black/45">{unit}</span>
        )}
      </p>
      {hasChange && (
        <p className={`mt-2 text-xs ${better ? 'text-emerald-700' : 'text-red-600'}`}>
          {(delta ?? 0) > 0 ? '+' : ''}{delta} {better ? 'better' : 'worse'}
        </p>
      )}
    </div>
  )
}
