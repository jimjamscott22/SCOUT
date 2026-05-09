import type { Mode } from '../types/api'

interface Props {
  mode: Mode
  onChange: (mode: Mode) => void
}

export function ModeToggle({ mode, onChange }: Props) {
  return (
    <div className="flex rounded border border-[var(--border)] overflow-hidden text-sm font-semibold">
      {(['footprint', 'threat'] as Mode[]).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={[
            'px-4 py-1.5 uppercase tracking-widest transition-colors',
            mode === m
              ? 'bg-[var(--accent)] text-black'
              : 'bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--text)]',
          ].join(' ')}
        >
          {m}
        </button>
      ))}
    </div>
  )
}
