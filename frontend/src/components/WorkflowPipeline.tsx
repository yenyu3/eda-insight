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
        className={`status-dot ${dotClass(status)}`}
        animate={{ opacity: [1, 0.25, 1] }}
        transition={{ duration: 1.2, repeat: Infinity }}
      />
    )
  }
  return <span className={`status-dot ${dotClass(status)}`} />
}

interface WorkflowPipelineProps {
  stages?: Stage[]
}

export default function WorkflowPipeline({ stages = [] }: WorkflowPipelineProps) {
  if (!stages.length) {
    return <p className="text-sm text-black/45">Waiting for pipeline status.</p>
  }

  return (
    <div>
      {stages.map((stage) => (
        <div key={stage.name} className="pipeline-row">
          <StatusDot status={stage.status} />
          <span className="flex-1 text-sm text-[var(--heading-color)]">
            {STAGE_LABELS[stage.name] ?? stage.name}
          </span>
          {stage.duration_ms != null && (
            <span className="text-xs text-black/40">{stage.duration_ms}ms</span>
          )}
          <span className="tag">{stage.status}</span>
        </div>
      ))}
    </div>
  )
}
