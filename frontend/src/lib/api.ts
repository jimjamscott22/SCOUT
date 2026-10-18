import type { InvestigateRequest, InvestigationOut } from '../types/api'

/** Turn a FastAPI error body into one readable sentence. */
function describeError(status: number, body: string): string {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      // Pydantic 422: [{ msg: "Value error, invalid domain: …", loc: [...] }]
      const msgs = detail
        .map((d) => (d as { msg?: string }).msg?.replace(/^Value error, /, ''))
        .filter(Boolean)
      if (msgs.length > 0) return msgs.join('; ')
    }
  } catch {
    // body wasn't JSON (e.g. proxy error page) — fall through
  }
  if (status >= 500) return 'The SCOUT backend hit an error. Check the server logs.'
  return `Request failed (${status})`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      ...init,
    })
  } catch {
    throw new Error('Cannot reach the SCOUT backend. Is `scout serve` running?')
  }
  if (!res.ok) {
    throw new Error(describeError(res.status, await res.text()))
  }
  return res.json() as Promise<T>
}

export function postInvestigate(body: InvestigateRequest): Promise<InvestigationOut> {
  return request<InvestigationOut>('/api/investigate', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getInvestigation(id: string): Promise<InvestigationOut> {
  return request<InvestigationOut>(`/api/investigations/${id}`)
}
