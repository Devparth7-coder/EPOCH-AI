import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  Activity, ArrowRight, CircleSlash, Clock3, Database, FileSearch, Gauge, Layers, ShieldAlert, Sparkles,
} from 'lucide-react'
import { api, type Analytics, type Health, type SessionSummary } from '../lib/api'
import { VERDICT_ORDER, verdictMeta } from '../lib/verdicts'
import { ms, num, pct, relativeTime, titleCase, usd } from '../lib/format'
import {
  Callout, EmptyState, ErrorState, LoadingPanel, Metric, ModeBadge, Panel, QualityBar, SectionHeader, StatusDot, VerdictBadge,
} from '../components/ui'

export default function Dashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [history, setHistory] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const load = () => {
    setError(null)
    Promise.all([api.analytics(), api.health(), api.history({ limit: 6 })])
      .then(([a, h, hist]) => {
        setAnalytics(a)
        setHealth(h)
        setHistory(hist.items)
      })
      .catch((e) => setError(e.message))
  }

  useEffect(load, [])

  const distribution = useMemo(() => {
    if (!analytics) return []
    return VERDICT_ORDER.map((key) => ({
      key,
      name: verdictMeta(key).label,
      value: analytics.verdict_distribution[key] ?? 0,
      color: verdictMeta(key).color,
    })).filter((d) => d.value > 0)
  }, [analytics])

  const totals = analytics?.totals
  const hasData = (totals?.sessions ?? 0) > 0

  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label mb-1">Intelligence dashboard</div>
          <h1 className="text-xl font-semibold text-white">Workspace overview</h1>
          <p className="mt-1 text-sm text-slate-400">
            Every figure below is aggregated from persisted investigations. Nothing on this screen is simulated.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ModeBadge mode={health?.runtime_mode ?? analytics?.runtime_mode} />
          <Link to="/app/workspace" className="btn-primary">
            New research <ArrowRight size={14} />
          </Link>
        </div>
      </div>

      {/* metrics */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {!analytics ? (
          Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton h-[92px]" />)
        ) : (
          <>
            <Metric
              label="Claims analysed"
              value={num(totals?.claims_analyzed)}
              hint={`${num(totals?.sessions)} investigations · ${num(totals?.completed)} completed`}
              icon={<Layers size={14} className="text-cyan-300" />}
            />
            <Metric
              label="Outdated claims detected"
              value={num(totals?.outdated_detected)}
              tone="warn"
              hint={
                totals?.verdicts_issued
                  ? `${pct((totals.outdated_detected ?? 0) / totals.verdicts_issued)} of all verdicts`
                  : 'No verdicts issued yet'
              }
              icon={<Clock3 size={14} className="text-verdict-outdated" />}
            />
            <Metric
              label="Mean evidence quality"
              value={analytics ? pct(analytics.quality.mean_evidence_quality) : '—'}
              tone={analytics && analytics.quality.mean_evidence_quality >= 0.55 ? 'good' : 'warn'}
              hint="Authority · relevance · recency · corroboration · consistency"
              icon={<ShieldAlert size={14} className="text-verdict-verified" />}
            />
            <Metric
              label="Mean execution time"
              value={ms(analytics?.performance.mean_pipeline_latency_ms)}
              tone="accent"
              hint={`${num(analytics?.performance.tokens_consumed)} tokens · ${usd(analytics?.performance.estimated_cost_usd)} estimated cost`}
              icon={<Gauge size={14} className="text-cyan-300" />}
            />
          </>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        {/* activity */}
        <Panel className="p-5">
          <SectionHeader
            eyebrow="Throughput"
            title="Verification activity"
            description="Investigations and retrieved sources over the last 14 days."
            actions={<span className="mono text-2xs text-slate-500">{analytics?.activity.length ?? 0} days</span>}
          />
          <div className="h-52">
            {!analytics ? (
              <div className="skeleton h-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analytics.activity} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="inv" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#22D3EE" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="ev" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tickFormatter={(v: string) => v.slice(5)}
                    tick={{ fill: '#64748B', fontSize: 10 }}
                    axisLine={{ stroke: '#1E2A3F' }}
                    tickLine={false}
                  />
                  <YAxis tick={{ fill: '#64748B', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: '#0A0F1A', border: '1px solid #1E2A3F', borderRadius: 8, fontSize: 12,
                    }}
                    labelStyle={{ color: '#94A3B8' }}
                  />
                  <Area type="monotone" dataKey="evidence" stroke="#8B5CF6" strokeWidth={1.5} fill="url(#ev)" name="Sources" />
                  <Area type="monotone" dataKey="investigations" stroke="#22D3EE" strokeWidth={1.6} fill="url(#inv)" name="Investigations" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        {/* verdict distribution */}
        <Panel className="p-5">
          <SectionHeader eyebrow="Verdicts" title="Verification distribution" />
          {!analytics ? (
            <div className="skeleton h-52" />
          ) : distribution.length === 0 ? (
            <EmptyState
              icon={<CircleSlash size={16} />}
              title="No verdicts yet"
              description="Run an investigation to populate the verdict distribution."
              action={
                <Link to="/app/workspace" className="btn-primary">
                  Start research
                </Link>
              }
            />
          ) : (
            <div className="flex items-center gap-4">
              <div className="h-40 w-40 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={distribution} dataKey="value" innerRadius={44} outerRadius={66} paddingAngle={2} stroke="none">
                      {distribution.map((entry) => (
                        <Cell key={entry.key} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: '#0A0F1A', border: '1px solid #1E2A3F', borderRadius: 8, fontSize: 12 }}
                      itemStyle={{ color: '#E2E8F0' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="flex-1 space-y-1.5">
                {distribution.map((entry) => (
                  <li key={entry.key} className="flex items-center justify-between gap-2 text-xs">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: entry.color }} />
                      <span className="truncate text-slate-300">{entry.name}</span>
                    </span>
                    <span className="mono text-slate-400">{entry.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analytics && analytics.claim_type_distribution && Object.keys(analytics.claim_type_distribution).length > 0 && (
            <div className="mt-4 border-t border-ink-700/70 pt-3">
              <div className="label mb-2">Claim types</div>
              <div className="h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={Object.entries(analytics.claim_type_distribution).map(([k, v]) => ({ name: titleCase(k), value: v }))}
                    margin={{ top: 0, right: 0, left: -24, bottom: -8 }}
                  >
                    <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 9 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#64748B', fontSize: 9 }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: '#0A0F1A', border: '1px solid #1E2A3F', borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="value" fill="#22D3EE" radius={[3, 3, 0, 0]} opacity={0.55} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        {/* recent activity */}
        <Panel className="p-5">
          <SectionHeader
            eyebrow="Recent"
            title="Verification activity"
            actions={
              <Link to="/app/history" className="text-2xs text-cyan-300 hover:text-cyan-200">
                View all history →
              </Link>
            }
          />
          {!history ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="skeleton h-12" />
              ))}
            </div>
          ) : history.length === 0 ? (
            <EmptyState
              icon={<FileSearch size={16} />}
              title="No investigations yet"
              description="Paste a claim, an AI answer (or a URL) to run the full verification pipeline."
              action={
                <Link to="/app/workspace" className="btn-primary">
                  Start research
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-ink-700/60">
              {history.map((item) => (
                <li key={item.id}>
                  <button
                    onClick={() => navigate(item.status === 'succeeded' ? `/app/research/${item.id}` : `/app/workspace/${item.id}`)}
                    className="flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-ink-800/40"
                  >
                    <StatusDot status={item.status} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[0.8125rem] text-slate-200">{item.title}</div>
                      <div className="mono mt-0.5 text-2xs text-slate-500">
                        {item.claim_count} claims · {item.depth} · {relativeTime(item.created_at)}
                      </div>
                    </div>
                    {item.overall_verdict ? (
                      <VerdictBadge verdict={item.overall_verdict} size="sm" />
                    ) : (
                      <span className="chip border-ink-600 text-slate-500">{titleCase(item.status)}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* system status */}
        <div className="space-y-4">
          <Panel className="p-5">
            <SectionHeader eyebrow="System" title="Runtime status" />
            {!health ? (
              <div className="skeleton h-32" />
            ) : (
              <div className="space-y-2.5 text-xs">
                <Row label="API" value={health.status} tone={health.status === 'healthy' ? 'good' : 'warn'} />
                <Row label="Database" value={`${health.database.engine} · ${health.database.ok ? 'ok' : 'error'}`} tone={health.database.ok ? 'good' : 'critical'} />
                <Row label="Model gateway" value={health.model_routing.gateway} />
                <Row label="Primary model" value={health.model_routing.primary} mono />
                <Row label="Fallback model" value={health.model_routing.fallback} mono />
                <Row label="Runtime mode" value={health.runtime_mode} tone={health.runtime_mode === 'live' ? 'good' : 'warn'} />
                <Row label="Uptime" value={`${Math.round(health.uptime_seconds / 60)} min`} />
              </div>
            )}
            {health && health.runtime_mode !== 'live' && (
              <div className="mt-3">
                <Callout tone="warn" title="Deterministic mode">
                  {health.mode_explanation}
                </Callout>
              </div>
            )}
          </Panel>

          <Panel className="p-5">
            <SectionHeader eyebrow="Evidence" title="Top domains" />
            {!analytics ? (
              <LoadingPanel rows={3} />
            ) : analytics.top_domains.length === 0 ? (
              <p className="text-xs text-slate-500">No sources retrieved yet.</p>
            ) : (
              <ul className="space-y-2">
                {analytics.top_domains.slice(0, 5).map((d) => (
                  <li key={d.domain} className="flex items-center gap-2">
                    <Database size={12} className="shrink-0 text-slate-600" />
                    <span className="min-w-0 flex-1 truncate text-xs text-slate-300">{d.domain}</span>
                    <span className="mono text-2xs text-slate-500">{d.count}</span>
                    <div className="w-16">
                      <QualityBar value={d.mean_authority} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      {!hasData && analytics && (
        <Callout tone="info" title="This workspace is empty">
          <div className="flex flex-wrap items-center gap-2">
            <span>Nothing has been investigated yet.</span>
            <Link to="/app/workspace" className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200">
              Run the first investigation <Sparkles size={12} />
            </Link>
          </div>
        </Callout>
      )}

      <div className="flex items-center justify-between text-2xs text-slate-600">
        <span className="inline-flex items-center gap-1.5">
          <Activity size={11} /> Aggregated {new Date().toLocaleString()}
        </span>
        <span className="mono">
          {analytics ? `${analytics.totals.sources_retrieved} sources · ${analytics.totals.failed} failed runs` : '—'}
        </span>
      </div>
    </div>
  )
}

function Row({ label, value, tone = 'default', mono = false }: { label: string; value: string; tone?: 'default' | 'good' | 'warn' | 'critical'; mono?: boolean }) {
  const toneClass = {
    default: 'text-slate-300', good: 'text-verdict-verified', warn: 'text-verdict-outdated', critical: 'text-verdict-contradicted',
  }[tone]
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className={`${toneClass} ${mono ? 'mono' : ''} truncate text-right`}>{value}</span>
    </div>
  )
}
