import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertOctagon, Braces, Check, Clock3, GitCompareArrows, Loader2, Radar, Scale, ScanSearch,
} from 'lucide-react'
import type { StageState } from '../lib/api'
import { ms } from '../lib/format'

const ICONS: Record<string, typeof Braces> = {
  extracting_claims: Braces,
  planning_research: Radar,
  retrieving_evidence: ScanSearch,
  analyzing_temporal: Clock3,
  detecting_contradictions: GitCompareArrows,
  generating_verdicts: Scale,
}

export default function PipelineTimeline({ stages, compact = false }: { stages: StageState[]; compact?: boolean }) {
  const done = stages.filter((s) => s.status === 'done').length
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="label">Verification pipeline</div>
        <div className="mono text-2xs text-slate-500">
          {done}/{stages.length || 6} stages complete
        </div>
      </div>
      <ol className="relative space-y-0.5">
        {stages.map((stage, i) => {
          const Icon = ICONS[stage.stage] ?? Braces
          const isRunning = stage.status === 'running'
          const isDone = stage.status === 'done'
          const isFailed = stage.status === 'failed'
          return (
            <li key={stage.stage} className="relative flex gap-3 py-2">
              {i < stages.length - 1 && (
                <span
                  className={`absolute left-[13px] top-9 h-[calc(100%-14px)] w-px ${
                    isDone ? 'bg-cyan-epoch/35' : 'bg-ink-600'
                  }`}
                />
              )}
              <span
                className={`relative z-10 grid h-7 w-7 shrink-0 place-items-center rounded-md border ${
                  isFailed
                    ? 'border-verdict-contradicted/40 bg-verdict-contradicted/10 text-verdict-contradicted'
                    : isDone
                      ? 'border-cyan-epoch/40 bg-cyan-epoch/10 text-cyan-300'
                      : isRunning
                        ? 'border-cyan-epoch/50 bg-cyan-epoch/10 text-cyan-200'
                        : 'border-ink-600 bg-ink-850 text-slate-600'
                }`}
              >
                {isDone ? (
                  <Check size={13} />
                ) : isFailed ? (
                  <AlertOctagon size={13} />
                ) : isRunning ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Icon size={13} />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className={`text-[0.8125rem] ${
                      isDone || isRunning ? 'text-slate-200' : 'text-slate-500'
                    } ${isFailed ? 'text-rose-300' : ''}`}
                  >
                    {stage.label}
                  </span>
                  {stage.duration_ms !== null && stage.status !== 'pending' && (
                    <span className="mono shrink-0 text-2xs text-slate-500">{ms(stage.duration_ms)}</span>
                  )}
                </div>
                <AnimatePresence>
                  {stage.detail && !compact && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-0.5 text-2xs leading-relaxed text-slate-500"
                    >
                      {stage.detail}
                    </motion.p>
                  )}
                </AnimatePresence>
                {isRunning && !stage.detail && (
                  <div className="mt-1.5 h-1 w-24 overflow-hidden rounded-full bg-ink-700">
                    <div className="h-full w-1/3 animate-shimmer rounded-full bg-cyan-epoch/60" />
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
