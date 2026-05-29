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
      {data.detail && data.detail !== data.label && (
        <span style={{ display: 'block', fontSize: '0.62rem', opacity: 0.85, fontFamily: 'var(--mono-font, monospace)' }}>
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
          {data.detail && data.detail !== data.label && (
            <span style={{ display: 'block', marginTop: 2, fontSize: '0.58rem', fontFamily: 'var(--mono-font, monospace)', opacity: 0.65 }}>
              {data.detail}
            </span>
          )}
        </span>
      </div>
      {/* YES branches right, NO continues down (main flow) */}
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
      fontFamily: 'var(--mono-font, "Roboto Mono", monospace)',
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
      {data.detail && data.detail !== data.label && (
        <span style={{ display: 'block', marginTop: 4, fontSize: '0.68rem', color: 'rgba(0,0,0,0.5)' }}>
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

function applyDagreLayout(rawNodes: FlowNode[], rawEdges: FlowEdge[]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', ranksep: 56, nodesep: 36 })

  rawNodes.forEach((n) => {
    const w = NODE_WIDTH[n.type] ?? 140
    // process node 高度依行數動態調整
    const h = n.type === 'process'
      ? Math.max(NODE_HEIGHT.process, n.label.split('\n').length * 22 + 16)
      : (NODE_HEIGHT[n.type] ?? 48)
    g.setNode(n.id, { width: w, height: h })
  })
  rawEdges.forEach((e) => g.setEdge(e.source, e.target))

  dagre.layout(g)

  const nodes: Node[] = rawNodes.map((n) => {
    const pos = g.node(n.id)
    const w = NODE_WIDTH[n.type] ?? 140
    const h = n.type === 'process'
      ? Math.max(NODE_HEIGHT.process, n.label.split('\n').length * 22 + 16)
      : (NODE_HEIGHT[n.type] ?? 48)
    return {
      id: n.id,
      type: n.type,
      position: { x: pos.x - w / 2, y: pos.y - h / 2 },
      data: { label: n.display_label ?? n.label, detail: n.detail ?? n.label, kind: n.kind },
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

function BlockFlow({ block, query }: { block: AlwaysBlock; query: string }) {
  const filteredBlock = useMemo(() => filterBlock(block, query), [block, query])
  const { nodes, edges } = useMemo(
    () => applyDagreLayout(filteredBlock.nodes, filteredBlock.edges),
    [filteredBlock],
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

function AssignSection({ assigns }: { assigns: FlowchartData['assign_blocks'] }) {
  if (!assigns.length) return null
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-black/40">
        Combinational Logic
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {assigns.map((a) => (
          <div key={a.id} style={{
            background: 'rgba(0,0,0,0.025)',
            border: '1px solid rgba(0,0,0,0.09)',
            borderLeft: '3px solid #1D9E75',
            borderRadius: 12,
            padding: '10px 14px',
            minWidth: 140,
          }}>
            <p style={{ fontSize: '0.68rem', color: 'rgba(0,0,0,0.4)', marginBottom: 2, fontFamily: 'var(--nav-font)' }}>
              assign
            </p>
            <p style={{ fontFamily: 'var(--mono-font, "Roboto Mono", monospace)', fontSize: '0.82rem', color: '#0f1012' }}>
              {a.output} = {a.expression}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function Legend() {
  const items = [
    ['#378ADD', 'Clock / trigger'],
    ['#EF9F27', 'Condition / state branch'],
    ['#1D9E75', 'Signal update'],
    ['#8b8b8b', 'Summary / inferred edge'],
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

function CompactSignals({ block }: { block: AlwaysBlock }) {
  const updates = block.assigned_signals?.slice(0, 4) ?? []
  const controls = block.condition_signals?.slice(0, 4) ?? []
  const parts = []
  if (updates.length) parts.push(`Updates ${updates.join(', ')}`)
  if (controls.length) parts.push(`Controlled by ${controls.join(', ')}`)
  if (!parts.length) return null
  return <p className="text-xs text-black/45">{parts.join(' · ')}</p>
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
  const [mode, setMode] = useState<'flow' | 'fsm'>('flow')
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
        <div style={{ maxWidth: 760 }}>
          {data.summary && <p className="text-sm text-black/60">{data.summary}</p>}
          {data.truncated && (
            <p className="mt-1 text-xs text-black/40">
              Summary view{data.hidden_count ? `, ${data.hidden_count} branch${data.hidden_count === 1 ? '' : 'es'} hidden` : ''}.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data.state_diagram && (
            <div className="segmented" style={{ display: 'inline-flex' }}>
              <button type="button" className={mode === 'flow' ? 'active' : ''} onClick={() => setMode('flow')}>Flow</button>
              <button type="button" className={mode === 'fsm' ? 'active' : ''} onClick={() => setMode('fsm')}>FSM</button>
            </div>
          )}
        </div>
      </div>

      {mode === 'fsm' && data.state_diagram && (
        <div className="mt-4">
          <StateDiagram data={data.state_diagram} />
        </div>
      )}

      {mode === 'flow' && (
        <>
      {/* Tab switcher for multiple always blocks */}
      {always_blocks.length > 1 && (
        <div className="mb-4" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {always_blocks.map((ab, i) => (
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
                fontFamily: 'var(--nav-font, Poppins, sans-serif)',
                fontSize: '0.78rem',
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {ab.title ?? (ab.trigger === '*' ? 'always @(*)' : ab.trigger)}
            </button>
          ))}
        </div>
      )}

      {/* ReactFlow area */}
      {activeBlock && (
        <>
          <div className="mb-3 mt-2 flex flex-wrap items-end justify-between gap-3">
            <div style={{ maxWidth: 760 }}>
              {activeBlock.summary && <p className="text-sm text-black/60">{activeBlock.summary}</p>}
              <CompactSignals block={activeBlock} />
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
              placeholder="Signal or condition"
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
          <BlockFlow block={activeBlock} query={activeQuery} />
        </>
      )}

      {/* Assign / combinational section */}
      {hasAssign && <AssignSection assigns={assign_blocks} />}
        </>
      )}

      <details className="mt-4">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-widest text-black/35">
          Flowchart details
        </summary>
        <div className="mt-3 grid gap-3">
          <Legend />
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
