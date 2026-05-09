import cytoscape from 'cytoscape'
import { useEffect, useRef } from 'react'
import { toCyElements } from '../lib/graph'
import type { EdgeOut, NodeOut } from '../types/api'

// Cytoscape doesn't read CSS variables, so node colours are hardcoded here.
// They mirror the theme values in theme.css.
const STYLESHEET: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'font-size': '10px',
      color: '#e0e0e0',
      'background-color': '#555555',
      width: 28,
      height: 28,
      'text-margin-y': 4,
    },
  },
  { selector: 'node[type="breach"]',     style: { 'background-color': '#ef4444' } },
  { selector: 'node[type="account"]',    style: { 'background-color': '#3b82f6' } },
  { selector: 'node[type="repo"]',       style: { 'background-color': '#3b82f6' } },
  { selector: 'node[type="email"]',      style: { 'background-color': '#00ff88' } },
  { selector: 'node[type="ip"]',         style: { 'background-color': '#ffb000' } },
  { selector: 'node[type="domain"]',     style: { 'background-color': '#a78bfa' } },
  { selector: 'node[type="cert"]',       style: { 'background-color': '#f59e0b' } },
  { selector: 'node[type="dns_record"]', style: { 'background-color': '#94a3b8' } },
  { selector: 'node[type="username"]',   style: { 'background-color': '#22d3ee' } },
  { selector: 'node[type="hash"]',       style: { 'background-color': '#f97316' } },
  { selector: 'node[type="url"]',        style: { 'background-color': '#e879f9' } },
  {
    selector: 'node:selected',
    style: { 'border-width': 2, 'border-color': '#ffffff' },
  },
  {
    selector: 'edge',
    style: {
      label: 'data(label)',
      'font-size': '9px',
      color: '#888888',
      'line-color': '#333333',
      'target-arrow-color': '#333333',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      width: 1.5,
      'text-rotation': 'autorotate',
    },
  },
]

interface Props {
  nodes: NodeOut[]
  edges: EdgeOut[]
  onNodeClick: (node: NodeOut) => void
}

export function ResultsGraph({ nodes, edges, onNodeClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  // Stable ref so the tap handler always calls the latest callback without
  // needing to destroy/rebuild the graph when onNodeClick identity changes.
  const onClickRef = useRef(onNodeClick)
  useEffect(() => { onClickRef.current = onNodeClick })

  useEffect(() => {
    if (!containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: toCyElements(nodes, edges),
      style: STYLESHEET,
      layout: { name: 'cose', animate: false, padding: 40 },
      wheelSensitivity: 0.3,
    })

    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id() as string
      const match = nodes.find((n) => n.id === nodeId)
      if (match) onClickRef.current(match)
    })

    return () => cy.destroy()
  }, [nodes, edges]) // onClickRef is stable; intentionally omitted

  return <div ref={containerRef} className="w-full h-full bg-[var(--bg)]" />
}
