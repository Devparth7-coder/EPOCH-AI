import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertCircle, ArrowRight, ClipboardPaste, FileText, Link2, Play, RefreshCw, Sparkles, Waypoints,
} from 'lucide-react'
import { api, type SessionDetail } from '../lib/api'
import { ms, num, pct, shortDate, titleCase } from '../lib/format'
import { verdictMeta } from '../lib/verdicts'
import PipelineTimeline from '../components/PipelineTimeline'
import {
  Callout, EmptyState, ErrorState, Panel, QualityBar, SectionHeader, Spinner, VerdictBadge,
} from '../components/ui'

const TABS = [
  { key: 'text', label: 'Claim or text', icon: FileText, hint: 'One or more factual statements to verify.' },
  { key: 'ai_answer', label: 'Paste AI answer', icon: ClipboardPaste, hint: 'Verify a model answer claim by claim.' },
  { key: 'url', label: 'URL', icon: Link2, hint: 'Fetch a public page and verify its assertions.' },
] as const

const DEPTHS = [
  { key: 'quick', label: 'Quick', body: 'Fewer claims, one search per claim.' },
  { key: 'standard', label: 'Standard', body: 'Up to 12 claims, two targeted searches each.' },
  { key: 'deep', label: 'Deep', body: 'Contradiction probes and broader retrieval.' },
] as const

const EXAMPLES = [
  'Python 3.7 is the newest version of Python and should be used for all new projects. React 19 was released in December 2024.',
  'Node.js 18 is the current Active LTS release. PostgreSQL 16 is the newest major release of PostgreSQL.',
  'The GDPR became applicable on May 25, 2018. The EU AI Act entered into force on August 1, 2024. TLS 1.3 is specified in RFC 8446.',
]

export default function Workspace() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<(typeof TABS)[number]['key']>('text')
  const [content, setContent] = useState('')
  const [depth, setDepth] = useState<(typeof DEPTHS)[number]['key']>('standard')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [preview, setPreview] = useState<{ text: string; claim_type: string; checkworthiness: number }[] | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const pollRef = useRef<number | null>(null)

  // load an existing session when routed to /app/workspace/:id
  useEffect(() => {
    if (!id) {
      setSession(null)
      return
    }
    let cancelled = false
    const load = async () => {
      try {
        const detail = await api.research(id)
        if (cancelled) return
        setSession(detail)
        if (detail.status === 'running' || detail.status === 'queued') {
          pollRef.current = window.setTimeout(load, 800)
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    }
    load()
    return () => {
      cancelled = true
      if (pollRef.current) window.clearTimeout(pollRef.current)
    }
  }, [id])

  // live claim preview (fast path, no persistence, no research)
  useEffect(() => {
    if (session || content.trim().length < 40) {
      setPreview(null)
      return
    }
    const timer = window.setTimeout(async () => {
      setPreviewLoading(true)
      try {
        const res = await api.previewClaims(content)
        setPreview(res.claims.slice(0, 6))
      } catch {
        setPreview(null)
      } finally {
        setPreviewLoading(false)
      }
    }, 600)
    return () => window.clearTimeout(timer)
  }, [content, session])

  const submit = useCallback(async () => {
    setError(null)
    if (content.trim().length < 10) {
      setError('Enter at least a sentence to verify.')
      return
    }
    setSubmitting(true)
    try {
      const created = await api.createResearch({ content, input_type: tab, depth })
      navigate(`/app/workspace/${created.research_id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }, [content, tab, depth, navigate])

  const running = session && (session.status === 'running' || session.status === 'queued')
  const metrics = (session?.metrics ?? {}) as Record<string, number>

  const verdictSummary = useMemo(() => {
    if (!session?.claims?.length) return null
    const counts: Record<string, number> = {}
    session.claims.forEach((c) => {
      const v = c.verdict?.verdict
      if (v) counts[v] = (counts[v] ?? 0) + 1
    })
    return counts
  }, [session])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label mb-1">Research workspace</div>
          <h1 className="text-xl font-semibold text-white">
            {session ? session.title : 'Investigate a claim'}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            {session
              ? 'Execution state below is read from the backend on every poll — no simulated progress.'
              : 'EPOCH decomposes your input into atomic claims, retrieves current evidence and issues an explained verdict for each one.'}
          </p>
        </div>
        {session && (
          <div className="flex flex-wrap items-center gap-2">
            {session.status === 'succeeded' && (
              <>
                <Link to={`/app/research/${session.id}`} className="btn-primary">
                  Open report <ArrowRight size={14} />
                </Link>
                <Link to={`/app/evidence/${session.id}`} className="btn-ghost">
                  <Waypoints size={14} /> Evidence graph
                </Link>
              </>
            )}
            <button className="btn-ghost" onClick={() => navigate('/app/workspace')}>
              <RefreshCw size={14} /> New
            </button>
          </div>
        )}
      </div>

      {error && <ErrorState message={error} />}

      <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        {/* ---------- input ---------- */}
        <div className="space-y-4">
          {!session ? (
            <Panel className="p-5">
              <div className="mb-3 flex flex-wrap gap-1.5">
                {TABS.map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setTab(t.key)}
                    className={`chip transition-colors ${
                      tab === t.key
                        ? 'border-cyan-epoch/40 bg-cyan-epoch/10 text-cyan-200'
                        : 'border-ink-600 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <t.icon size={11} />
                    {t.label}
                  </button>
                ))}
              </div>

              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={9}
                spellCheck={false}
                placeholder={
                  tab === 'url'
                    ? 'https://example.com/article-to-verify'
                    : tab === 'ai_answer'
                      ? 'Paste the model answer you want to verify…'
                      : 'Paste one or more factual claims…'
                }
                className="input resize-y font-mono text-[0.8125rem] leading-relaxed"
              />

              <div className="mt-2 flex items-center justify-between text-2xs text-slate-500">
                <span>{content.length.toLocaleString()} / 20,000 characters</span>
                <span>{TABS.find((t) => t.key === tab)?.hint}</span>
              </div>

              <div className="mt-4">
                <div className="label mb-2">Research depth</div>
                <div className="grid gap-2 sm:grid-cols-3">
                  {DEPTHS.map((d) => (
                    <button
                      key={d.key}
                      onClick={() => setDepth(d.key)}
                      className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                        depth === d.key
                          ? 'border-cyan-epoch/45 bg-cyan-epoch/[0.08]'
                          : 'border-ink-600/80 hover:border-ink-500'
                      }`}
                    >
                      <div className={`text-[0.8125rem] font-medium ${depth === d.key ? 'text-cyan-200' : 'text-slate-300'}`}>
                        {d.label}
                      </div>
                      <div className="mt-0.5 text-2xs leading-relaxed text-slate-500">{d.body}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between gap-3">
                <button onClick={submit} disabled={submitting || content.trim().length < 10} className="btn-solid">
                  {submitting ? <Spinner label="Dispatching…" /> : <><Play size={14} /> Run verification</>}
                </button>
                <button
                  className="text-2xs text-slate-500 hover:text-slate-300"
                  onClick={() => setContent(EXAMPLES[Math.floor(Math.random() * EXAMPLES.length)])}
                >
                  <Sparkles size={11} className="mr-1 inline" />
                  insert an example
                </button>
              </div>
            </Panel>
          ) : (
            <Panel className="p-5">
              <SectionHeader
                eyebrow="Original input"
                title={session.input_type === 'url' ? 'Fetched document' : titleCase(session.input_type)}
                actions={
                  <span className="chip border-ink-600 text-slate-400">
                    depth {session.depth} · {session.runtime_mode}
                  </span>
                }
              />
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-ink-700/70 bg-ink-900/70 p-3 text-[0.8125rem] leading-relaxed text-slate-300">
                {session.original_query}
              </pre>
              {session.source_url && (
                <a
                  href={session.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-2 block truncate text-2xs text-cyan-400 hover:text-cyan-300"
                >
                  {session.source_url}
                </a>
              )}
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Stat label="Claims" value={num(session.claim_count)} />
                <Stat label="Sources" value={num(session.evidence_count)} />
                <Stat label="Searches" value={num(metrics.searches)} />
                <Stat label="Runtime" value={ms(metrics.pipeline_latency_ms)} />
              </div>
            </Panel>
          )}

          {/* claim preview before running */}
          {!session && preview && preview.length > 0 && (
            <Panel className="p-5">
              <SectionHeader
                eyebrow="Live preview"
                title="Claims EPOCH can see"
                description="Extracted locally without spending retrieval budget. Run the pipeline for verdicts."
                actions={previewLoading ? <Spinner label="updating" /> : null}
              />
              <ul className="space-y-1.5">
                {preview.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 rounded-md border border-ink-700/60 bg-ink-900/40 px-2.5 py-2">
                    <span className="mono mt-0.5 text-2xs text-slate-600">{String(i + 1).padStart(2, '0')}</span>
                    <span className="min-w-0 flex-1 text-[0.8125rem] leading-relaxed text-slate-300">{c.text}</span>
                    <span className="chip shrink-0 border-ink-600 text-slate-500">{c.claim_type}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {session?.status === 'failed' && (
            <Callout tone="critical" title="Investigation failed">
              {session.error ?? 'The pipeline stopped before producing a report.'}
            </Callout>
          )}
        </div>

        {/* ---------- pipeline ---------- */}
        <div className="space-y-4">
          <Panel className="p-5">
            {!session ? (
              <div className="py-6">
                <EmptyState
                  icon={<Play size={16} />}
                  title="Execution states appear here"
                  description="Six stages run in sequence: extraction, planning, retrieval, temporal analysis, contradiction detection and verdicts."
                />
              </div>
            ) : (
              <>
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <VerdictBadge verdict={session.overall_verdict} size="md" />
                    {session.confidence !== null && (
                      <span className="mono text-2xs text-slate-500">confidence {pct(session.confidence)}</span>
                    )}
                  </div>
                  <span className={`chip ${running ? 'border-cyan-epoch/40 text-cyan-200' : 'border-ink-600 text-slate-400'}`}>
                    {titleCase(session.status)}
                  </span>
                </div>
                <PipelineTimeline stages={session.stage_states.length ? session.stage_states : placeholderStages()} />
                {running && (
                  <div className="mt-3 flex items-center gap-2 text-2xs text-slate-500">
                    <AlertCircle size={11} className="text-cyan-300" />
                    live — polling the research resource
                  </div>
                )}
                {session.summary && (
                  <div className="mt-4 rounded-lg border border-ink-700/70 bg-ink-900/50 p-3 text-xs leading-relaxed text-slate-300">
                    {session.summary}
                  </div>
                )}
                {verdictSummary && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {Object.entries(verdictSummary).map(([verdict, count]) => (
                      <span
                        key={verdict}
                        className="chip"
                        style={{
                          color: verdictMeta(verdict).color,
                          borderColor: `${verdictMeta(verdict).color}44`,
                          background: `${verdictMeta(verdict).color}12`,
                        }}
                      >
                        {verdictMeta(verdict).label} {count}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </Panel>

          {session && session.claims.length > 0 && (
            <Panel className="p-5">
              <SectionHeader eyebrow="Results" title="Claim verdicts" />
              <ul className="space-y-2">
                {session.claims.map((claim) => (
                  <motion.li
                    key={claim.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-lg border border-ink-700/70 bg-ink-900/40 p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.8125rem] leading-relaxed text-slate-200">{claim.text}</p>
                      <VerdictBadge verdict={claim.verdict?.verdict} size="sm" />
                    </div>
                    {claim.verdict && (
                      <>
                        <p className="mt-1.5 text-2xs leading-relaxed text-slate-500">{claim.verdict.explanation}</p>
                        <div className="mt-2 grid grid-cols-3 gap-2">
                          <QualityBar value={claim.verdict.evidence_quality} label="Quality" />
                          <QualityBar value={claim.verdict.calibrated_probability} label="Confidence" />
                          <div className="text-2xs text-slate-500">
                            <div className="mb-1 flex justify-between">
                              <span>Support</span>
                              <span className="mono text-slate-400">{claim.verdict.supporting_count}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>Contra</span>
                              <span className="mono text-slate-400">{claim.verdict.contradicting_count}</span>
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                  </motion.li>
                ))}
              </ul>
            </Panel>
          )}

          {session?.status === 'succeeded' && (
            <Panel className="p-5">
              <SectionHeader eyebrow="Provenance" title="Execution detail" />
              <div className="grid grid-cols-2 gap-2 text-2xs">
                <Detail label="Started" value={shortDate(session.started_at)} />
                <Detail label="Completed" value={shortDate(session.completed_at)} />
                <Detail label="Tokens" value={num(metrics.tokens)} />
                <Detail label="Estimated cost" value={`$${Number(metrics.estimated_cost_usd ?? 0).toFixed(4)}`} />
                <Detail label="Retrieval provider" value={String(metrics.search_provider ?? '—')} />
                <Detail label="Duplicates removed" value={num(metrics.deduplicated)} />
                <Detail label="Temporal observations" value={num(metrics.temporal_observations)} />
                <Detail label="Evidence quality" value={pct(Number(metrics.evidence_quality_mean ?? 0))} />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {session.models_used.map((m) => (
                  <span key={m} className="chip border-ink-600 text-slate-400">
                    {m}
                  </span>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}

function placeholderStages() {
  return [
    'extracting_claims', 'planning_research', 'retrieving_evidence',
    'analyzing_temporal', 'detecting_contradictions', 'generating_verdicts',
  ].map((stage) => ({
    stage,
    label: stage.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    status: 'pending' as const,
    started_at: null,
    finished_at: null,
    duration_ms: null,
    detail: null,
    metrics: {},
  }))
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-700/70 bg-ink-900/50 px-2.5 py-2">
      <div className="label">{label}</div>
      <div className="mono mt-1 text-sm text-slate-200">{value}</div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-ink-700/60 bg-ink-900/40 px-2 py-1.5">
      <span className="text-slate-500">{label}</span>
      <span className="mono truncate text-slate-300">{value}</span>
    </div>
  )
}
