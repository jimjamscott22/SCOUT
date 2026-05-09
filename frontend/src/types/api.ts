export type Mode = 'footprint' | 'threat'

export type InputType = 'email' | 'username' | 'domain' | 'ip' | 'hash' | 'url'

export interface InvestigateRequest {
  mode: Mode
  target: string
  target_type: InputType
  sources?: string[]
}

export interface NodeOut {
  id: string
  type: string
  label: string
  source_name: string
  attrs: Record<string, unknown>
}

export interface EdgeOut {
  src_id: string
  dst_id: string
  relation: string
  source_name: string
}

export interface SourceRunOut {
  source_name: string
  status: string
  cache_hit: boolean
  error_message: string | null
}

export interface InvestigationOut {
  id: string
  mode: Mode
  target: string
  target_type: InputType
  created_at: string
  completed_at: string | null
  status: string
  note: string | null
  source_runs: SourceRunOut[]
  nodes: NodeOut[]
  edges: EdgeOut[]
}

export interface InvestigationSummary {
  id: string
  mode: Mode
  target: string
  target_type: InputType
  created_at: string
  status: string
}

export interface SourceInfo {
  name: string
  modes: string[]
  accepts: string[]
  auth_required: boolean
  configured: boolean
}
