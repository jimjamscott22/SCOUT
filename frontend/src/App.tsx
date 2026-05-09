import { useCallback, useEffect, useState } from 'react'
import { InvestigationForm } from './components/InvestigationForm'
import { ModeToggle } from './components/ModeToggle'
import { NodeDetailPanel } from './components/NodeDetailPanel'
import { ResultsGraph } from './components/ResultsGraph'
import { ResultsList } from './components/ResultsList'
import type { InvestigationOut, Mode, NodeOut } from './types/api'

export default function App() {
  const [mode, setMode] = useState<Mode>('footprint')
  const [result, setResult] = useState<InvestigationOut | null>(null)
  const [selectedNode, setSelectedNode] = useState<NodeOut | null>(null)

  useEffect(() => {
    document.body.className = mode
  }, [mode])

  function handleModeChange(newMode: Mode) {
    setMode(newMode)
    setResult(null)
    setSelectedNode(null)
  }

  const handleNodeClick = useCallback((node: NodeOut) => {
    setSelectedNode(node)
  }, [])

  function handleResult(r: InvestigationOut) {
    setResult(r)
    setSelectedNode(null)
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="flex items-center justify-between px-6 py-3 border-b border-[var(--border)] flex-shrink-0">
        <span className="text-[var(--accent)] font-bold text-xl tracking-widest">SCOUT</span>
        <ModeToggle mode={mode} onChange={handleModeChange} />
        <button
          type="button"
          className="text-[var(--muted)] hover:text-[var(--text)] text-lg"
          title="Settings"
        >
          ⚙
        </button>
      </header>

      <div className="px-6 py-4 border-b border-[var(--border)] flex-shrink-0">
        <InvestigationForm mode={mode} onResult={handleResult} />
      </div>

      <main className="flex-1 flex overflow-hidden">
        {result == null ? (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-[var(--muted)] text-sm">
              Enter a target above to start an investigation.
            </p>
          </div>
        ) : (
          <>
            {/* Left pane — Cytoscape graph */}
            <div className="flex-1 relative overflow-hidden">
              <ResultsGraph
                nodes={result.nodes}
                edges={result.edges}
                onNodeClick={handleNodeClick}
              />
              {selectedNode != null && (
                <NodeDetailPanel
                  node={selectedNode}
                  onClose={() => setSelectedNode(null)}
                />
              )}
            </div>

            {/* Right pane — source status + node list */}
            <div className="w-72 border-l border-[var(--border)] flex-shrink-0 overflow-hidden">
              <ResultsList
                sourceRuns={result.source_runs}
                nodes={result.nodes}
                onNodeClick={handleNodeClick}
              />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
