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

function TriggerNode({ data }: { data: { label: string } }) {
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
      <Handle type="source" position={Position.Bottom} style={{ background: '#2563eb' }} />
    </div>
  )
}

function DiamondNode({ data }: { data: { label: string } }) {
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
        </span>
      </div>
      {/* YES branches right, NO continues down (main flow) */}
      <Handle type="source" position={Position.Right} id="yes" style={{ background: '#1D9E75', top: '50%' }} />
      <Handle type="source" position={Position.Bottom} id="no" style={{ background: '#9ca3af', left: '50%' }} />
      <Handle type="source" position={Position.Left} id="branch" style={{ background: '#9ca3af', top: '50%' }} />
    </>
  )
}

function ProcessNode({ data }: { data: { label: string } }) {
  return (
    <div style={{
      background: 'rgba(29,158,117,0.10)',
      border: '1.5px solid rgba(29,158,117,0.4)',
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
      data: { label: n.label },
    }
  })

  const edges: Edge[] = rawEdges.map((e) => {
    const isYes = e.label === 'YES'
    const isNo = e.label === 'NO'
    return {
      id: e.id,
      type: 'smoothstep',
      source: e.source,
      target: e.target,
      sourceHandle: isYes ? 'yes' : isNo ? 'no' : e.label ? 'branch' : undefined,
      label: e.label,
      style: {
        stroke: isYes ? '#1D9E75' : isNo ? '#9ca3af' : '#d1d5db',
        strokeWidth: 1.5,
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

function BlockFlow({ block }: { block: AlwaysBlock }) {
  const { nodes, edges } = useMemo(
    () => applyDagreLayout(block.nodes, block.edges),
    [block],
  )

  const flowHeight = Math.min(Math.max(300, block.nodes.length * 76), 620)

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

// ─── Main export ──────────────────────────────────────────────────────────────

interface LogicFlowchartProps {
  data: FlowchartData | null
}

export default function LogicFlowchart({ data }: LogicFlowchartProps) {
  const [activeIdx, setActiveIdx] = useState(0)

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

  return (
    <div>
      {/* Tab switcher for multiple always blocks */}
      {always_blocks.length > 1 && (
        <div className="segmented mb-4" style={{ display: 'inline-flex' }}>
          {always_blocks.map((ab, i) => (
            <button
              key={ab.id}
              type="button"
              className={safeIdx === i ? 'active' : ''}
              onClick={() => setActiveIdx(i)}
            >
              {ab.trigger === '*' ? 'always @(*)' : ab.trigger}
            </button>
          ))}
        </div>
      )}

      {/* ReactFlow area */}
      {hasAlways && <BlockFlow block={always_blocks[safeIdx]} />}

      {/* Assign / combinational section */}
      {hasAssign && <AssignSection assigns={assign_blocks} />}
    </div>
  )
}
