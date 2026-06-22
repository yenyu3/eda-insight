import { useSSEStream } from '../hooks/useSSEStream'
import AIFormattedText from './AIFormattedText'
import LoadingState from './LoadingState'

interface AIInsightPanelProps {
  runId: string | undefined
  enabled?: boolean
}

export default function AIInsightPanel({ runId, enabled = true }: AIInsightPanelProps) {
  const { text, done, error } = useSSEStream(runId, enabled)

  if (!enabled) {
    return (
      <LoadingState
        compact
        title="Waiting for analysis results"
        description="AI review will start after the EDA pipeline has enough evidence."
      />
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        AI insight failed: {error}
      </div>
    )
  }

  return (
    <div className="ai-box ai-box-plain">
      {!text && !done && (
        <LoadingState
          compact
          title="Generating AI review"
          description="The model is reading logs and metrics. This can take a moment."
        />
      )}
      <AIFormattedText text={text} />
    </div>
  )
}
