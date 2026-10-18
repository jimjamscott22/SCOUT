import { useCallback, useEffect, useState } from 'react'
import { InvestigationForm } from './components/InvestigationForm'
import { ModeToggle } from './components/ModeToggle'
import { NodeDetailPanel } from './components/NodeDetailPanel'
import { ResultsGraph } from './components/ResultsGraph'
import { ResultsList } from './components/ResultsList'
import type { InvestigationOut, Mode, NodeOut, SourceRunOut } from './types/api'

/** Explain why an investigation produced no nodes. */
function describeEmpty(runs: SourceRunOut[]): string {
  if (runs.length === 0) return 'No sources support this target type in this mode.'
  if (runs.every((r) => r.status === 'skipped')) {
    return 'Every source was skipped — they need API keys. Run `scout config init` and add keys to ~/.scout/config.toml.'
  }
  if (runs.some((r) => r.status === 'error')) {
    return 'No results, and some sources errored. See the source list for details.'
  }
  return 'No data found for this target.'
}

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
              {result.nodes.length === 0 ? (
                <div className="h-full flex items-center justify-center px-8">
                  <p className="text-[var(--muted)] text-sm text-center max-w-md">
                    {describeEmpty(result.source_runs)}
                  </p>
                </div>
              ) : (
                <ResultsGraph
                  nodes={result.nodes}
                  edges={result.edges}
                  onNodeClick={handleNodeClick}
                />
              )}
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
