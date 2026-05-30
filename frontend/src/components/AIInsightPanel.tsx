import { motion } from 'framer-motion'
import { useSSEStream } from '../hooks/useSSEStream'
import AIFormattedText from './AIFormattedText'

interface AIInsightPanelProps {
  runId: string | undefined
  enabled?: boolean
}

export default function AIInsightPanel({ runId, enabled = true }: AIInsightPanelProps) {
  const { text, done, error } = useSSEStream(runId, enabled)

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
        AI insight failed: {error}
      </div>
    )
  }

  return (
    <div className="ai-box ai-box-plain">
      <AIFormattedText text={text} />
      {!done && text && (
        <motion.span
          className="ml-1 inline-block h-4 w-0.5 align-middle bg-[var(--accent-color)]"
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 0.8, repeat: Infinity }}
        />
      )}
    </div>
  )
}
