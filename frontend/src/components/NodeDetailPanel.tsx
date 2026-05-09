import type { NodeOut } from '../types/api'

interface Props {
  node: NodeOut
  onClose: () => void
}

export function NodeDetailPanel({ node, onClose }: Props) {
  const attrEntries = Object.entries(node.attrs)

  return (
    <div className="absolute top-4 right-4 w-72 bg-[var(--surface)] border border-[var(--border)] rounded p-4 shadow-2xl z-10">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-widest text-[var(--accent)]">{node.type}</span>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--text)] text-xl leading-none"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      <p className="text-sm font-semibold text-[var(--text)] mb-1 break-all">{node.label}</p>
      <p className="text-xs text-[var(--muted)] mb-3 break-all font-mono">{node.id}</p>

      {attrEntries.length > 0 && (
        <div className="border-t border-[var(--border)] pt-3 space-y-1.5">
          {attrEntries.map(([k, v]) => (
            <div key={k} className="flex gap-2 text-xs">
              <span className="text-[var(--muted)] w-28 flex-shrink-0 truncate" title={k}>
                {k}
              </span>
              <span className="text-[var(--text)] break-all">{String(v)}</span>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-[var(--muted)] mt-3 pt-2 border-t border-[var(--border)]">
        via {node.source_name}
      </p>
    </div>
  )
}
