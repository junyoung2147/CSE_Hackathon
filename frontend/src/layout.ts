import dagre from '@dagrejs/dagre'
import type { Edge as FlowEdge, Node as FlowNode } from '@xyflow/react'
import { edges, subjects, type Edge } from './data'

export const NODE_W = 168
export const NODE_H = 46

/**
 * dagre로 왼쪽→오른쪽 층 배치(선수과목이 왼쪽). 선수(pre) 간선만 배치에 쓰고,
 * 관련(rel) 간선은 배치에 영향 없이 점선으로만 그린다.
 */
export function layoutGraph(showIsolated: boolean) {
  const connected = new Set<string>()
  for (const e of edges) {
    connected.add(e.from)
    connected.add(e.to)
  }
  const visible = subjects.filter((s) => showIsolated || connected.has(s.code))

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'LR', nodesep: 18, ranksep: 90, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const s of visible) g.setNode(s.code, { width: NODE_W, height: NODE_H })
  for (const e of edges) {
    if (e.type === 'pre' && g.hasNode(e.from) && g.hasNode(e.to)) g.setEdge(e.from, e.to)
  }
  dagre.layout(g)

  const positions = new Map<string, { x: number; y: number }>()
  for (const s of visible) {
    const n = g.node(s.code)
    positions.set(s.code, { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 })
  }
  return { visible, positions }
}

export function toFlowEdges(highlight: Set<string>, selected: string | null): FlowEdge[] {
  return edges.map((e: Edge, i) => {
    const onPath =
      selected !== null && e.type === 'pre' && (e.to === selected || highlight.has(e.to)) && highlight.has(e.from)
    const isRel = e.type === 'rel'
    return {
      id: `e${i}-${e.from}-${e.to}`,
      source: e.from,
      target: e.to,
      type: 'default',
      animated: onPath,
      style: {
        stroke: onPath ? '#d97706' : isRel ? '#9ca3af' : '#cbd5e1',
        strokeWidth: onPath ? 2.5 : 1.2,
        strokeDasharray: isRel ? '6 4' : e.orWith.length ? '2 3' : undefined,
        opacity: selected && !onPath ? 0.35 : 1,
      },
    }
  })
}

export type NodeData = { label: string }
export type SubjectNode = FlowNode<NodeData>
