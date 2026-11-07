import { motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { AlertTriangle, ArrowUpRight, Info, Loader2 } from 'lucide-react'
import { verdictMeta } from '../lib/verdicts'
import { pct } from '../lib/format'

export function Panel({
  children,
  className = '',
  as = 'div',
  hover = false,
}: {
  children: ReactNode
  className?: string
  as?: 'div' | 'section' | 'article'
  hover?: boolean
}) {
  const Tag = motion[as] as typeof motion.div
  return (
    <Tag
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
      className={`panel ${hover ? 'transition-colors duration-200 hover:border-ink-500/80' : ''} ${className}`}
    >
      {children}
    </Tag>
  )
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow && <div className="label mb-1.5">{eyebrow}</div>}
        <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
        {description && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-400">{description}</p>}
      </div>
      {actions}
    </div>
  )
}

export function Metric({
  label,
  value,
  hint,
  tone = 'default',
  icon,
}: {
  label: string
  value: ReactNode
  hint?: string
  tone?: 'default' | 'good' | 'warn' | 'critical' | 'accent'
  icon?: ReactNode
}) {
  const toneClass = {
    default: 'text-slate-100',
    good: 'text-verdict-verified',
    warn: 'text-verdict-outdated',
    critical: 'text-verdict-contradicted',
    accent: 'text-cyan-300',
  }[tone]
  return (
    <div className="panel-flat px-4 py-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="label">{label}</div>
        {icon}
      </div>
      <div className={`mt-2 text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</div>
      {hint && <div className="mt-1 text-2xs leading-relaxed text-slate-500">{hint}</div>}
    </div>
  )
}

export function VerdictBadge({
  verdict,
  size = 'md',
  showDot = true,
}: {
  verdict?: string | null
  size?: 'sm' | 'md' | 'lg'
  showDot?: boolean
}) {
  const meta = verdictMeta(verdict)
  const sizing = {
    sm: 'px-2 py-0.5 text-[0.625rem]',
    md: 'px-2.5 py-1 text-2xs',
    lg: 'px-3 py-1.5 text-xs',
  }[size]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold uppercase tracking-[0.1em] ${sizing}`}
      style={{ color: meta.color, background: meta.bg, borderColor: meta.border }}
      title={meta.description}
    >
      {showDot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} />}
      {meta.label}
    </span>
  )
}

export function StatusDot({ status }: { status: string }) {
  const map: Record<string, string> = {
    succeeded: 'bg-verdict-verified',
    running: 'bg-cyan-epoch animate-pulseSoft',
    queued: 'bg-slate-500',
    failed: 'bg-verdict-contradicted',
  }
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${map[status] ?? 'bg-slate-500'}`} />
}

export function QualityBar({ value, label }: { value: number; label?: string }) {
  const tone = value >= 0.66 ? '#34D399' : value >= 0.4 ? '#FBBF24' : '#F43F5E'
  return (
    <div className="w-full">
      {label && (
        <div className="mb-1 flex items-center justify-between text-2xs text-slate-500">
          <span>{label}</span>
          <span className="mono text-slate-400">{pct(value)}</span>
        </div>
      )}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700">
        <motion.div
          className="h-full rounded-full"
          style={{ background: tone }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(2, Math.min(100, value * 100))}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
}

export function LoadingPanel({ rows = 3, title }: { rows?: number; title?: string }) {
  return (
    <Panel className="p-5">
      {title && <div className="label mb-3">{title}</div>}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-4" />
        ))}
      </div>
    </Panel>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-ink-600/80 px-6 py-12 text-center">
      <div className="rounded-lg border border-ink-600/80 bg-ink-850 p-2.5 text-slate-500">{icon ?? <Info size={16} />}</div>
      <div>
        <div className="text-sm font-medium text-slate-200">{title}</div>
        {description && <div className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">{description}</div>}
      </div>
      {action}
    </div>
  )
}

export function Callout({
  tone = 'info',
  title,
  children,
}: {
  tone?: 'info' | 'warn' | 'critical' | 'good'
  title?: string
  children: ReactNode
}) {
  const styles = {
    info: { border: 'border-ink-500/60', bg: 'bg-ink-800/70', color: 'text-slate-300', Icon: Info },
    warn: { border: 'border-verdict-outdated/30', bg: 'bg-verdict-outdated/[0.07]', color: 'text-amber-200/90', Icon: AlertTriangle },
    critical: { border: 'border-verdict-contradicted/30', bg: 'bg-verdict-contradicted/[0.07]', color: 'text-rose-200/90', Icon: AlertTriangle },
    good: { border: 'border-verdict-verified/30', bg: 'bg-verdict-verified/[0.07]', color: 'text-emerald-200/90', Icon: Info },
  }[tone]
  const { Icon } = styles
  return (
    <div className={`rounded-lg border ${styles.border} ${styles.bg} px-3.5 py-3`}>
      <div className="flex gap-2.5">
        <Icon size={15} className={`mt-0.5 shrink-0 ${styles.color}`} />
        <div className="min-w-0">
          {title && <div className="text-xs font-semibold text-slate-100">{title}</div>}
          <div className={`text-xs leading-relaxed ${styles.color}`}>{children}</div>
        </div>
      </div>
    </div>
  )
}

export function ModeBadge({ mode }: { mode?: string }) {
  const live = mode === 'live'
  const hybrid = mode === 'hybrid'
  const color = live ? '#34D399' : hybrid ? '#FBBF24' : '#8B5CF6'
  const label = live ? 'Live providers' : hybrid ? 'Hybrid mode' : 'Simulated mode'
  const hint = live
    ? 'Bifrost + Tavily configured. Every number on this screen is a live measurement.'
    : hybrid
      ? 'One provider family is live; the other uses the deterministic engine.'
      : 'No external credentials configured: deterministic engine + bundled evidence corpus. All displayed metrics are real measurements of this mode.'
  return (
    <span
      className="chip"
      title={hint}
      style={{ color, borderColor: `${color}55`, background: `${color}14` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-slate-400">
      <Loader2 size={14} className="animate-spin text-cyan-300" />
      {label}
    </span>
  )
}

export function InlineLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="group inline-flex items-center gap-1 text-cyan-300 underline decoration-cyan-500/30 underline-offset-2 transition-colors hover:text-cyan-200 hover:decoration-cyan-300"
    >
      {children}
      <ArrowUpRight size={12} className="opacity-50 transition-opacity group-hover:opacity-100" />
    </a>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Callout tone="critical" title="Request failed">
      <div className="flex flex-wrap items-center gap-3">
        <span>{message}</span>
        {onRetry && (
          <button className="btn-ghost" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    </Callout>
  )
}
