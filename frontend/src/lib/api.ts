/** Typed API client. All credentials stay on the server; the browser calls same-origin /api routes. */
export const API_BASE = '/api/v1'

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code = 'request_failed', status = 500) {
    super(message)
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  const text = await res.text()
  const body = text ? JSON.parse(text) : {}
  if (!res.ok) {
    const err = body?.error ?? {}
    throw new ApiError(err.message ?? `Request failed (${res.status})`, err.code ?? 'request_failed', res.status)
  }
  return body as T
}

export interface StageState {
  stage: string
  label: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  detail: string | null
  metrics: Record<string, unknown>
}

export interface ClaimVerdict {
  verdict: string
  calibrated_probability: number
  evidence_quality: number
  supporting_count: number
  contradicting_count: number
  components: Record<string, number>
  explanation: string
  what_changed: string | null
  limitations: string[]
}

export interface ClaimEvidenceRef {
  source_id: string
  url: string
  title: string
  domain: string
  publisher: string | null
  published_at: string | null
  retrieved_at: string | null
  authority_score: number
  stance: string
  strength: number
  rationale: string
  conflict_kind: string | null
}

export interface Claim {
  id: string
  ordinal: number
  text: string
  claim_type: string
  entities: string[]
  numbers: string[]
  dates: string[]
  versions: string[]
  checkworthiness: number
  search_queries: string[]
  verdict: ClaimVerdict | null
  evidence: ClaimEvidenceRef[]
}

export interface SourcePassage {
  id: string
  text: string
  relevance: number
  start_offset: number
}

export interface Source {
  id: string
  url: string
  canonical_url: string
  domain: string
  title: string
  publisher: string | null
  source_type: string
  published_at: string | null
  effective_at: string | null
  retrieved_at: string
  authority_score: number
  freshness_score: number
  is_superseded: boolean
  version: string | null
  provider: string
  injection_flags: string[]
  passages?: SourcePassage[]
}

export interface TemporalObservation {
  id: string
  claim_id: string
  source_id: string | null
  observation_type: string
  detail: string
  published_at: string | null
  effective_at: string | null
  retrieved_at: string | null
  age_days: number | null
  decay_factor: number | null
}

export interface SessionSummary {
  id: string
  title: string
  excerpt?: string
  input_type: string
  depth: string
  status: string
  stage: string
  overall_verdict: string | null
  confidence: number | null
  runtime_mode: string
  claim_count: number
  created_at: string
  completed_at: string | null
}

export interface SessionDetail extends SessionSummary {
  original_query: string
  source_url: string | null
  progress: number
  summary: string | null
  error: string | null
  stage_states: StageState[]
  models_used: string[]
  metrics: Record<string, number | string | Record<string, number> | null>
  started_at: string | null
  evidence_count: number
  claims: Claim[]
}

export interface GraphNode {
  id: string
  kind: 'claim' | 'source' | 'temporal'
  label: string
  verdict?: string | null
  evidence_quality?: number
  claim_type?: string
  domain?: string
  source_type?: string
  url?: string
  authority?: number
  freshness?: number
  published_at?: string | null
  effective_at?: string | null
  retrieved_at?: string | null
  version?: string | null
  is_superseded?: boolean
  detail?: string
  claim_id?: string
  observation_type?: string
}

export interface GraphLink {
  id: string
  source: string
  target: string
  stance: string
  strength: number
  rationale: string
}

export interface EvidenceBundle {
  research_id: string
  sources: Source[]
  temporal_observations: TemporalObservation[]
  claims: { id: string; text: string; claim_type: string; verdict: string | null; evidence: ClaimEvidenceRef[] }[]
  graph: { nodes: GraphNode[]; links: GraphLink[]; counts: Record<string, number> }
}

export interface Report {
  research_id: string
  title: string
  original_query: string
  input_type: string
  depth: string
  runtime_mode: string
  overall_verdict: string
  confidence: number
  summary: string
  generated_at: string
  claims: Claim[]
  sources: Source[]
  temporal_observations: TemporalObservation[]
  metrics: Record<string, number | string | null>
  limitations: string[]
  calibration: { method: string; trained_on: string; n: number; note: string }
}

export interface Health {
  status: string
  timestamp: string
  uptime_seconds: number
  version: string
  environment: string
  runtime_mode: 'live' | 'hybrid' | 'simulated'
  mode_explanation: string
  database: { ok: boolean; engine: string; error: string | null }
  providers: Record<string, { configured: boolean; base_url?: string | null }>
  model_routing: { primary: string; fallback: string; chain: string[]; gateway: string }
  python: string
  limits: Record<string, number>
}

export interface Analytics {
  runtime_mode: string
  totals: {
    sessions: number
    completed: number
    failed: number
    claims_analyzed: number
    sources_retrieved: number
    outdated_detected: number
    verdicts_issued: number
  }
  verdict_distribution: Record<string, number>
  claim_type_distribution: Record<string, number>
  quality: { mean_evidence_quality: number; mean_calibrated_probability: number }
  performance: {
    mean_pipeline_latency_ms: number
    max_pipeline_latency_ms: number
    tokens_consumed: number
    estimated_cost_usd: number
  }
  activity: { date: string; investigations: number; evidence: number }[]
  top_domains: { domain: string; count: number; mean_authority: number }[]
  recent: {
    id: string
    title: string
    status: string
    overall_verdict: string | null
    confidence: number | null
    claim_count: number
    created_at: string
    runtime_mode: string
  }[]
  benchmarks: {
    id: string
    run_label: string
    system: string
    claim_count: number
    runtime_mode: string
    metrics: Record<string, number>
    created_at: string
  }[]
}

export interface Observability {
  runtime_mode: string
  gateway: string
  model_routing: { primary: string; fallback: string; observed_routes: string[] }
  by_model: {
    provider: string
    model: string
    route: string
    status: string
    calls: number
    mean_latency_ms: number
    prompt_tokens: number
    completion_tokens: number
    cost_usd: number
    retries: number
  }[]
  usage: { total_calls: number; total_tokens: number; estimated_cost_usd: number; provider_failures: number }
  search: { requests: number; failed_requests: number }
  research: { by_status: Record<string, number>; mean_execution_ms: number; verification_failures: number }
  stage_latency_ms: Record<string, number>
  notes: string[]
}

export interface BenchmarkExample {
  id: string
  claim: string
  gold: string
  predicted: string
  evidence_quality: number
  confidence: number
  citations: string[]
  explanation: string
}

export interface BenchmarkLatest {
  available?: boolean
  run_id: string
  dataset_size: number
  runtime_mode: string
  search_provider: string
  generated_at: string
  epoch: Record<string, number>
  baseline: Record<string, number>
  delta: Record<string, number>
  per_class?: Record<string, { support: number; precision: number; recall: number; f1: number }>
  confusion?: Record<string, Record<string, number>>
  calibration?: { a: number; b: number; c: number; trained_on: string; n: number; brier_score: number } | null
  notes: string[]
  examples?: BenchmarkExample[]
}

export const api = {
  health: () => request<Health>('/system/health'),
  observability: () => request<Observability>('/system/observability'),
  analytics: () => request<Analytics>('/analytics'),
  benchmark: () => request<BenchmarkLatest>('/benchmark/latest'),
  history: (params: Record<string, string | number | undefined> = {}) => {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
      .join('&')
    return request<{ total: number; items: SessionSummary[]; limit: number; offset: number }>(`/history?${qs}`)
  },
  createResearch: (payload: { content: string; input_type?: string; depth?: string; title?: string }) =>
    request<{ research_id: string; status: string; runtime_mode: string; poll_url: string }>('/research', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  research: (id: string) => request<SessionDetail>(`/research/${id}`),
  evidence: (id: string) => request<EvidenceBundle>(`/research/${id}/evidence`),
  report: (id: string) => request<Report>(`/research/${id}/report`),
  previewClaims: (content: string) =>
    request<{ claims: { text: string; claim_type: string; checkworthiness: number; dates: string[]; versions: string[] }[]; meta: Record<string, unknown> }>(
      '/claims/preview',
      { method: 'POST', body: JSON.stringify({ content }) },
    ),
}
