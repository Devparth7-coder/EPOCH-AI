import { useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, Cpu, Database, Gauge, Globe2, RefreshCw, Server, TriangleAlert, Wallet,
} from 'lucide-react'
import { api, type BenchmarkLatest, type Health, type Observability } from '../lib/api'
import { ms, num, pct, relativeTime, usd } from '../lib/format'
import {
  Callout, ErrorState, Metric, ModeBadge, Panel, SectionHeader, StatusDot,
} from '../components/ui'

export default function SystemPage() {
  const [health, setHealth] = useState<Health | null>(null)
  const [obs, setObs] = useState<Observability | null>(null)
  const [bench, setBench] = useState<BenchmarkLatest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = () => {
    setRefreshing(true)
    setError(null)
    Promise.all([api.health(), api.observability(), api.benchmark().catch(() => null)])
      .then(([h, o, b]) => {
        setHealth(h)
        setObs(o)
        setBench(b && (b as unknown as { available?: boolean }).available !== false ? b : null)
      })
      .catch((e) => setError(e.message))
      .finally(() => setRefreshing(false))
  }

  useEffect(load, [])

  if (error) return <ErrorState message={error} onRetry={load} />

  const stageEntries = Object.entries(obs?.stage_latency_ms ?? {}).sort((a, b) => b[1] - a[1])
  const maxStage = Math.max(1, ...stageEntries.map(([, v]) => v))

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="label mb-1">System observability</div>
          <h1 className="text-xl font-semibold text-white">Runtime telemetry</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Model routing, token consumption, latency and failures aggregated from persisted execution logs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {health && <ModeBadge mode={health.runtime_mode} />}
          <button className="btn-ghost" onClick={load} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Model calls"
          value={num(obs?.usage.total_calls)}
          hint={`${num(obs?.usage.provider_failures)} provider failures`}
          icon={<Cpu size={14} className="text-cyan-300" />}
        />
        <Metric
          label="Tokens consumed"
          value={num(obs?.usage.total_tokens)}
          tone="accent"
          hint="prompt + completion, measured per call"
          icon={<Activity size={14} className="text-violet-300" />}
        />
        <Metric
          label="Estimated model cost"
          value={usd(obs?.usage.estimated_cost_usd)}
          hint="computed from configured per-1K token prices"
          icon={<Wallet size={14} className="text-verdict-verified" />}
        />
        <Metric
          label="Search requests"
          value={num(obs?.search.requests)}
          tone={obs && obs.search.failed_requests > 0 ? 'warn' : 'default'}
          hint={`${num(obs?.search.failed_requests)} failed`}
          icon={<Globe2 size={14} className="text-cyan-300" />}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <Panel className="p-5">
          <SectionHeader eyebrow="Routing" title="Model gateway" />
          {!health ? (
            <div className="skeleton h-40" />
          ) : (
            <div className="space-y-2.5 text-xs">
              <Row label="Gateway in use" value={health.model_routing.gateway} tone={health.model_routing.gateway === 'bifrost' ? 'good' : 'default'} />
              <Row label="Primary model" value={health.model_routing.primary} mono />
              <Row label="Fallback model" value={health.model_routing.fallback} mono />
              <Row label="Observed routes" value={(obs?.model_routing.observed_routes ?? ['—']).join(', ')} mono />
              <Row label="Database" value={`${health.database.engine} · ${health.database.ok ? 'ok' : 'error'}`} tone={health.database.ok ? 'good' : 'critical'} />
              <Row label="Python runtime" value={health.python} mono />
              <Row label="Uptime" value={`${Math.round(health.uptime_seconds / 60)} min`} />
            </div>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2">
            {Object.entries(health?.providers ?? {}).map(([name, info]) => (
              <div key={name} className="flex items-center justify-between rounded-md border border-ink-700/60 bg-ink-900/40 px-2.5 py-1.5">
                <span className="text-2xs capitalize text-slate-400">{name}</span>
                <span className={`text-2xs ${info.configured ? 'text-verdict-verified' : 'text-slate-600'}`}>
                  {info.configured ? 'configured' : 'not set'}
                </span>
              </div>
            ))}
          </div>
          {health && health.runtime_mode !== 'live' && (
            <div className="mt-3">
              <Callout tone="warn" title="Deterministic mode active">
                {health.mode_explanation}
              </Callout>
            </div>
          )}
        </Panel>

        <Panel className="p-5">
          <SectionHeader eyebrow="Pipeline" title="Stage latency" description="Mean duration per stage across completed investigations." />
          {!obs ? (
            <div className="skeleton h-40" />
          ) : stageEntries.length === 0 ? (
            <p className="text-xs text-slate-500">No completed investigations yet.</p>
          ) : (
            <div className="space-y-2">
              {stageEntries.map(([stage, value]) => (
                <div key={stage} className="flex items-center gap-2">
                  <span className="w-40 shrink-0 truncate text-2xs capitalize text-slate-400">
                    {stage.replace(/_/g, ' ')}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
                    <div className="h-full rounded-full bg-cyan-epoch/60" style={{ width: `${(value / maxStage) * 100}%` }} />
                  </div>
                  <span className="mono w-16 text-right text-2xs text-slate-500">{ms(value)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 grid grid-cols-2 gap-2 border-t border-ink-700/60 pt-3">
            <Cell icon={<Gauge size={12} />} label="Mean research time" value={ms(obs?.research.mean_execution_ms)} />
            <Cell icon={<TriangleAlert size={12} />} label="Verification failures" value={num(obs?.research.verification_failures)} />
            <Cell icon={<Server size={12} />} label="Completed runs" value={num(obs?.research.by_status?.succeeded)} />
            <Cell icon={<AlertTriangle size={12} />} label="Failed runs" value={num(obs?.research.by_status?.failed)} />
          </div>
        </Panel>
      </div>

      <Panel className="p-5">
        <SectionHeader eyebrow="Execution log" title="Calls by model and route" description="One row per provider/model/route/status combination." />
        {!obs ? (
          <div className="skeleton h-32" />
        ) : obs.by_model.length === 0 ? (
          <p className="text-xs text-slate-500">
            No model calls have been logged yet.{' '}
            {health?.runtime_mode === 'simulated' ? (
              <>
                In <span className="mono text-slate-400">simulated</span> mode the deterministic engines run locally,
                so no provider calls are made and this table stays empty by design. Configure a model gateway or
                Tavily key and switch to live mode to see real calls, tokens, latency and cost here.
              </>
            ) : (
              <>Run an investigation to populate this table.</>
            )}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ink-700/70 text-left text-2xs uppercase tracking-wider text-slate-500">
                  {['Provider', 'Model', 'Route', 'Status', 'Calls', 'Mean latency', 'Prompt', 'Completion', 'Cost', 'Retries'].map((h) => (
                    <th key={h} className="pb-2 pr-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-800">
                {obs.by_model.map((row) => (
                  <tr key={`${row.provider}-${row.model}-${row.route}-${row.status}`}>
                    <td className="py-2 pr-3 text-slate-300">{row.provider}</td>
                    <td className="mono py-2 pr-3 text-slate-400">{row.model}</td>
                    <td className="py-2 pr-3 text-slate-500">{row.route}</td>
                    <td className="py-2 pr-3">
                      <span className={`inline-flex items-center gap-1.5 ${row.status === 'ok' ? 'text-verdict-verified' : 'text-verdict-contradicted'}`}>
                        <StatusDot status={row.status === 'ok' ? 'succeeded' : 'failed'} /> {row.status}
                      </span>
                    </td>
                    <td className="mono py-2 pr-3 text-slate-300">{row.calls}</td>
                    <td className="mono py-2 pr-3 text-slate-400">{ms(row.mean_latency_ms)}</td>
                    <td className="mono py-2 pr-3 text-slate-400">{num(row.prompt_tokens)}</td>
                    <td className="mono py-2 pr-3 text-slate-400">{num(row.completion_tokens)}</td>
                    <td className="mono py-2 pr-3 text-slate-400">{usd(row.cost_usd)}</td>
                    <td className="mono py-2 text-slate-500">{row.retries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-3 space-y-1">
          {(obs?.notes ?? []).map((note) => (
            <p key={note} className="text-2xs text-slate-600">• {note}</p>
          ))}
        </div>
      </Panel>

      {bench && (
        <Panel className="p-5">
          <SectionHeader
            eyebrow="Evaluation"
            title="Latest benchmark run"
            description={`${bench.dataset_size} labelled claims · ${bench.runtime_mode} mode · generated ${relativeTime(bench.generated_at)}`}
          />
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {[
              ['Accuracy', pct(Number(bench.epoch.accuracy), 1)],
              ['Macro F1', Number(bench.epoch.macro_f1).toFixed(3)],
              ['Outdated recall', pct(Number(bench.epoch.outdated_detection_recall), 1)],
              ['Citation correctness', pct(Number(bench.epoch.citation_correctness), 1)],
              ['False verification', pct(Number(bench.epoch.false_verification_rate), 1)],
              ['Baseline accuracy', pct(Number(bench.baseline.accuracy), 1)],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-md border border-ink-700/60 bg-ink-900/40 px-2.5 py-2">
                <div className="text-[0.5625rem] uppercase tracking-wider text-slate-500">{String(label)}</div>
                <div className="mono mt-0.5 text-sm text-slate-200">{String(value)}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-2xs text-slate-600">Run id {bench.run_id}</p>
        </Panel>
      )}
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

function Cell({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md border border-ink-700/60 bg-ink-900/40 px-2.5 py-2">
      <div className="flex items-center gap-1.5 text-[0.5625rem] uppercase tracking-wider text-slate-500">
        {icon} {label}
      </div>
      <div className="mono mt-0.5 text-sm text-slate-200">{value}</div>
    </div>
  )
}
