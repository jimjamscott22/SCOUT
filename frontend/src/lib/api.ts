import type { InvestigateRequest, InvestigationOut } from '../types/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${text}`)
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
