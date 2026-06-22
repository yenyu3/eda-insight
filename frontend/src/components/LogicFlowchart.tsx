import { useState, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react'
import dagre from '@dagrejs/dagre'
import '@xyflow/react/dist/style.css'
import type { FlowchartData, AlwaysBlock, FlowNode, FlowEdge } from '../types'

// ─── View mode ───────────────────────────────────────────────────────────────

type ViewMode = 'business' | 'semantic' | 'raw'

function pickLabel(node: FlowNode, mode: ViewMode): string {
  if (mode === 'business') return node.business_label ?? node.semantic_label ?? node.display_label ?? node.label
  if (mode === 'semantic') return node.semantic_label ?? node.display_label ?? node.label
  return node.label
}

function pickDetail(node: FlowNode, mode: ViewMode): string | undefined {
  if (mode === 'business') {
    return undefined
  }
  if (mode === 'semantic') {
    const main = node.semantic_label ?? node.display_label ?? node.label
    return main !== node.label ? node.label : undefined
  }
  const sem = node.semantic_label
  return sem && sem !== node.label ? sem : undefined
}

// ─── Node dimensions for dagre layout ───────────────────────────────────────

const NODE_WIDTH: Record<string, number> = { trigger: 160, decision: 88, process: 160 }
const NODE_HEIGHT: Record<string, number> = { trigger: 36, decision: 88, process: 44 }

// ─── Custom node components ──────────────────────────────────────────────────

function TriggerNode({ data }: { data: { label: string; detail?: string } }) {
  return (
    <div style={{
      background: '#378ADD',
      border: '1.5px solid #2563eb',
      borderRadius: 999,
      padding: '6px 18px',
      color: '#fff',
      fontFamily: 'var(--nav-font, Poppins, sans-serif)',
      fontWeight: 500,
      fontSize: '0.78rem',
      whiteSpace: 'nowrap',
      textAlign: 'center',
    }}>
      {data.label}
      {data.detail && (
        <span style={{ display: 'block', fontSize: '0.62rem', opacity: 0.75, fontFamily: 'var(--mono-font, monospace)', marginTop: 1 }}>
          {data.detail}
        </span>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: '#2563eb' }} />
    </div>
  )
}

function DiamondNode({ data }: { data: { label: string; detail?: string } }) {
  return (
    <>
      <Handle type="target" position={Position.Top} style={{ background: '#EF9F27' }} />
      <div style={{
        width: 88,
        height: 88,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transform: 'rotate(45deg)',
        background: 'rgba(239,159,39,0.12)',
        border: '1.5px solid #EF9F27',
        borderRadius: 6,
      }}>
        <span style={{
          transform: 'rotate(-45deg)',
          fontSize: '0.75rem',
          fontFamily: 'var(--nav-font, Poppins, sans-serif)',
          fontWeight: 600,
          color: '#0f1012',
          textAlign: 'center',
          maxWidth: 68,
          lineHeight: 1.3,
          display: 'block',
          wordBreak: 'break-word',
        }}>
          {data.label}
          {data.detail && (
            <span style={{ display: 'block', marginTop: 2, fontSize: '0.58rem', fontFamily: 'var(--mono-font, monospace)', opacity: 0.55, wordBreak: 'break-all' }}>
              {data.detail}
            </span>
          )}
        </span>
      </div>
      <Handle type="source" position={Position.Right} id="yes" style={{ background: '#1D9E75', top: '50%' }} />
      <Handle type="source" position={Position.Bottom} id="no" style={{ background: '#9ca3af', left: '50%' }} />
      <Handle type="source" position={Position.Left} id="branch" style={{ background: '#9ca3af', top: '50%' }} />
    </>
  )
}

function ProcessNode({ data }: { data: { label: string; detail?: string; kind?: string } }) {
  const isSummary = data.kind === 'summary'
  return (
    <div style={{
      background: isSummary ? 'rgba(0,0,0,0.035)' : 'rgba(29,158,117,0.10)',
      border: isSummary ? '1.5px dashed rgba(0,0,0,0.22)' : '1.5px solid rgba(29,158,117,0.4)',
      borderRadius: 8,
      padding: '8px 12px',
      fontFamily: 'var(--nav-font, Poppins, sans-serif)',
      fontSize: '0.82rem',
      color: '#0f1012',
      minWidth: 120,
      maxWidth: 164,
      textAlign: 'center',
      lineHeight: 1.5,
      whiteSpace: 'pre-line',
    }}>
      <Handle type="target" position={Position.Top} style={{ background: 'rgba(29,158,117,0.5)' }} />
      {data.label}
      {data.detail && (
        <span style={{ display: 'block', marginTop: 4, fontSize: '0.68rem', color: 'rgba(0,0,0,0.42)', fontFamily: 'var(--mono-font, monospace)', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {data.detail}
        </span>
      )}
    </div>
  )
}

const nodeTypes: NodeTypes = {
  trigger: TriggerNode,
  decision: DiamondNode,
  process: ProcessNode,
}

// ─── dagre layout ────────────────────────────────────────────────────────────

function applyDagreLayout(
  rawNodes: FlowNode[],
  rawEdges: FlowEdge[],
  mode: ViewMode,
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', ranksep: 56, nodesep: 36 })

  rawNodes.forEach((n) => {
    const w = NODE_WIDTH[n.type] ?? 140
    const h = n.type === 'process'
      ? Math.max(NODE_HEIGHT.process, pickLabel(n, mode).split('\n').length * 22 + 16)
      : (NODE_HEIGHT[n.type] ?? 48)
    g.setNode(n.id, { width: w, height: h })
  })
  rawEdges.forEach((e) => g.setEdge(e.source, e.target))

  dagre.layout(g)

  const nodes: Node[] = rawNodes.map((n) => {
    const pos = g.node(n.id)
    const w = NODE_WIDTH[n.type] ?? 140
    const h = n.type === 'process'
      ? Math.max(NODE_HEIGHT.process, pickLabel(n, mode).split('\n').length * 22 + 16)
      : (NODE_HEIGHT[n.type] ?? 48)
    return {
      id: n.id,
      type: n.type,
      position: { x: pos.x - w / 2, y: pos.y - h / 2 },
      data: {
        label: pickLabel(n, mode),
        detail: pickDetail(n, mode),
        kind: n.kind,
      },
    }
  })

  const edges: Edge[] = rawEdges.map((e) => {
    const isYes = e.label === 'YES'
    const isNo = e.label === 'NO'
    const isSummary = e.kind === 'summary'
    const isSequence = e.kind === 'sequence'
    return {
      id: e.id,
      type: 'smoothstep',
      source: e.source,
      target: e.target,
      sourceHandle: isYes ? 'yes' : isNo ? 'no' : e.label ? 'branch' : undefined,
      label: e.label,
      style: {
        stroke: isYes ? '#1D9E75' : isNo ? '#9ca3af' : isSummary ? '#8b8b8b' : '#d1d5db',
        strokeWidth: isSequence || isSummary ? 1.25 : 1.5,
        strokeDasharray: isSequence || isSummary ? '5 4' : undefined,
      },
      labelStyle: {
        fontFamily: 'var(--nav-font, Poppins, sans-serif)',
        fontSize: '0.68rem',
        fontWeight: 600,
        letterSpacing: '0.5px',
        fill: isYes ? '#1D9E75' : '#9ca3af',
      },
      labelBgStyle: {
        fill: isYes ? 'rgba(29,158,117,0.08)' : 'rgba(0,0,0,0.04)',
      },
    }
  })

  return { nodes, edges }
}

// ─── Single block flowchart ───────────────────────────────────────────────────

function filterBlock(block: AlwaysBlock, query: string): AlwaysBlock {
  const q = query.trim().toLowerCase()
  if (!q) return block
  const visible = new Set(
    block.nodes
      .filter((node) => {
        const haystack = [
          node.label,
          node.display_label,
          node.semantic_label,
          node.business_label,
          node.detail,
          ...(node.assigned_signals ?? []),
          ...(node.condition_signals ?? []),
        ].join(' ').toLowerCase()
        return haystack.includes(q)
      })
      .map((node) => node.id),
  )
  const edges = block.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target))
  return { ...block, nodes: block.nodes.filter((node) => visible.has(node.id)), edges }
}

function BlockFlow({ block, query, mode }: { block: AlwaysBlock; query: string; mode: ViewMode }) {
  const filteredBlock = useMemo(() => filterBlock(block, query), [block, query])
  const { nodes, edges } = useMemo(
    () => applyDagreLayout(filteredBlock.nodes, filteredBlock.edges, mode),
    [filteredBlock, mode],
  )

  const flowHeight = Math.min(Math.max(300, filteredBlock.nodes.length * 76), 620)

  if (!filteredBlock.nodes.length) {
    return <p className="text-sm text-black/45">No flowchart nodes match this filter.</p>
  }

  return (
    <div style={{
      height: flowHeight,
      background: 'rgba(0,0,0,0.018)',
      border: '1px solid rgba(0,0,0,0.09)',
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(0,0,0,0.06)" gap={20} size={1} />
        <Controls
          showInteractive={false}
          style={{
            background: '#fff',
            border: '1px solid rgba(0,0,0,0.09)',
            borderRadius: 8,
          }}
        />
      </ReactFlow>
    </div>
  )
}

// ─── Assign block section ─────────────────────────────────────────────────────
function AssignSection({ assigns, mode }: { assigns: FlowchartData['assign_blocks']; mode: ViewMode }) {
  if (!assigns.length) return null

  const sectionLabel =
    mode === 'raw'      ? 'Combinational Logic' :
    mode === 'semantic' ? 'Instant Calculation'  :
                          'Always-On Logic'

  return (
    <div className="mt-5">
      <div style={{ marginBottom: 10, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <p className="text-xs font-semibold uppercase tracking-widest text-black/40">
          {sectionLabel}
        </p>
        <span style={{ fontSize: '0.72rem', color: 'rgba(0,0,0,0.42)', fontFamily: 'var(--nav-font, Poppins, sans-serif)' }}>
          {assigns.length} assign{assigns.length === 1 ? '' : 's'}
        </span>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))',
        gap: 10,
      }}>
        {assigns.map((a) => {
          const intentText =
            mode === 'business' ? (a.business_label ?? a.intent_label) :
            mode === 'semantic' ? (a.semantic_label ?? a.intent_label) :
            undefined
          const showCode = mode !== 'business'

          return (
            <div key={a.id} style={{
              background: 'rgba(0,0,0,0.025)',
              border: '1px solid rgba(0,0,0,0.09)',
              borderRadius: 12,
              padding: 14,
              minWidth: 0,
            }}>
              {intentText && (
                <p style={{
                  fontSize: '0.82rem',
                  fontFamily: 'var(--nav-font, Poppins, sans-serif)',
                  fontWeight: 600,
                  color: '#0f1012',
                  marginBottom: showCode ? 10 : 0,
                  lineHeight: 1.45,
                }}>
                  {intentText}
                </p>
              )}
              {showCode && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{
                      fontSize: '0.66rem',
                      color: 'rgba(0,0,0,0.4)',
                      fontFamily: 'var(--nav-font, Poppins, sans-serif)',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                    }}>
                      assign
                    </span>
                  </div>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, auto) auto minmax(0, 1fr)',
                    alignItems: 'start',
                    gap: 8,
                    fontFamily: 'var(--mono-font, "Roboto Mono", monospace)',
                    fontSize: '0.82rem',
                    lineHeight: 1.55,
                    color: '#0f1012',
                    opacity: mode === 'semantic' ? 0.55 : 1,
                  }}>
                    <code style={{ display: 'block', minWidth: 0, overflowWrap: 'anywhere', whiteSpace: 'normal', fontFamily: 'inherit', background: 'transparent', fontWeight: 600 }}>
                      {a.output}
                    </code>
                    <span style={{ color: 'rgba(0,0,0,0.36)' }}>=</span>
                    <code style={{ display: 'block', minWidth: 0, overflowWrap: 'anywhere', whiteSpace: 'normal', fontFamily: 'inherit', background: 'transparent' }}>
                      {a.expression}
                    </code>
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── View mode toggle ─────────────────────────────────────────────────────────

const VIEW_MODE_OPTIONS: { value: ViewMode; label: string; desc: string }[] = [
  { value: 'business', label: 'Overview',  desc: 'Plain-language summary — best for AE / PM who need a quick read without Verilog knowledge' },
  { value: 'semantic', label: 'Semantic',  desc: 'Flow-verb descriptions with raw code as reference — best for tech PM / SE reviewing architecture' },
  { value: 'raw',      label: 'Raw',       desc: 'Original Verilog conditions and assignments with semantic hints — best for engineers debugging' },
]

function ViewModeToggle({ mode, onChange }: { mode: ViewMode; onChange: (m: ViewMode) => void }) {
  return (
    <div className="segmented" style={{ display: 'inline-flex' }}>
      {VIEW_MODE_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={mode === opt.value ? 'active' : ''}
          onClick={() => onChange(opt.value)}
          title={opt.desc}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function Legend({ mode }: { mode: ViewMode }) {
  const items: [string, string][] = mode === 'raw'
    ? [
        ['#378ADD', 'Always block 觸發條件'],
        ['#EF9F27', '條件判斷 / case 分流'],
        ['#1D9E75', '訊號賦值'],
        ['#8b8b8b', '摘要 / 推斷邊'],
      ]
    : [
        ['#378ADD', '流程起點'],
        ['#EF9F27', '決策分支'],
        ['#1D9E75', '狀態 / 資料更新'],
        ['#8b8b8b', '省略或推斷路徑'],
      ]
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 10 }}>
      {items.map(([color, label]) => (
        <span key={label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', color: 'rgba(0,0,0,0.55)' }}>
          <span style={{ width: 10, height: 10, borderRadius: 999, background: color }} />
          {label}
        </span>
      ))}
    </div>
  )
}

function CompactSignals({ block, mode }: { block: AlwaysBlock; mode: ViewMode }) {
  if (mode !== 'raw') return null
  const updates = block.assigned_signals?.slice(0, 4) ?? []
  const controls = block.condition_signals?.slice(0, 4) ?? []
  const parts: string[] = []
  if (updates.length) parts.push(`Writes: ${updates.join(', ')}`)
  if (controls.length) parts.push(`Reads: ${controls.join(', ')}`)
  if (!parts.length) return null
  return (
    <p className="text-xs text-black/45" style={{ fontFamily: 'var(--mono-font, monospace)' }}>
      {parts.join(' · ')}
    </p>
  )
}

function StateDiagram({ data }: { data: NonNullable<FlowchartData['state_diagram']> }) {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <p className="text-sm text-black/60">{data.summary}</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {data.states.map((state) => <span key={state} className="tag font-mono">{state}</span>)}
      </div>
      <div style={{ display: 'grid', gap: 8 }}>
        {data.transitions.length ? data.transitions.map((t, idx) => (
          <div key={`${t.source}-${t.target}-${idx}`} style={{ border: '1px solid rgba(0,0,0,0.09)', borderRadius: 8, padding: '8px 10px', fontFamily: 'var(--mono-font, monospace)', fontSize: '0.8rem' }}>
            {t.source} {'->'} {t.target}
          </div>
        )) : <p className="text-sm text-black/45">No explicit state transitions detected.</p>}
      </div>
    </div>
  )
}

// ─── Main export ──────────────────────────────────────────────────────────────

interface LogicFlowchartProps {
  data: FlowchartData | null
}

export default function LogicFlowchart({ data }: LogicFlowchartProps) {
  const [activeIdx, setActiveIdx] = useState(0)
  const [viewMode, setViewMode] = useState<ViewMode>('business')
  const [flowMode, setFlowMode] = useState<'flow' | 'fsm'>('flow')
  const [query, setQuery] = useState('')
  const [showFilter, setShowFilter] = useState(false)

  if (!data || data.error) {
    return <p className="text-sm text-red-500">Could not parse logic structure.</p>
  }

  const { always_blocks, assign_blocks } = data
  const hasAlways = always_blocks.length > 0
  const hasAssign = assign_blocks.length > 0

  if (!hasAlways && !hasAssign) {
    return <p className="text-sm text-black/45">No logic blocks found in this design.</p>
  }

  const safeIdx = Math.min(activeIdx, always_blocks.length - 1)
  const activeBlock = hasAlways ? always_blocks[safeIdx] : null
  const shouldOfferFilter = (activeBlock?.nodes.length ?? 0) > 10
  const activeQuery = shouldOfferFilter && showFilter ? query : ''

  function exportJson() {
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'logic-flowchart.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div style={{ maxWidth: 680 }}>
          {data.summary && <p className="text-sm text-black/60">{data.summary}</p>}
          {data.truncated && (
            <p className="mt-1 text-xs text-black/40">
              部分內容已省略{data.hidden_count ? `，${data.hidden_count} 個分支未顯示` : ''}。
              {data.truncation_reasons && data.truncation_reasons.length > 0 && (
                <span className="ml-1">
                  ({data.truncation_reasons.map(r => ({
                    always_block_limit: '區塊過多',
                    case_arm_limit: 'case 分支過多',
                    nesting_depth_limit: '巢狀過深',
                    loop_summary: '迴圈已摘要',
                  }[r] ?? r)).join('、')})
                </span>
              )}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <ViewModeToggle mode={viewMode} onChange={setViewMode} />
          {data.state_diagram && (
            <div className="segmented" style={{ display: 'inline-flex' }}>
              <button type="button" className={flowMode === 'flow' ? 'active' : ''} onClick={() => setFlowMode('flow')}>Flow</button>
              <button type="button" className={flowMode === 'fsm' ? 'active' : ''} onClick={() => setFlowMode('fsm')}>FSM</button>
            </div>
          )}
        </div>
      </div>

      {flowMode === 'fsm' && data.state_diagram && (
        <div className="mt-4">
          <StateDiagram data={data.state_diagram} />
        </div>
      )}

      {flowMode === 'flow' && (
        <>
          {always_blocks.length > 1 && (
            <div className="mb-4" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {always_blocks.map((ab, i) => {
                const tabLabel = viewMode === 'raw'
                  ? (ab.trigger === '*' ? 'always @(*)' : ab.trigger)
                  : (ab.title ?? (ab.trigger === '*' ? 'always @(*)' : ab.trigger))
                return (
                  <button
                    key={ab.id}
                    type="button"
                    onClick={() => setActiveIdx(i)}
                    style={{
                      minHeight: 32,
                      maxWidth: 260,
                      borderRadius: 999,
                      border: '1px solid rgba(0,0,0,0.12)',
                      background: safeIdx === i ? '#0f1012' : 'rgba(0,0,0,0.025)',
                      color: safeIdx === i ? '#fff' : 'rgba(0,0,0,0.58)',
                      padding: '6px 12px',
                      fontFamily: viewMode === 'raw' ? 'var(--mono-font, monospace)' : 'var(--nav-font, Poppins, sans-serif)',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {tabLabel}
                  </button>
                )
              })}
            </div>
          )}

          {activeBlock && (
            <>
              <div className="mb-3 mt-2 flex flex-wrap items-end justify-between gap-3">
                <div style={{ maxWidth: 760 }}>
                  {activeBlock.summary && viewMode !== 'raw' && (
                    <p className="text-sm text-black/60">{activeBlock.summary}</p>
                  )}
                  <CompactSignals block={activeBlock} mode={viewMode} />
                </div>
                {shouldOfferFilter && (
                  <button
                    type="button"
                    className="analysis-share-button"
                    onClick={() => setShowFilter((v) => !v)}
                    style={{ background: showFilter ? '#0f1012' : '#fff', color: showFilter ? '#fff' : '#0f1012' }}
                  >
                    Find signal
                  </button>
                )}
              </div>
              {shouldOfferFilter && showFilter && (
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Signal name or keyword"
                  style={{
                    width: '100%',
                    maxWidth: 320,
                    border: '1px solid rgba(0,0,0,0.12)',
                    borderRadius: 8,
                    padding: '8px 10px',
                    fontSize: '0.82rem',
                    marginBottom: 12,
                  }}
                />
              )}
              <BlockFlow block={activeBlock} query={activeQuery} mode={viewMode} />
            </>
          )}

          {hasAssign && <AssignSection assigns={assign_blocks} mode={viewMode} />}
        </>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-widest text-black/35">
          Flowchart details
        </summary>
        <div className="mt-3 grid gap-3">
          <Legend mode={viewMode} />
          {activeBlock?.source_line_start && (
            <p className="text-xs text-black/45">
              Source lines {activeBlock.source_line_start}
              {activeBlock.source_line_end && activeBlock.source_line_end !== activeBlock.source_line_start
                ? `-${activeBlock.source_line_end}`
                : ''}
            </p>
          )}
          <div>
            <button type="button" className="analysis-share-button" onClick={exportJson}>Export JSON</button>
          </div>
        </div>
      </details>
    </div>
  )
}
