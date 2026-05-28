import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { DependencyGraphData } from '../types'

interface SimNode extends d3.SimulationNodeDatum {
  id: string
  in_degree: number
}

type SimLink = d3.SimulationLinkDatum<SimNode>

interface DependencyGraphProps {
  data?: DependencyGraphData | null
}

export default function DependencyGraph({ data }: DependencyGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!data?.nodes?.length || !svgRef.current) return

    const el = svgRef.current
    d3.select(el).selectAll('*').remove()

    const W = el.clientWidth || 480
    const H = 220
    const critPath = new Set(data.critical_path ?? [])

    const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }))
    const links: SimLink[] = data.links.map((l) => ({ ...l }))

    const sim = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(90))
      .force('charge', d3.forceManyBody<SimNode>().strength(-200))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<SimNode>(40))

    const svg = d3.select(el)
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('width', '100%')

    svg.append('defs').append('marker')
      .attr('id', 'arrow').attr('viewBox', '0 -5 10 10')
      .attr('refX', 22).attr('markerWidth', 6).attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#9ca3af')

    const link = svg.append('g').selectAll<SVGLineElement, SimLink>('line')
      .data(links).join('line')
      .attr('stroke', '#d1d5db').attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrow)')

    const drag = d3.drag<SVGGElement, SimNode>()
      .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
      .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })

    const node = svg.append('g').selectAll<SVGGElement, SimNode>('g')
      .data(nodes).join('g')
      .call(drag)

    node.append('rect')
      .attr('rx', 6).attr('ry', 6).attr('width', 80).attr('height', 28)
      .attr('x', -40).attr('y', -14)
      .attr('fill', (d) => d.in_degree === 0 ? '#dbeafe' : '#f0fdf4')
      .attr('stroke', (d) => critPath.has(d.id) ? '#3b82f6' : '#d1d5db')
      .attr('stroke-width', (d) => critPath.has(d.id) ? 2 : 1)

    node.append('text')
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('font-size', 11).attr('fill', '#374151')
      .text((d) => d.id.length > 12 ? d.id.slice(0, 11) + '…' : d.id)

    node.append('title').text((d) => d.id)

    sim.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0)
      node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => { sim.stop() }
  }, [data])

  return <svg ref={svgRef} style={{ width: '100%', minHeight: 220 }} />
}
