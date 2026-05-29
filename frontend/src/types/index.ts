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
  line: number | null
}

export interface ParserResult {
  modules: Module[]
  lint_issues: LintIssue[]
}

export interface WorkflowPlan {
  steps: Array<'lint' | 'simulate' | 'synthesize' | 'dependency'>
  reason: string
  source: 'fixed' | 'ai' | 'fallback'
}

export interface WaveformTimeline {
  [signal: string]: { times: number[]; values: (number | string | null)[] }
}

export interface WaveformData {
  signals: string[]
  timeline: WaveformTimeline
  stats?: {
    sim_duration_ns: number
    clock_period_ns: number | null
    switching_activity: Record<string, number>
  }
  error?: string
  warning?: string
}

export interface SynthesisResult {
  cell_count: number | null
  wire_count: number | null
  flip_flop_count: number | null
  critical_path_ns: number | null
  slack_ns: number | null
  area_estimate?: string | null
  error?: string
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

export interface BottleneckAnalysis {
  bottlenecks: string[]
  impact: string
  suggestions: string
}

export interface AnalysisResult {
  run_id: string
  filename: string
  parser_result: ParserResult
  workflow_plan: WorkflowPlan | null
  waveform: WaveformData | null
  synthesis: SynthesisResult | null
  dependency_graph: DependencyGraphData | null
  ai_summary: string | null
  risk_scores: RiskScores | null
  bottleneck_analysis: BottleneckAnalysis | null
  lint_issues: LintIssue[]
}

export interface RunRecord {
  run_id: string
  filename: string
  status: StageStatus
  created_at: string
  ppa_cell_count: number | null
  ppa_critical_path_ns?: number | null
  ppa_slack_ns?: number | null
  cell_count?: number | null
  warning_count?: number
  sim_passed?: boolean | null
}

export interface HistoryData {
  runs: RunRecord[]
}

export interface CompareVersion extends RunRecord {
  cell_count: number | null
  wire_count: number | null
  flip_flop_count: number | null
  critical_path_ns: number | null
  slack_ns: number | null
  synthesis: SynthesisResult | null
}

export interface DiffEntry {
  delta: number | null
  pct?: number | null
  better: boolean | null
}

export interface CompareResult {
  version_a: CompareVersion
  version_b: CompareVersion
  diff: Record<string, DiffEntry | null>
  complexity_scores?: {
    a: number
    b: number
  }
  recommended?: 'a' | 'b' | null
  ai_tradeoff?: string
  error?: string
}

export interface StageLog {
  stage: string
  status: string
  log_output: string | null
  duration_ms: number | null
}
