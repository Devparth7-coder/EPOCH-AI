import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight, Boxes, Braces, Clock3, Database, FileCheck2, GitCompareArrows, Layers,
  Moon, Radar, ScanSearch, Scale, ShieldCheck, Sun, Waypoints,
} from 'lucide-react'
import { api, type BenchmarkLatest, type Health } from '../lib/api'
import { useTheme } from '../lib/theme'
import { VerdictBadge } from '../components/ui'
import { verdictMeta } from '../lib/verdicts'
import { pct, usd } from '../lib/format'
import { Logo } from '../components/AppShell'

const STEPS = [
  { icon: Braces, title: 'Extract claims', body: 'Input is decomposed into atomic, independently checkable claims with entities, dates, numbers and versions.' },
  { icon: Radar, title: 'Plan research', body: 'A planning agent builds targeted, non-redundant searches per claim — version drift and policy claims get different query shapes.' },
  { icon: ScanSearch, title: 'Retrieve evidence', body: 'Live search returns sources that are normalised, deduplicated and timestamped at retrieval time.' },
  { icon: Clock3, title: 'Analyse temporally', body: 'Publication dates, effective dates, versions and support windows are separated from the day you asked the question.' },
  { icon: GitCompareArrows, title: 'Detect contradictions', body: 'Every claim–source pair is classified as supporting, contradicting or unrelated context. Genuine conflicts are preserved.' },
  { icon: Scale, title: 'Decide & explain', body: 'A deterministic verdict engine issues one of six verdicts with a written explanation, or refuses to decide.' },
]

const CAPABILITIES = [
  { icon: Clock3, title: 'Temporal validity', body: 'Claim-type-specific decay, supersession detection and version drift — the difference between what was true and what is true.' },
  { icon: GitCompareArrows, title: 'Contradiction analysis', body: 'Direction-aware supersession, polarity and numeric conflict detection that separates real disagreement from scope differences.' },
  { icon: Waypoints, title: 'Evidence graph', body: 'Claims, sources and temporal events as an inspectable graph with per-edge strength and rationale.' },
  { icon: ShieldCheck, title: 'Calibrated confidence', body: 'Evidence quality (a measurement) is kept strictly separate from calibrated probability (a prediction).' },
  { icon: FileCheck2, title: 'Verifiable citations', body: 'Every citation links to the source it came from, with retrieval timestamps preserved in the report.' },
  { icon: Database, title: 'Full replay', body: 'Original query, claims, evidence, verdicts and model logs are persisted so any report can be re-inspected later.' },
]

export default function Landing() {
  const { theme, toggle } = useTheme()
  const [health, setHealth] = useState<Health | null>(null)
  const [bench, setBench] = useState<BenchmarkLatest | null>(null)
  const [benchAvailable, setBenchAvailable] = useState<boolean | null>(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api
      .benchmark()
      .then((b) => {
        setBenchAvailable(b.available !== false)
        if (b.available !== false) setBench(b)
      })
      .catch(() => setBenchAvailable(false))
  }, [])

  const metrics: { key: keyof BenchmarkLatest['epoch']; label: string; format: (v: number) => string; lowerBetter?: boolean }[] = [
    { key: 'accuracy', label: 'Verdict accuracy', format: (v) => pct(v, 1) },
    { key: 'macro_f1', label: 'Macro F1', format: (v) => v.toFixed(3) },
    { key: 'outdated_detection_recall', label: 'Outdated detection recall', format: (v) => pct(v, 1) },
    { key: 'false_verification_rate', label: 'False verification rate', format: (v) => pct(v, 1), lowerBetter: true },
    { key: 'citation_correctness', label: 'Citation correctness', format: (v) => pct(v, 1) },
  ]

  return (
    <div className="min-h-screen bg-ink-900 text-slate-200">
      {/* ---------------- nav ---------------- */}
      <header className="sticky top-0 z-30 border-b border-ink-800/80 bg-ink-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <Link to="/" aria-label="EPOCH AI home">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-6 text-[0.8125rem] text-slate-400 md:flex">
            <a href="#product" className="transition-colors hover:text-slate-100">Product</a>
            <a href="#how" className="transition-colors hover:text-slate-100">How it works</a>
            <a href="#capabilities" className="transition-colors hover:text-slate-100">Capabilities</a>
            <a href="#benchmark" className="transition-colors hover:text-slate-100">Benchmark</a>
          </nav>
          <div className="flex items-center gap-2">
            <button onClick={toggle} className="btn-ghost h-8 w-8 !px-0" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            </button>
            <Link to="/app" className="btn-primary">
              Open workspace <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </header>

      {/* ---------------- hero ---------------- */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 grid-lines opacity-[0.5]" />
        <div className="pointer-events-none absolute -top-40 left-1/2 h-[420px] w-[820px] -translate-x-1/2 rounded-full bg-cyan-epoch/[0.06] blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl gap-10 px-5 pb-16 pt-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:pb-24 lg:pt-20">
          <div>
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="mb-5 inline-flex items-center gap-2 rounded-full border border-ink-600/80 bg-ink-850/80 px-3 py-1 text-2xs uppercase tracking-[0.18em] text-slate-400"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-epoch" />
              Temporal intelligence &amp; evidence verification
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.06 }}
              className="text-balance text-4xl font-semibold leading-[1.08] tracking-tight text-white sm:text-5xl lg:text-[3.4rem]"
            >
              Know What Is True.
              <br />
              <span className="text-cyan-300">Know When It Changed.</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.12 }}
              className="mt-5 max-w-xl text-[0.9375rem] leading-relaxed text-slate-400"
            >
              An intelligence engine that investigates information, detects outdated claims, and verifies facts
              against current evidence — then shows you exactly which sources say so, and when they said it.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.18 }}
              className="mt-7 flex flex-wrap items-center gap-3"
            >
              <Link to="/app/workspace" className="btn-solid px-5 py-2.5">
                Start research <ArrowRight size={15} />
              </Link>
              <Link to="/app" className="btn-ghost px-5 py-2.5">
                Explore intelligence
              </Link>
            </motion.div>
            <div className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 text-2xs text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck size={12} className="text-verdict-verified" />
                Never verifies without sufficient evidence
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Layers size={12} className="text-cyan-300" />
                Six verdicts, three of them honest about uncertainty
              </span>
            </div>
          </div>

          <TemporalVisualisation />
        </div>
      </section>

      {/* ---------------- problem ---------------- */}
      <section id="product" className="border-y border-ink-800 bg-ink-850/40">
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-14 md:grid-cols-[0.9fr_1.1fr] md:items-center">
          <div>
            <div className="label mb-2">The problem</div>
            <h2 className="text-2xl font-semibold text-white">
              Most answers are accurate for a moment you cannot identify.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              Models, docs and dashboards all answer with the same confidence whether the fact is from this morning
              or from 2019. EPOCH treats every assertion as a claim with a lifespan: it looks for what was true,
              what is true now, and what changed in between.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { title: 'Stale by default', body: 'Answers built on undated knowledge drift silently out of date.' },
              { title: 'Confidently wrong', body: 'A wrong value and a right value are returned in the same tone.' },
              { title: 'Uncheckable', body: 'Citations often point at pages that never said what was claimed.' },
            ].map((item) => (
              <div key={item.title} className="panel-flat p-4">
                <div className="text-[0.8125rem] font-medium text-slate-100">{item.title}</div>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- how it works ---------------- */}
      <section id="how" className="mx-auto max-w-6xl px-5 py-16">
        <div className="mb-9 max-w-2xl">
          <div className="label mb-2">How EPOCH works</div>
          <h2 className="text-2xl font-semibold text-white">A pipeline, not a prompt.</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Six observable stages run for every investigation. Each stage persists its own state, timing and
            metrics, so progress shown in the workspace is execution, never an animation.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.35, delay: i * 0.04 }}
              className="panel group relative p-4 transition-colors hover:border-ink-500/80"
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="grid h-8 w-8 place-items-center rounded-md border border-ink-600 bg-ink-850 text-cyan-300">
                  <step.icon size={15} />
                </div>
                <span className="mono text-2xs text-slate-600">0{i + 1}</span>
              </div>
              <div className="text-[0.875rem] font-medium text-slate-100">{step.title}</div>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{step.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ---------------- capabilities ---------------- */}
      <section id="capabilities" className="border-y border-ink-800 bg-ink-850/40">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <div className="mb-9 flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-2xl">
              <div className="label mb-2">Core capabilities</div>
              <h2 className="text-2xl font-semibold text-white">Built like an intelligence system.</h2>
            </div>
            <Link to="/app" className="btn-ghost">
              See it running <ArrowRight size={14} />
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((cap) => (
              <div key={cap.title} className="panel-flat p-4">
                <cap.icon size={16} className="mb-2.5 text-violet-300" />
                <div className="text-[0.875rem] font-medium text-slate-100">{cap.title}</div>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{cap.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------------- example results ---------------- */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-3">
          <div className="max-w-2xl">
            <div className="label mb-2">Example verification results</div>
            <h2 className="text-2xl font-semibold text-white">Real verdicts from the labelled benchmark.</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">
              These are measured outputs of the current engine on labelled claims — not mock-ups. Each verdict
              ships with the evidence it used.
            </p>
          </div>
          {benchAvailable === false && (
            <span className="chip border-ink-600 text-slate-400">No benchmark artefact yet</span>
          )}
        </div>

        {benchAvailable === false ? (
          <div className="rounded-xl border border-dashed border-ink-600 p-8 text-center text-sm text-slate-500">
            Run <code className="mono rounded bg-ink-800 px-1.5 py-0.5 text-cyan-300">python benchmark/run_benchmark.py</code>{' '}
            in the backend to generate measured examples.
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-3">
            {(bench?.examples ?? []).slice(0, 3).map((ex) => {
              const meta = verdictMeta(ex.predicted)
              return (
                <div key={ex.id} className="panel p-4">
                  <div className="mb-2.5 flex items-center justify-between">
                    <VerdictBadge verdict={ex.predicted} size="sm" />
                    <span className="mono text-2xs text-slate-500">quality {ex.evidence_quality.toFixed(2)}</span>
                  </div>
                  <p className="text-[0.8125rem] leading-relaxed text-slate-200">{ex.claim}</p>
                  <p className="mt-2 text-xs leading-relaxed text-slate-500">{ex.explanation}</p>
                  <div className="mt-3 space-y-1 border-t border-ink-700/70 pt-2.5">
                    {ex.citations.slice(0, 2).map((url) => (
                      <a
                        key={url}
                        href={url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="block truncate text-2xs text-cyan-400/80 hover:text-cyan-300"
                      >
                        {url.replace(/^https?:\/\//, '')}
                      </a>
                    ))}
                  </div>
                  <div className="mt-2 flex items-center gap-1.5 text-2xs" style={{ color: meta.color }}>
                    <span className="h-1 w-1 rounded-full" style={{ background: meta.color }} />
                    {meta.description}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ---------------- benchmark ---------------- */}
      <section id="benchmark" className="border-y border-ink-800 bg-ink-850/40">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-2xl">
              <div className="label mb-2">Measured performance</div>
              <h2 className="text-2xl font-semibold text-white">
                {bench ? `${bench.dataset_size} labelled claims. Measured, not promised.` : 'Benchmark'}
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                EPOCH is compared against a single-pass LLM-only baseline that has no temporal or contradiction
                reasoning. Numbers below are computed from the saved run artefact.
              </p>
            </div>
            {bench && (
              <div className="text-right text-2xs text-slate-500">
                <div className="mono">run {bench.run_id}</div>
                <div className="mt-0.5">
                  mode: {bench.runtime_mode} · retrieval: {bench.search_provider}
                </div>
              </div>
            )}
          </div>

          {!bench ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="skeleton h-24" />
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-ink-600/70">
              <table className="w-full text-sm">
                <thead className="bg-ink-800/80 text-left">
                  <tr className="text-2xs uppercase tracking-[0.12em] text-slate-500">
                    <th className="px-4 py-2.5 font-medium">Metric</th>
                    <th className="px-4 py-2.5 font-medium">EPOCH pipeline</th>
                    <th className="px-4 py-2.5 font-medium">LLM-only baseline</th>
                    <th className="px-4 py-2.5 font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-700/60 bg-ink-900/40">
                  {metrics.map((row) => {
                    const epochValue = Number(bench.epoch[row.key] ?? 0)
                    const baseValue = Number(bench.baseline[row.key] ?? 0)
                    const delta = epochValue - baseValue
                    const better = row.lowerBetter ? delta < 0 : delta > 0
                    return (
                      <tr key={String(row.key)} className="text-slate-300">
                        <td className="px-4 py-2.5 text-[0.8125rem]">{row.label}</td>
                        <td className="px-4 py-2.5 mono text-cyan-200">{row.format(epochValue)}</td>
                        <td className="px-4 py-2.5 mono text-slate-400">{row.format(baseValue)}</td>
                        <td className={`px-4 py-2.5 mono ${better ? 'text-verdict-verified' : 'text-slate-500'}`}>
                          {delta > 0 ? '+' : ''}
                          {row.key === 'mean_latency_ms' || row.key === 'cost_per_investigation_usd'
                            ? delta.toFixed(3)
                            : row.format(delta)}
                        </td>
                      </tr>
                    )
                  })}
                  <tr className="text-slate-400">
                    <td className="px-4 py-2.5 text-[0.8125rem]">Cost per investigation</td>
                    <td className="px-4 py-2.5 mono text-cyan-200">{usd(Number(bench?.epoch.cost_per_investigation_usd ?? 0))}</td>
                    <td className="px-4 py-2.5 mono">—</td>
                    <td className="px-4 py-2.5 mono text-slate-600">n/a</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="panel-flat p-4">
              <div className="label mb-1.5">How to read this</div>
              <ul className="space-y-1.5 text-xs leading-relaxed text-slate-500">
                <li>• Retrieval is deterministic in benchmark mode, so the score measures reasoning, not web noise.</li>
                <li>• Experiment targets are not shown as results; only computed values appear here.</li>
                <li>• Calibration is fitted on this benchmark, so its Brier score is optimistic.</li>
              </ul>
            </div>
            <div className="panel-flat p-4">
              <div className="label mb-1.5">Category coverage</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(bench?.per_class ?? {}).map(([verdict, stats]) => (
                  <span
                    key={verdict}
                    className="chip border-ink-600"
                    style={{ color: verdictMeta(verdict).color }}
                    title={`precision ${stats.precision} / recall ${stats.recall}`}
                  >
                    {verdictMeta(verdict).label} · n={stats.support}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- integrations ---------------- */}
      <section className="mx-auto max-w-6xl px-5 py-16">
        <div className="mb-8 max-w-2xl">
          <div className="label mb-2">Technology</div>
          <h2 className="text-2xl font-semibold text-white">Integrations you can inspect.</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Status is read live from the backend health endpoint — a provider shows “live” only when a server-side
            credential is actually configured.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { name: 'Bifrost by Maxim AI', role: 'Model gateway', key: 'bifrost' },
            { name: 'OpenAI', role: 'Reasoning models', key: 'openai' },
            { name: 'Google Gemini', role: 'Reasoning models', key: 'gemini' },
            { name: 'Tavily', role: 'Live web research', key: 'tavily' },
          ].map((item) => {
            const configured = health?.providers?.[item.key]?.configured
            return (
              <div key={item.key} className="panel-flat flex items-start justify-between gap-2 p-3.5">
                <div>
                  <div className="text-[0.8125rem] font-medium text-slate-100">{item.name}</div>
                  <div className="mt-0.5 text-2xs text-slate-500">{item.role}</div>
                </div>
                <span
                  className="chip shrink-0"
                  style={{
                    color: configured ? '#34D399' : '#94A3B8',
                    borderColor: configured ? '#34D39955' : '#94A3B833',
                    background: configured ? '#34D39914' : '#94A3B814',
                  }}
                >
                  {configured ? 'live' : 'not set'}
                </span>
              </div>
            )
          })}
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5 text-2xs text-slate-500">
          {['FastAPI', 'Pydantic', 'SQLAlchemy', 'PostgreSQL', 'pgvector-ready', 'React 18', 'Vite', 'TypeScript',
            'Tailwind CSS', 'Framer Motion', 'Recharts', 'Lucide', 'Docker', 'Render', 'Vercel', 'Neon'].map((t) => (
            <span key={t} className="rounded-md border border-ink-600/70 bg-ink-850/60 px-2 py-1">
              {t}
            </span>
          ))}
        </div>
      </section>

      {/* ---------------- cta ---------------- */}
      <section className="border-t border-ink-800">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <div className="panel relative overflow-hidden p-8 sm:p-10">
            <div className="pointer-events-none absolute inset-0 grid-lines opacity-40" />
            <div className="relative flex flex-wrap items-center justify-between gap-6">
              <div className="max-w-xl">
                <h2 className="text-2xl font-semibold text-white">Information has a lifespan. EPOCH measures it.</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">
                  Paste a claim, an AI answer or a document. Get verdicts you can defend, with the sources behind
                  them and the dates that changed them.
                </p>
              </div>
              <div className="flex gap-2">
                <Link to="/app/workspace" className="btn-solid px-5 py-2.5">
                  Start research <ArrowRight size={15} />
                </Link>
                <Link to="/app/system" className="btn-ghost px-5 py-2.5">
                  System status
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-ink-800 bg-ink-950/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-2xs text-slate-600">
          <div className="flex items-center gap-2">
            <Boxes size={12} />
            EPOCH AI · Temporal intelligence &amp; evidence verification engine
          </div>
          <div className="flex items-center gap-4">
            <Link to="/app" className="hover:text-slate-400">Workspace</Link>
            <Link to="/app/history" className="hover:text-slate-400">History</Link>
            <a href="/api/docs" className="hover:text-slate-400">API docs</a>
            <span className="mono">{health?.runtime_mode ?? '—'} mode</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Hero visualisation: claims decaying along a timeline.                */
/* ------------------------------------------------------------------ */
function TemporalVisualisation() {
  const rows = [
    { label: 'Python 3.7 is the newest release', verdict: 'OUTDATED', age: '2,400 d' },
    { label: 'React 19 shipped as stable', verdict: 'VERIFIED', age: '340 d' },
    { label: 'Node.js 18 is the Active LTS', verdict: 'PARTIALLY_OUTDATED', age: '560 d' },
    { label: 'EU AI Act entered into force', verdict: 'VERIFIED', age: '820 d' },
    { label: 'TLS 1.2 is the newest TLS version', verdict: 'CONTRADICTED', age: '5,900 d' },
  ]
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.15 }}
      className="panel relative overflow-hidden p-4"
    >
      <div className="pointer-events-none absolute inset-0 grid-lines opacity-40" />
      <div className="relative flex items-center justify-between pb-3">
        <div className="label">Temporal validity scan</div>
        <span className="mono text-2xs text-slate-500">publication → retrieval</span>
      </div>

      <div className="relative space-y-2">
        {rows.map((row, i) => {
          const meta = verdictMeta(row.verdict)
          return (
            <motion.div
              key={row.label}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: 0.3 + i * 0.09 }}
              className="flex items-center gap-3 rounded-md border border-ink-700/70 bg-ink-900/70 px-2.5 py-2"
            >
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: meta.color }} />
              <span className="min-w-0 flex-1 truncate text-[0.75rem] text-slate-300">{row.label}</span>
              <span className="mono hidden text-2xs text-slate-500 sm:block">{row.age}</span>
              <span className="text-[0.625rem] font-semibold uppercase tracking-wider" style={{ color: meta.color }}>
                {meta.short}
              </span>
              <div className="h-1 w-14 overflow-hidden rounded-full bg-ink-700">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: meta.color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${100 - Math.min(88, parseInt(row.age.replace(/[^\d]/g, ''), 10) / 60)}%` }}
                  transition={{ duration: 0.9, delay: 0.45 + i * 0.09 }}
                />
              </div>
            </motion.div>
          )
        })}
      </div>

      <div className="relative mt-3 flex items-center justify-between border-t border-ink-700/70 pt-2.5">
        <div className="flex items-center gap-1.5 text-2xs text-slate-500">
          <Clock3 size={11} />
          decay weighted by claim type
        </div>
        <div className="flex items-center gap-1">
          {['VERIFIED', 'PARTIALLY_OUTDATED', 'OUTDATED', 'CONTRADICTED'].map((v) => (
            <span key={v} className="h-1 w-6 rounded-full" style={{ background: verdictMeta(v).color, opacity: 0.6 }} />
          ))}
        </div>
      </div>
    </motion.div>
  )
}
