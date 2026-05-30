import { motion } from 'framer-motion'
import type { Stage, StageStatus } from '../types'

const STAGE_LABELS: Record<string, string> = {
  verilog_parse: 'Verilog Parse',
  ai_plan: 'AI Plan',
  lint: 'Lint Check',
  simulation: 'Simulation',
  synthesis: 'Synthesis',
  dep_analysis: 'Dependency Analysis',
  ai_report: 'AI Report',
}

function dotClass(status: StageStatus) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'error') return 'bg-red-500'
  if (status === 'running') return 'bg-blue-500'
  return 'bg-gray-400'
}

function StatusDot({ status }: { status: StageStatus }) {
  if (status === 'running') {
    return (
      <motion.span
        className={`status-dot pipeline-status-dot ${dotClass(status)}`}
        animate={{ opacity: [1, 0.35, 1], scale: [1, 1.45, 1] }}
        transition={{ duration: 1.15, repeat: Infinity, ease: 'easeInOut' }}
      />
    )
  }
  return <span className={`status-dot pipeline-status-dot ${dotClass(status)}`} />
}

interface WorkflowPipelineProps {
  stages?: Stage[]
}

export default function WorkflowPipeline({ stages = [] }: WorkflowPipelineProps) {
  if (!stages.length) {
    return <p className="text-sm text-black/45">Waiting for pipeline status.</p>
  }

  return (
    <div className="pipeline-list">
      {stages.map((stage, index) => (
        <motion.div
          key={stage.name}
          className={`pipeline-row ${stage.status}`}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: index * 0.045, duration: 0.28, ease: 'easeOut' }}
        >
          <span className="pipeline-node">
            <StatusDot status={stage.status} />
          </span>
          <span className="flex-1 text-sm text-[var(--heading-color)]">
            {STAGE_LABELS[stage.name] ?? stage.name}
          </span>
          {stage.duration_ms != null && (
            <span className="text-xs text-black/40">{stage.duration_ms}ms</span>
          )}
          <span className="tag">{stage.status}</span>
        </motion.div>
      ))}
    </div>
  )
}
