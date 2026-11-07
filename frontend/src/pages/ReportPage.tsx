import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft, CalendarClock, Check, Copy, Download, ExternalLink, FileJson, Info, Printer, ShieldAlert, Waypoints,
} from 'lucide-react'
import { api, type Claim, type Report } from '../lib/api'
import { STANCE_META, verdictMeta } from '../lib/verdicts'
import { ms, num, pct, relativeTime, shortDate, titleCase, usd } from '../lib/format'
import {
  Callout, EmptyState, ErrorState, InlineLink, Panel, QualityBar, SectionHeader, VerdictBadge,
} from '../components/ui'

export default function ReportPage() {
  const { id } = useParams()
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!id) return
    api
      .report(id)
      .then(setReport)
      .catch((e) => setError(e.message))
  }, [id])

  const groupedObservations = useMemo(() => {
    if (!report) return {}
    return report.temporal_observations.reduce<Record<string, typeof report.temporal_observations>>((acc, obs) => {
      acc[obs.observation_type] = acc[obs.observation_type] ?? []
      acc[obs.observation_type].push(obs)
      return acc
    }, {})
  }, [report])

  const download = (format: 'json' | 'md') => {
    if (!report) return
    let blob: Blob
    if (format === 'json') {
      blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    } else {
      blob = new Blob([toMarkdown(report)], { type: 'text/markdown' })
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `epoch-report-${report.research_id}.${format}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const copySummary = async () => {
    if (!report) return
    await navigator.clipboard.writeText(toMarkdown(report))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  if (error) {
    return (
      <div className="space-y-4">
        <ErrorState message={error} />
        <Link to="/app/history" className="btn-ghost">
          <ArrowLeft size={14} /> Back to history
        </Link>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-24" />
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton h-40" />
          ))}
        </div>
      </div>
    )
  }

  const meta = verdictMeta(report.overall_verdict)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link to="/app/history" className="text-2xs text-slate-400 hover:text-slate-200">
          <ArrowLeft size={12} className="mr-1 inline" /> history
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/app/evidence/${report.research_id}`} className="btn-ghost">
            <Waypoints size={14} /> Evidence graph
          </Link>
          <button onClick={copySummary} className="btn-ghost">
            {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copied' : 'Copy Markdown'}
          </button>
          <button onClick={() => download('json')} className="btn-ghost">
            <FileJson size={14} /> JSON
          </button>
          <button onClick={() => download('md')} className="btn-ghost">
            <Download size={14} /> Markdown
          </button>
          <button onClick={() => window.print()} className="btn-primary">
            <Printer size={14} /> Print / PDF
          </button>
        </div>
      </div>

      {/* verdict header */}
      <Panel className="overflow-hidden p-0">
        <div
          className="border-b px-5 py-4"
          style={{ borderColor: meta.border, background: `linear-gradient(90deg, ${meta.bg}, transparent 70%)` }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="label mb-1.5">Verification report · {report.research_id}</div>
              <h1 className="text-lg font-semibold text-white">{report.title}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <VerdictBadge verdict={report.overall_verdict} size="lg" />
                <span className="chip border-ink-600 text-slate-400">{report.depth} depth</span>
                <span className="chip border-ink-600 text-slate-400">{report.runtime_mode}</span>
                <span className="mono text-2xs text-slate-500">generated {shortDate(report.generated_at)}</span>
              </div>
            </div>
            <div className="grid w-full max-w-xs grid-cols-2 gap-2 sm:w-auto">
              <HeaderStat label="Claims" value={num(report.claims.length)} />
              <HeaderStat label="Sources" value={num(report.sources.length)} />
              <HeaderStat label="Confidence" value={pct(report.confidence)} />
              <HeaderStat label="Runtime" value={ms(Number(report.metrics.pipeline_latency_ms ?? 0))} />
            </div>
          </div>
        </div>
        <div className="px-5 py-4">
          <p className="text-[0.875rem] leading-relaxed text-slate-300">{report.summary}</p>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-2xs text-slate-500">
            <span>Temporal observations: {report.temporal_observations.length}</span>
            <span>Retrieval: {String(report.metrics.search_provider ?? '—')}</span>
            <span>Tokens: {num(Number(report.metrics.tokens ?? 0))}</span>
            <span>Estimated cost: {usd(Number(report.metrics.estimated_cost_usd ?? 0))}</span>
            <span>Calibration: {report.calibration.trained_on} (n={report.calibration.n})</span>
          </div>
        </div>
      </Panel>

      {/* claims */}
      <div className="space-y-3">
        <SectionHeader
          eyebrow="Claim verdicts"
          title={`${report.claims.length} claims verified`}
          description="Each verdict shows the evidence quality measurement, the calibrated confidence, and the reasoning trail."
        />
        {report.claims.map((claim, index) => (
          <ClaimCard key={claim.id} claim={claim} index={index} />
        ))}
      </div>

      {/* temporal */}
      {Object.keys(groupedObservations).length > 0 && (
        <Panel className="p-5">
          <SectionHeader
            eyebrow="What changed"
            title="Temporal intelligence layer"
            description="Publication time, effective time and retrieval time are treated as distinct quantities."
          />
          <div className="grid gap-2 md:grid-cols-2">
            {Object.entries(groupedObservations).map(([type, obs]) => (
              <div key={type} className="rounded-lg border border-ink-700/70 bg-ink-900/40 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <CalendarClock size={13} className="text-violet-300" />
                  <span className="text-[0.8125rem] font-medium text-slate-200">{titleCase(type)}</span>
                  <span className="mono ml-auto text-2xs text-slate-500">{obs.length}</span>
                </div>
                <ul className="space-y-1.5">
                  {obs.slice(0, 3).map((o) => (
                    <li key={o.id} className="text-2xs leading-relaxed text-slate-400">
                      • {o.detail}
                      {o.age_days !== null && <span className="text-slate-600"> ({Math.round(o.age_days)} days old)</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* sources */}
      <Panel className="p-5">
        <SectionHeader
          eyebrow="Provenance"
          title={`${report.sources.length} sources cited`}
          description="Every citation below is the exact URL the evidence was retrieved from, with its retrieval timestamp."
        />
        <ol className="space-y-1.5">
          {report.sources.map((source, i) => (
            <li key={source.id} className="flex flex-wrap items-center gap-2 rounded-md border border-ink-700/60 bg-ink-900/40 px-3 py-2">
              <span className="mono text-2xs text-slate-600">[{i + 1}]</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[0.8125rem] text-slate-200">{source.title}</span>
                <span className="mono truncate text-2xs text-slate-500">{source.domain}</span>
              </span>
              <span className="text-2xs text-slate-500">{source.source_type}</span>
              <span className="mono text-2xs text-slate-500">pub {shortDate(source.published_at)}</span>
              <span className="mono text-2xs text-slate-600">ret {relativeTime(source.retrieved_at)}</span>
              <InlineLink href={source.url}>open</InlineLink>
            </li>
          ))}
        </ol>
      </Panel>

      {/* limitations */}
      <div className="grid gap-4 md:grid-cols-2">
        <Panel className="p-5">
          <SectionHeader eyebrow="Honesty" title="Confidence limitations" />
          {report.limitations.length === 0 ? (
            <p className="text-xs text-slate-500">No limitations were recorded for this investigation.</p>
          ) : (
            <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
              {report.limitations.map((l) => (
                <li key={l} className="flex gap-2">
                  <ShieldAlert size={12} className="mt-0.5 shrink-0 text-verdict-outdated" />
                  {l}
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel className="p-5">
          <SectionHeader eyebrow="Method" title="Calibration" />
          <p className="text-xs leading-relaxed text-slate-400">{report.calibration.note}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-2xs">
            <Meta label="Method" value={report.calibration.method} />
            <Meta label="Trained on" value={report.calibration.trained_on} />
            <Meta label="Samples" value={String(report.calibration.n)} />
            <Meta label="Evidence quality" value={pct(Number(report.metrics.evidence_quality_mean ?? 0))} />
          </div>
          <div className="mt-3">
            <Callout tone="info" title="Two different numbers">
              Evidence quality measures how good the retrieved evidence is. Calibrated confidence estimates how
              likely this verdict is correct. They are computed separately and shown separately.
            </Callout>
          </div>
        </Panel>
      </div>

      <div className="flex items-center justify-between text-2xs text-slate-600 print:hidden">
        <span className="inline-flex items-center gap-1.5">
          <Info size={11} /> Report immutably tied to research id {report.research_id}
        </span>
        <a href="/api/docs" className="hover:text-slate-400">
          API documentation
        </a>
      </div>
    </div>
  )
}

function ClaimCard({ claim, index }: { claim: Claim; index: number }) {
  const [expanded, setExpanded] = useState(index === 0)
  const meta = verdictMeta(claim.verdict?.verdict)
  const supporting = claim.evidence.filter((e) => e.stance === 'supports')
  const contradicting = claim.evidence.filter((e) => e.stance === 'contradicts')
  const superseding = claim.evidence.filter((e) => e.stance === 'supersedes')

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: Math.min(index * 0.03, 0.2) }}
      className="panel overflow-hidden"
    >
      <div className="flex flex-wrap items-start gap-3 border-b border-ink-700/60 px-4 py-3">
        <span className="mono mt-0.5 text-2xs text-slate-600">C{String(index + 1).padStart(2, '0')}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[0.875rem] leading-relaxed text-slate-100">{claim.text}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span className="chip border-ink-600 text-slate-500">{claim.claim_type}</span>
            {claim.versions.slice(0, 2).map((v) => (
              <span key={v} className="chip border-ink-600 text-slate-500">v{v}</span>
            ))}
            {claim.dates.slice(0, 2).map((d) => (
              <span key={d} className="chip border-ink-600 text-slate-500">{d}</span>
            ))}
            <span className="mono text-2xs text-slate-600">checkworthiness {claim.checkworthiness.toFixed(2)}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <VerdictBadge verdict={claim.verdict?.verdict} />
          <span className="mono text-2xs text-slate-500">
            {claim.verdict ? `confidence ${pct(claim.verdict.calibrated_probability)}` : 'no verdict'}
          </span>
        </div>
      </div>

      <div className="grid gap-4 px-4 py-3 md:grid-cols-[1fr_260px]">
        <div className="space-y-2.5">
          <p className="text-xs leading-relaxed text-slate-300">{claim.verdict?.explanation}</p>
          {claim.verdict?.what_changed && (
            <div className="flex items-start gap-2 rounded-md border border-verdict-outdated/25 bg-verdict-outdated/[0.06] px-2.5 py-2">
              <CalendarClock size={12} className="mt-0.5 shrink-0 text-verdict-outdated" />
              <span className="text-2xs leading-relaxed text-amber-100/90">{claim.verdict.what_changed}</span>
            </div>
          )}
          {claim.verdict?.limitations?.length ? (
            <ul className="space-y-1 text-2xs leading-relaxed text-slate-500">
              {claim.verdict.limitations.map((l) => (
                <li key={l}>• {l}</li>
              ))}
            </ul>
          ) : null}

          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-2xs text-cyan-300 hover:text-cyan-200"
          >
            {expanded ? 'Hide evidence' : `Show evidence (${claim.evidence.length})`}
          </button>

          {expanded && (
            <div className="space-y-1.5">
              {claim.evidence.length === 0 && (
                <p className="text-2xs text-slate-500">No evidence relationship survived the relevance filter.</p>
              )}
              {claim.evidence.map((ev) => {
                const stanceMeta = STANCE_META[ev.stance] ?? STANCE_META.context_only
                return (
                  <div key={`${ev.source_id}-${ev.stance}`} className="rounded-md border border-ink-700/60 bg-ink-900/40 p-2.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span
                        className="chip"
                        style={{ color: stanceMeta.color, borderColor: `${stanceMeta.color}44`, background: `${stanceMeta.color}12` }}
                      >
                        {stanceMeta.label}
                      </span>
                      <span className="mono text-2xs text-slate-500">{ev.strength.toFixed(2)}</span>
                      {ev.conflict_kind && <span className="chip border-ink-600 text-slate-500">{ev.conflict_kind}</span>}
                      <span className="mono ml-auto text-2xs text-slate-600">pub {shortDate(ev.published_at)}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="min-w-0 flex-1 truncate text-2xs text-slate-300">{ev.title || ev.domain}</span>
                      <a
                        href={ev.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex shrink-0 items-center gap-1 text-2xs text-cyan-400 hover:text-cyan-300"
                      >
                        {ev.domain} <ExternalLink size={9} />
                      </a>
                    </div>
                    <p className="mt-1 text-2xs leading-relaxed text-slate-500">{ev.rationale}</p>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="space-y-2.5 rounded-lg border border-ink-700/60 bg-ink-900/40 p-3">
          <QualityBar value={claim.verdict?.evidence_quality ?? 0} label="Evidence quality" />
          <QualityBar value={claim.verdict?.calibrated_probability ?? 0} label="Calibrated confidence" />
          <div className="grid grid-cols-3 gap-1.5 text-center text-2xs">
            <Count label="Support" value={supporting.length} color="#34D399" />
            <Count label="Contra" value={contradicting.length} color="#F43F5E" />
            <Count label="Superseded" value={superseding.length} color="#F59E0B" />
          </div>
          {claim.verdict?.components && (
            <div className="space-y-1 border-t border-ink-700/60 pt-2 text-[0.625rem] text-slate-500">
              {Object.entries(claim.verdict.components)
                .filter(([key]) => ['authority', 'relevance', 'temporal', 'corroboration', 'consistency'].includes(key))
                .map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="w-20 shrink-0 capitalize">{key}</span>
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-ink-700">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${Math.min(100, Number(value) * 100)}%`, background: meta.color, opacity: 0.7 }}
                      />
                    </div>
                    <span className="mono w-8 text-right">{Number(value).toFixed(2)}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function Count({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="rounded-md border border-ink-700/60 bg-ink-850/60 px-1.5 py-1">
      <div className="mono text-sm" style={{ color }}>{value}</div>
      <div className="text-[0.5625rem] uppercase tracking-wider text-slate-500">{label}</div>
    </div>
  )
}

function HeaderStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-700/60 bg-ink-900/50 px-2.5 py-1.5">
      <div className="text-[0.5625rem] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mono text-sm text-slate-200">{value}</div>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-700/60 bg-ink-900/40 px-2 py-1.5">
      <div className="text-[0.5625rem] uppercase tracking-wider text-slate-500">{label}</div>
      <div className="mono mt-0.5 truncate text-slate-300">{value}</div>
    </div>
  )
}

function toMarkdown(report: Report): string {
  const lines: string[] = []
  lines.push(`# EPOCH verification report`)
  lines.push('')
  lines.push(`**Claim set:** ${report.title}`)
  lines.push(`**Overall verdict:** ${report.overall_verdict} (confidence ${(report.confidence * 100).toFixed(0)}%)`)
  lines.push(`**Generated:** ${report.generated_at}`)
  lines.push(`**Research id:** ${report.research_id} · mode: ${report.runtime_mode}`)
  lines.push('')
  lines.push(`## Summary`)
  lines.push(report.summary)
  lines.push('')
  lines.push(`## Claims`)
  report.claims.forEach((claim, i) => {
    lines.push(`### ${i + 1}. ${claim.text}`)
    lines.push(`- Verdict: **${claim.verdict?.verdict ?? 'UNVERIFIED'}**`)
    lines.push(`- Evidence quality: ${(claim.verdict?.evidence_quality ?? 0).toFixed(2)} · calibrated confidence: ${(claim.verdict?.calibrated_probability ?? 0).toFixed(2)}`)
    lines.push(`- Supporting: ${claim.verdict?.supporting_count ?? 0} · Contradicting: ${claim.verdict?.contradicting_count ?? 0}`)
    lines.push(`- Explanation: ${claim.verdict?.explanation ?? ''}`)
    if (claim.verdict?.what_changed) lines.push(`- What changed: ${claim.verdict.what_changed}`)
    if (claim.verdict?.limitations?.length) lines.push(`- Limitations: ${claim.verdict.limitations.join('; ')}`)
    claim.evidence.forEach((ev) => {
      lines.push(`  - [${ev.stance}] ${ev.title || ev.domain} — ${ev.url} (published ${ev.published_at ?? 'unknown'}, retrieved ${ev.retrieved_at ?? 'unknown'})`)
    })
    lines.push('')
  })
  if (report.limitations.length) {
    lines.push(`## Limitations`)
    report.limitations.forEach((l) => lines.push(`- ${l}`))
    lines.push('')
  }
  lines.push(`## Calibration`)
  lines.push(report.calibration.note)
  return lines.join('\n')
}
