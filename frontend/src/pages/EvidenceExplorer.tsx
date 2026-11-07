import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, CalendarClock, ExternalLink, ShieldAlert, Waypoints } from 'lucide-react'
import { api, type EvidenceBundle, type GraphNode, type SessionSummary } from '../lib/api'
import { STANCE_META, verdictMeta } from '../lib/verdicts'
import { ageInDays, ms, pct, relativeTime, shortDate, titleCase } from '../lib/format'
import EvidenceGraph from '../components/EvidenceGraph'
import {
  Callout, EmptyState, ErrorState, InlineLink, Panel, QualityBar, SectionHeader, VerdictBadge,
} from '../components/ui'

export default function EvidenceExplorer() {
  const { id } = useParams()
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null)
  const [researchId, setResearchId] = useState<string | null>(id ?? null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .history({ status: 'succeeded', limit: 20 })
      .then((res) => {
        setSessions(res.items)
        if (!id && res.items.length > 0) setResearchId(res.items[0].id)
      })
      .catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    if (!researchId) return
    setError(null)
    api
      .evidence(researchId)
      .then((b) => {
        setBundle(b)
        setSelected(null)
      })
      .catch((e) => setError(e.message))
  }, [researchId])

  const sourcesById = useMemo(() => {
    const map = new Map<string, EvidenceBundle['sources'][number]>()
    bundle?.sources.forEach((s) => map.set(s.id, s))
    return map
  }, [bundle])

  const claimById = useMemo(() => {
    const map = new Map<string, EvidenceBundle['claims'][number]>()
    bundle?.claims.forEach((c) => map.set(c.id, c))
    return map
  }, [bundle])

  if (error) return <ErrorState message={error} />

  if (sessions.length === 0 && !bundle) {
    return (
      <EmptyState
        icon={<Waypoints size={16} />}
        title="No evidence to explore yet"
        description="The evidence graph is built from a completed investigation. Run one to see claims, sources and temporal events connected."
        action={
          <Link to="/app/workspace" className="btn-primary">
            Start research <ArrowRight size={14} />
          </Link>
        }
      />
    )
  }

  const selectedSource = selected?.kind === 'source' ? sourcesById.get(selected.id) : undefined
  const selectedClaim = selected?.kind === 'claim' ? claimById.get(selected.id) : undefined
  const relatedRelationships =
    selectedClaim?.evidence ?? (selectedSource ? bundle?.claims.flatMap((c) => c.evidence.filter((e) => e.source_id === selectedSource.id)) ?? [] : [])

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label mb-1">Evidence explorer</div>
          <h1 className="text-xl font-semibold text-white">Evidence graph</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Claims on the left, retrieved sources in the middle, temporal events on the right. Edge colour is the
            classified stance; width is relationship strength.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={researchId ?? ''}
            onChange={(e) => setResearchId(e.target.value)}
            className="input max-w-xs py-1.5 text-xs"
            aria-label="Select investigation"
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title.slice(0, 60)}
              </option>
            ))}
          </select>
          {researchId && (
            <Link to={`/app/research/${researchId}`} className="btn-ghost">
              Open report <ArrowRight size={14} />
            </Link>
          )}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel className="p-4">
          {!bundle ? (
            <div className="skeleton h-96" />
          ) : (
            <EvidenceGraph
              nodes={bundle.graph.nodes}
              links={bundle.graph.links}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          )}
        </Panel>

        <Panel className="p-4">
          <SectionHeader eyebrow="Inspector" title={selected ? titleCase(selected.kind) : 'Nothing selected'} />
          {!selected && (
            <p className="text-xs leading-relaxed text-slate-500">
              Select a claim, a source or a temporal event in the graph to inspect its metadata and relationships.
            </p>
          )}

          {selected?.kind === 'claim' && selectedClaim && (
            <div className="space-y-3">
              <p className="text-[0.8125rem] leading-relaxed text-slate-200">{selectedClaim.text}</p>
              <div className="flex items-center gap-2">
                <VerdictBadge verdict={selectedClaim.verdict} size="sm" />
                <span className="chip border-ink-600 text-slate-400">{selectedClaim.claim_type}</span>
              </div>
              <div className="space-y-2">
                {relatedRelationships.length === 0 ? (
                  <p className="text-xs text-slate-500">No evidence relationships survived the relevance filter.</p>
                ) : (
                  relatedRelationships.map((rel) => {
                    const meta = STANCE_META[rel.stance] ?? STANCE_META.context_only
                    return (
                      <div key={`${rel.source_id}-${rel.stance}`} className="rounded-md border border-ink-700/70 bg-ink-900/40 p-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="chip" style={{ color: meta.color, borderColor: `${meta.color}44` }}>
                            {meta.label}
                          </span>
                          <span className="mono text-2xs text-slate-500">{rel.strength.toFixed(2)}</span>
                        </div>
                        <a
                          href={rel.url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="mt-1.5 block truncate text-2xs text-cyan-400 hover:text-cyan-300"
                        >
                          {rel.domain}
                        </a>
                        <p className="mt-1 text-2xs leading-relaxed text-slate-500">{rel.rationale}</p>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}

          {selected?.kind === 'source' && selectedSource && (
            <div className="space-y-3">
              <div>
                <div className="text-[0.8125rem] font-medium text-slate-100">{selectedSource.title}</div>
                <InlineLink href={selectedSource.url}>{selectedSource.domain}</InlineLink>
              </div>
              <div className="grid grid-cols-2 gap-2 text-2xs">
                <Meta label="Type" value={selectedSource.source_type} />
                <Meta label="Publisher" value={selectedSource.publisher ?? '—'} />
                <Meta label="Published" value={shortDate(selectedSource.published_at)} />
                <Meta label="Retrieved" value={relativeTime(selectedSource.retrieved_at)} />
                <Meta label="Effective" value={shortDate(selectedSource.effective_at)} />
                <Meta label="Version" value={selectedSource.version ?? '—'} />
              </div>
              <div className="space-y-2">
                <QualityBar value={selectedSource.authority_score} label="Source authority" />
                <QualityBar value={selectedSource.freshness_score} label="Freshness weight" />
              </div>
              {ageInDays(selectedSource.published_at) !== null && (
                <p className="text-2xs text-slate-500">
                  Published {ageInDays(selectedSource.published_at)} days before retrieval.
                </p>
              )}
              {selectedSource.injection_flags?.length > 0 && (
                <Callout tone="warn" title="Untrusted content flagged">
                  Prompt-injection signatures detected in this page: {selectedSource.injection_flags.join(', ')}. It was
                  treated strictly as data.
                </Callout>
              )}
              <div className="max-h-40 overflow-auto rounded-md border border-ink-700/70 bg-ink-950/60 p-2.5 text-2xs leading-relaxed text-slate-400">
                {selectedSource.passages?.length
                  ? selectedSource.passages.map((p) => <p key={p.id} className="mb-1.5">{p.text}</p>)
                  : 'No extracted passage retained for this source.'}
              </div>
            </div>
          )}

          {selected?.kind === 'temporal' && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-violet-300">
                <CalendarClock size={14} />
                <span className="text-[0.8125rem] font-medium">
                  {(selected.observation_type ?? '').replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-slate-400">{selected.detail}</p>
              <a
                href={`#`}
                onClick={(e) => e.preventDefault()}
                className="mono text-2xs text-slate-500"
              >
                observed {selected.published_at ? shortDate(selected.published_at) : 'without a publication date'}
              </a>
            </div>
          )}
        </Panel>
      </div>

      {bundle && (
        <Panel className="p-4">
          <SectionHeader
            eyebrow="Sources"
            title={`${bundle.sources.length} retrieved sources`}
            description="Deduplicated by canonical URL. Authority and freshness are computed, not claimed."
          />
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ink-700/70 text-left text-2xs uppercase tracking-wider text-slate-500">
                  <th className="pb-2 pr-3 font-medium">Source</th>
                  <th className="pb-2 pr-3 font-medium">Type</th>
                  <th className="pb-2 pr-3 font-medium">Published</th>
                  <th className="pb-2 pr-3 font-medium">Retrieved</th>
                  <th className="pb-2 pr-3 font-medium">Authority</th>
                  <th className="pb-2 font-medium">Freshness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-800">
                {bundle.sources.map((source) => (
                  <tr key={source.id} className="cursor-pointer hover:bg-ink-800/40" onClick={() => setSelected({
                    id: source.id, kind: 'source', label: source.title,
                  })}>
                    <td className="max-w-[380px] py-2 pr-3">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate text-slate-200">{source.title}</span>
                        <a href={source.url} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()}>
                          <ExternalLink size={10} className="text-cyan-400/70 hover:text-cyan-300" />
                        </a>
                      </div>
                      <div className="mono truncate text-2xs text-slate-600">{source.domain}</div>
                    </td>
                    <td className="py-2 pr-3 text-slate-400">{source.source_type}</td>
                    <td className="mono py-2 pr-3 text-slate-400">{shortDate(source.published_at)}</td>
                    <td className="mono py-2 pr-3 text-slate-500">{relativeTime(source.retrieved_at)}</td>
                    <td className="py-2 pr-3"><div className="w-16"><QualityBar value={source.authority_score} /></div></td>
                    <td className="py-2"><div className="w-16"><QualityBar value={source.freshness_score} /></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {bundle && bundle.temporal_observations.length > 0 && (
        <Panel className="p-4">
          <SectionHeader
            eyebrow="Temporal layer"
            title={`${bundle.temporal_observations.length} temporal observations`}
            description="Publication time, effective time and retrieval time are tracked separately."
          />
          <div className="grid gap-2 md:grid-cols-2">
            {bundle.temporal_observations.slice(0, 8).map((obs) => (
              <div key={obs.id} className="rounded-md border border-ink-700/70 bg-ink-900/40 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="chip border-violet-epoch/40 text-violet-300">
                    {obs.observation_type.replace(/_/g, ' ')}
                  </span>
                  {obs.age_days !== null && <span className="mono text-2xs text-slate-500">{Math.round(obs.age_days)}d old</span>}
                </div>
                <p className="mt-1.5 text-2xs leading-relaxed text-slate-400">{obs.detail}</p>
              </div>
            ))}
          </div>
        </Panel>
      )}
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
