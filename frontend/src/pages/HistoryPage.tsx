import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, Filter, History as HistoryIcon, RotateCw, Search, X } from 'lucide-react'
import { api, type SessionSummary } from '../lib/api'
import { VERDICT_ORDER, verdictMeta } from '../lib/verdicts'
import { num, relativeTime, shortDate, titleCase } from '../lib/format'
import { EmptyState, ErrorState, Panel, SectionHeader, StatusDot, VerdictBadge } from '../components/ui'

const PAGE_SIZE = 12

export default function HistoryPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [items, setItems] = useState<SessionSummary[] | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const q = params.get('q') ?? ''
  const verdict = params.get('verdict') ?? ''
  const status = params.get('status') ?? ''
  const dateFrom = params.get('date_from') ?? ''
  const dateTo = params.get('date_to') ?? ''
  const page = Number(params.get('page') ?? '0')

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  useEffect(() => {
    setBusy(true)
    setError(null)
    api
      .history({
        q: q || undefined,
        verdict: verdict || undefined,
        status: status || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      .then((res) => {
        setItems(res.items)
        setTotal(res.total)
      })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false))
  }, [q, verdict, status, dateFrom, dateTo, page])

  const distribution = useMemo(() => {
    if (!items) return []
    const counts: Record<string, number> = {}
    items.forEach((i) => {
      if (i.overall_verdict) counts[i.overall_verdict] = (counts[i.overall_verdict] ?? 0) + 1
    })
    return VERDICT_ORDER.map((v) => ({ key: v, count: counts[v] ?? 0 })).filter((d) => d.count > 0)
  }, [items])

  const activeFilters = [q, verdict, status, dateFrom, dateTo].filter(Boolean).length
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label mb-1">Research history</div>
          <h1 className="text-xl font-semibold text-white">Previous investigations</h1>
          <p className="mt-1 text-sm text-slate-400">
            {num(total)} investigations preserved with their claims, evidence and verdicts.
          </p>
        </div>
        <Link to="/app/workspace" className="btn-primary">
          New research <ArrowRight size={14} />
        </Link>
      </div>

      <Panel className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={q}
              onChange={(e) => update('q', e.target.value)}
              placeholder="Search titles and inputs…"
              className="input py-2 pl-9 text-xs"
            />
          </div>
          <select value={verdict} onChange={(e) => update('verdict', e.target.value)} className="input w-auto py-2 text-xs">
            <option value="">All verdicts</option>
            {VERDICT_ORDER.map((v) => (
              <option key={v} value={v}>
                {verdictMeta(v).label}
              </option>
            ))}
          </select>
          <select value={status} onChange={(e) => update('status', e.target.value)} className="input w-auto py-2 text-xs">
            <option value="">Any status</option>
            {['succeeded', 'running', 'queued', 'failed'].map((s) => (
              <option key={s} value={s}>
                {titleCase(s)}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => update('date_from', e.target.value ? `${e.target.value}T00:00:00Z` : '')}
            className="input w-auto py-2 text-xs"
            aria-label="From date"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => update('date_to', e.target.value ? `${e.target.value}T23:59:59Z` : '')}
            className="input w-auto py-2 text-xs"
            aria-label="To date"
          />
          {activeFilters > 0 && (
            <button className="btn-ghost py-2 text-xs" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
              <X size={13} /> Clear ({activeFilters})
            </button>
          )}
          <button className="btn-ghost py-2 text-xs" onClick={() => update('q', q)} disabled={busy}>
            <RotateCw size={13} className={busy ? 'animate-spin' : ''} />
          </button>
        </div>

        {distribution.length > 0 && (
          <div className="mt-3 flex items-center gap-2 border-t border-ink-700/60 pt-3">
            <Filter size={12} className="text-slate-600" />
            <div className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
              {distribution.map((d) => (
                <div
                  key={d.key}
                  style={{
                    width: `${(d.count / distribution.reduce((a, b) => a + b.count, 0)) * 100}%`,
                    background: verdictMeta(d.key).color,
                    opacity: 0.75,
                  }}
                  title={`${verdictMeta(d.key).label}: ${d.count}`}
                />
              ))}
            </div>
            <span className="mono text-2xs text-slate-500">{distribution.length} verdict classes</span>
          </div>
        )}
      </Panel>

      {error && <ErrorState message={error} />}

      <Panel className="overflow-hidden p-0">
        {!items ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton h-12" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={<HistoryIcon size={16} />}
              title="No investigations match these filters"
              description="Adjust the search or run a new investigation to populate the history."
              action={
                <Link to="/app/workspace" className="btn-primary">
                  Start research
                </Link>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ink-700/70 text-left text-2xs uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-2.5 font-medium">Investigation</th>
                  <th className="px-3 py-2.5 font-medium">Verdict</th>
                  <th className="px-3 py-2.5 font-medium">Claims</th>
                  <th className="px-3 py-2.5 font-medium">Status</th>
                  <th className="px-3 py-2.5 font-medium">Created</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-800">
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className="cursor-pointer transition-colors hover:bg-ink-800/40"
                    onClick={() => navigate(item.status === 'succeeded' ? `/app/research/${item.id}` : `/app/workspace/${item.id}`)}
                  >
                    <td className="max-w-[420px] px-4 py-2.5">
                      <div className="truncate text-[0.8125rem] text-slate-200">{item.title}</div>
                      <div className="mono mt-0.5 truncate text-2xs text-slate-600">
                        {item.depth} · {item.input_type} · {item.claim_count} claims · {item.runtime_mode}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      {item.overall_verdict ? <VerdictBadge verdict={item.overall_verdict} size="sm" /> : <span className="text-2xs text-slate-600">—</span>}
                    </td>
                    <td className="mono px-3 py-2.5 text-slate-400">{item.claim_count}</td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5 text-2xs text-slate-400">
                        <StatusDot status={item.status} /> {titleCase(item.status)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="mono text-2xs text-slate-400">{shortDate(item.created_at)}</div>
                      <div className="text-2xs text-slate-600">{relativeTime(item.created_at)}</div>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="text-2xs text-cyan-300">open →</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-2xs text-slate-500">
          <span>
            Showing {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total}
          </span>
          <div className="flex items-center gap-2">
            <button className="btn-ghost py-1.5 text-2xs" disabled={page === 0} onClick={() => update('page', String(page - 1))}>
              Previous
            </button>
            <span className="mono">
              {page + 1} / {pages}
            </span>
            <button
              className="btn-ghost py-1.5 text-2xs"
              disabled={page + 1 >= pages}
              onClick={() => update('page', String(page + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
