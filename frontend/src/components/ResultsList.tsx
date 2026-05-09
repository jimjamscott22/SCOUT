import type { NodeOut, SourceRunOut } from '../types/api'

const STATUS_STYLE: Record<string, string> = {
  ok:        'text-green-400',
  cache_hit: 'text-blue-400',
  skipped:   'text-[var(--muted)]',
  error:     'text-red-400',
}

const STATUS_LABEL: Record<string, string> = {
  ok:        'ok',
  cache_hit: 'cache',
  skipped:   'skip',
  error:     'err',
}

const NODE_DOT: Record<string, string> = {
  breach:     'bg-red-500',
  account:    'bg-blue-500',
  repo:       'bg-blue-500',
  email:      'bg-[#00ff88]',
  ip:         'bg-[#ffb000]',
  domain:     'bg-violet-400',
  cert:       'bg-amber-400',
  dns_record: 'bg-slate-400',
  username:   'bg-cyan-400',
  hash:       'bg-orange-400',
  url:        'bg-fuchsia-400',
}

interface Props {
  sourceRuns: SourceRunOut[]
  nodes: NodeOut[]
  onNodeClick: (node: NodeOut) => void
}

export function ResultsList({ sourceRuns, nodes, onNodeClick }: Props) {
  return (
    <div className="flex flex-col h-full text-sm">
      {/* Source status section */}
      <div className="p-3 border-b border-[var(--border)] flex-shrink-0">
        <p className="text-xs uppercase tracking-widest text-[var(--muted)] mb-2">Sources</p>
        <div className="space-y-1">
          {sourceRuns.map((run) => (
            <div key={run.source_name} className="flex items-center justify-between text-xs">
              <span className="text-[var(--text)] truncate mr-2">{run.source_name}</span>
              <span className={STATUS_STYLE[run.status] ?? 'text-[var(--muted)]'}>
                {STATUS_LABEL[run.status] ?? run.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Node list */}
      <div className="flex-1 overflow-y-auto p-3">
        <p className="text-xs uppercase tracking-widest text-[var(--muted)] mb-2">
          Nodes ({nodes.length})
        </p>
        <div className="space-y-0.5">
          {nodes.map((node) => (
            <button
              key={node.id}
              type="button"
              onClick={() => onNodeClick(node)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left hover:bg-[var(--surface)] transition-colors"
            >
              <span
                className={[
                  'w-2 h-2 rounded-full flex-shrink-0',
                  NODE_DOT[node.type] ?? 'bg-gray-500',
                ].join(' ')}
              />
              <span className="text-xs text-[var(--text)] truncate flex-1">{node.label}</span>
              <span className="text-xs text-[var(--muted)] flex-shrink-0">{node.type}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
