import type cytoscape from 'cytoscape'
import type { EdgeOut, NodeOut } from '../types/api'

export function toCyElements(nodes: NodeOut[], edges: EdgeOut[]): cytoscape.ElementDefinition[] {
  const cyNodes: cytoscape.ElementDefinition[] = nodes.map((n) => ({
    data: { id: n.id, label: n.label, type: n.type },
  }))
  const cyEdges: cytoscape.ElementDefinition[] = edges.map((e, i) => ({
    data: { id: `e-${i}`, source: e.src_id, target: e.dst_id, label: e.relation },
  }))
  return [...cyNodes, ...cyEdges]
}
