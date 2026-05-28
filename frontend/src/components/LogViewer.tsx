import type { StageLog } from '../types'

function colorLine(line: string): string {
  if (/\[✓\]|Passed|passed|done/i.test(line)) return 'text-emerald-600'
  if (/warning/i.test(line)) return 'text-amber-500'
  if (/error/i.test(line)) return 'text-red-500'
  return 'text-gray-500'
}

interface LogViewerProps {
  stages?: StageLog[]
}

export default function LogViewer({ stages = [] }: LogViewerProps) {
  const lines = stages.flatMap((s) =>
    s.log_output
      ? s.log_output.split('\n').filter(Boolean).map((l) => ({ stage: s.stage, line: l }))
      : []
  )

  if (!lines.length) {
    return <p className="text-xs text-gray-400 p-3">No logs yet.</p>
  }

  return (
    <div className="h-48 overflow-y-auto bg-gray-900 rounded-lg p-3 font-mono text-xs">
      {lines.map((entry, i) => (
        <div key={i} className={colorLine(entry.line)}>
          <span className="text-gray-600 mr-2">[{entry.stage}]</span>
          {entry.line}
        </div>
      ))}
    </div>
  )
}
