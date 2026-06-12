interface LoadingStateProps {
  title: string
  description?: string
  compact?: boolean
  className?: string
}

export default function LoadingState({
  title,
  description,
  compact = false,
  className = '',
}: LoadingStateProps) {
  return (
    <div
      className={`loading-state ${compact ? 'loading-state--compact' : ''} ${className}`.trim()}
      role="status"
      aria-live="polite"
    >
      <span className="loading-state-spinner" aria-hidden="true" />
      <div className="loading-state-copy">
        <p className="loading-state-title">{title}</p>
        {description && <p className="loading-state-description">{description}</p>}
      </div>
    </div>
  )
}
