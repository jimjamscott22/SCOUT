import { useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { postInvestigate } from '../lib/api'
import type { InputType, InvestigationOut, Mode } from '../types/api'

const INPUT_TYPES: Record<Mode, { value: InputType; label: string }[]> = {
  footprint: [
    { value: 'email', label: 'Email' },
    { value: 'username', label: 'Username' },
    { value: 'domain', label: 'Domain' },
  ],
  threat: [
    { value: 'ip', label: 'IP Address' },
    { value: 'domain', label: 'Domain' },
  ],
}

interface Props {
  mode: Mode
  onResult: (result: InvestigationOut) => void
}

export function InvestigationForm({ mode, onResult }: Props) {
  const options = INPUT_TYPES[mode]
  const [targetType, setTargetType] = useState<InputType>(options[0].value)
  const [target, setTarget] = useState('')

  useEffect(() => {
    setTargetType(INPUT_TYPES[mode][0].value)
  }, [mode])

  const mutation = useMutation({
    mutationFn: () => postInvestigate({ mode, target, target_type: targetType }),
    onSuccess: onResult,
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (target.trim()) mutation.mutate()
  }

  const busy = mutation.isPending

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-center">
      <select
        value={targetType}
        onChange={(e) => setTargetType(e.target.value as InputType)}
        disabled={busy}
        className="bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] rounded px-3 py-2 text-sm focus:outline-none focus:border-[var(--accent)]"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      <input
        type="text"
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        disabled={busy}
        placeholder={`Enter ${targetType}…`}
        className="flex-1 bg-[var(--surface)] border border-[var(--border)] text-[var(--text)] rounded px-3 py-2 text-sm placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)]"
      />

      <button
        type="submit"
        disabled={busy || !target.trim()}
        className="px-5 py-2 rounded text-sm font-semibold uppercase tracking-widest bg-[var(--accent)] text-black disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
      >
        {busy ? '…' : 'Investigate'}
      </button>

      {mutation.isError && (
        <span className="text-red-400 text-xs ml-2">
          {String(mutation.error)}
        </span>
      )}
    </form>
  )
}
