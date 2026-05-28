export type StageStatus = 'pending' | 'running' | 'done' | 'error'

export interface Stage {
  name: string
  status: StageStatus
  duration_ms: number | null
}

export interface RunStatus {
  run_id: string
  overall: StageStatus
  stages: Stage[]
}

export interface Port {
  name: string
  direction: 'input' | 'output' | 'inout'
  width: number
}

export interface Module {
  name: string
  ports: Port[]
  signals: string[]
  logic_type: 'sequential' | 'combinational' | 'mixed'
  instantiations: string[]
}

export interface LintIssue {
  type: string
  signal: string
  line: number
}

export interface ParserResult {
  modules: Module[]
  lint_issues: LintIssue[]
}

export interface WaveformTimeline {
  [signal: string]: { times: number[]; values: (number | string)[] }
}

export interface WaveformData {
  signals: string[]
  timeline: WaveformTimeline
  stats?: {
    sim_duration_ns: number
    clock_period_ns: number
    switching_activity: Record<string, number>
  }
}

export interface SynthesisResult {
  cell_count: number | null
  wire_count: number | null
  flip_flop_count: number | null
  critical_path_ns: number | null
  slack_ns: number | null
  area_estimate: string | null
}

export interface GraphNode {
  id: string
  in_degree: number
}

export interface GraphLink {
  source: string
  target: string
}

export interface DependencyGraphData {
  nodes: GraphNode[]
  links: GraphLink[]
  critical_path?: string[]
  topological_order?: string[]
}

export interface RiskScores {
  timing_risk?: number
  timing?: number
  area_risk?: number
  area?: number
  function_risk?: number
  function?: number
  summary?: string
}

export interface AnalysisResult {
  run_id: string
  filename: string
  parser_result: ParserResult
  waveform: WaveformData
  synthesis: SynthesisResult
  dependency_graph: DependencyGraphData
  ai_summary: string
  risk_scores: RiskScores
  lint_issues: LintIssue[]
}

export interface RunRecord {
  run_id: string
  filename: string
  status: StageStatus
  created_at: string
  ppa_cell_count: number | null
}

export interface HistoryData {
  runs: RunRecord[]
}

export interface CompareVersion {
  filename: string
  cell_count: number | null
  critical_path_ns: number | null
  slack_ns: number | null
}

export interface DiffEntry {
  delta: number | null
  pct?: number | null
  better: boolean
}

export interface CompareResult {
  version_a: CompareVersion
  version_b: CompareVersion
  diff: Record<string, DiffEntry>
  ai_tradeoff?: string
  error?: string
}

export interface StageLog {
  stage: string
  status: string
  log_output: string | null
  duration_ms: number | null
}
