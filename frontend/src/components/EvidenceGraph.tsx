import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import type { GraphLink, GraphNode } from '../lib/api'
import { STANCE_META, verdictMeta } from '../lib/verdicts'

interface Props {
  nodes: GraphNode[]
  links: GraphLink[]
  selectedId?: string | null
  onSelect: (node: GraphNode | null) => void
}

const COLUMN_X = { claim: 150, source: 560, temporal: 900 }

/**
 * Deterministic, hand-laid-out evidence graph: claims on the left, sources in
 * the middle, temporal events on the right. No force simulation means the same
 * evidence always renders the same way — important for a report you can cite.
 */
export default function EvidenceGraph({ nodes, links, selectedId, onSelect }: Props) {
  const [filters, setFilters] = useState({ supports: true, contradicts: true, supersedes: true, context_only: false, temporal: true })
  const [hovered, setHovered] = useState<string | null>(null)

  const positioned = useMemo(() => {
    const byColumn: Record<string, GraphNode[]> = { claim: [], source: [], temporal: [] }
    nodes.forEach((n) => byColumn[n.kind]?.push(n))
    const map = new Map<string, { x: number; y: number; node: GraphNode }>()
    ;(Object.keys(byColumn) as (keyof typeof COLUMN_X)[]).forEach((kind) => {
      const items = byColumn[kind]
      const gap = kind === 'claim' ? 132 : 88
      const total = Math.max(items.length, 1) * gap
      const offset = Math.max(0, (Math.max(total, 520) - total) / 2)
      items.forEach((node, i) => {
        map.set(node.id, { x: COLUMN_X[kind], y: 70 + offset + i * gap, node })
      })
    })
    return map
  }, [nodes])

  const height = useMemo(() => {
    const ys = Array.from(positioned.values()).map((p) => p.y)
    return Math.max(460, (ys.length ? Math.max(...ys) : 0) + 90)
  }, [positioned])

  const visibleLinks = links.filter((l) => filters[l.stance as keyof typeof filters] ?? false)
  const activeId = hovered ?? selectedId ?? null

  const relatedIds = useMemo(() => {
    if (!activeId) return new Set<string>()
    const set = new Set<string>([activeId])
    visibleLinks.forEach((l) => {
      if (l.source === activeId) set.add(l.target)
      if (l.target === activeId) set.add(l.source)
    })
    return set
  }, [activeId, visibleLinks])

  if (!nodes.length) {
    return (
      <div className="grid h-64 place-items-center rounded-xl border border-dashed border-ink-600 text-xs text-slate-500">
        No graph data yet — run an investigation to populate the evidence graph.
      </div>
    )
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {Object.entries(filters).map(([key, enabled]) => {
          const meta = STANCE_META[key] ?? { label: key, color: '#64748B' }
          return (
            <button
              key={key}
              onClick={() => setFilters((f) => ({ ...f, [key]: !enabled }))}
              className={`chip transition-opacity ${enabled ? '' : 'opacity-40'}`}
              style={{ color: meta.color, borderColor: `${meta.color}44`, background: `${meta.color}12` }}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} />
              {meta.label}
            </button>
          )
        })}
        <span className="ml-auto mono text-2xs text-slate-500">
          {nodes.filter((n) => n.kind === 'claim').length} claims · {nodes.filter((n) => n.kind === 'source').length} sources ·{' '}
          {links.length} edges
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-ink-600/70 bg-ink-950/40">
        <svg width={1000} height={height} className="min-w-[1000px]">
          <defs>
            {Object.entries(STANCE_META).map(([key, meta]) => (
              <marker
                key={key}
                id={`arrow-${key}`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="5"
                markerHeight="5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill={meta.color} opacity="0.75" />
              </marker>
            ))}
          </defs>

          {['Claims', 'Evidence sources', 'Temporal events'].map((label, i) => (
            <text
              key={label}
              x={COLUMN_X[(['claim', 'source', 'temporal'] as const)[i]]}
              y={26}
              textAnchor="middle"
              className="fill-slate-500"
              style={{ fontSize: 10, letterSpacing: '0.16em', textTransform: 'uppercase' }}
            >
              {label}
            </text>
          ))}

          {visibleLinks.map((link) => {
            const a = positioned.get(link.source)
            const b = positioned.get(link.target)
            if (!a || !b) return null
            const dim = activeId ? !(relatedIds.has(link.source) && relatedIds.has(link.target)) : false
            const meta = STANCE_META[link.stance] ?? { color: '#64748B' }
            const midX = (a.x + b.x) / 2
            return (
              <motion.path
                key={link.id}
                d={`M ${a.x + 84} ${a.y} C ${midX} ${a.y}, ${midX} ${b.y}, ${b.x - 76} ${b.y}`}
                fill="none"
                stroke={meta.color}
                strokeWidth={Math.max(0.7, link.strength * 2.4)}
                strokeOpacity={dim ? 0.06 : 0.45}
                strokeDasharray={link.stance === 'context_only' ? '3 4' : undefined}
                markerEnd={`url(#arrow-${link.stance})`}
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: dim ? 0.06 : 0.45 }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            )
          })}

          {Array.from(positioned.values()).map(({ x, y, node }) => {
            const isActive = activeId === node.id
            const dim = activeId ? !relatedIds.has(node.id) : false
            if (node.kind === 'claim') {
              const meta = verdictMeta(node.verdict)
              return (
                <g
                  key={node.id}
                  transform={`translate(${x - 84}, ${y - 26})`}
                  onClick={() => onSelect(node)}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'pointer', opacity: dim ? 0.35 : 1 }}
                >
                  <rect width="168" height="52" rx="7" fill="#0D1320" stroke={isActive ? meta.color : '#1E2A3F'} strokeWidth={isActive ? 1.6 : 1} />
                  <rect width="3" height="52" rx="1.5" fill={meta.color} />
                  <text x="12" y="20" style={{ fontSize: 9.5, letterSpacing: '0.12em' }} className="fill-slate-500">
                    {(node.claim_type ?? 'claim').toUpperCase()}
                  </text>
                  <text x="12" y="36" style={{ fontSize: 10.5 }} className="fill-slate-200">
                    {node.label.length > 26 ? `${node.label.slice(0, 26)}…` : node.label}
                  </text>
                  <text x="12" y="46" style={{ fontSize: 8.5 }} fill={meta.color}>
                    {meta.label.toUpperCase()}
                  </text>
                </g>
              )
            }
            if (node.kind === 'temporal') {
              return (
                <g
                  key={node.id}
                  transform={`translate(${x - 66}, ${y - 18})`}
                  onClick={() => onSelect(node)}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: 'pointer', opacity: dim ? 0.35 : 1 }}
                >
                  <rect width="132" height="36" rx="18" fill="#150F26" stroke={isActive ? '#A78BFA' : '#3B2E63'} />
                  <circle cx="16" cy="18" r="3" fill="#A78BFA" />
                  <text x="30" y="15" style={{ fontSize: 9 }} className="fill-violet-300">
                    {(node.observation_type ?? 'temporal').replace(/_/g, ' ').toUpperCase()}
                  </text>
                  <text x="30" y="27" style={{ fontSize: 8.5 }} className="fill-slate-500">
                    {node.published_at ? node.published_at.slice(0, 10) : 'no date'}
                  </text>
                </g>
              )
            }
            const auth = node.authority ?? 0
            return (
              <g
                key={node.id}
                transform={`translate(${x - 76}, ${y - 22})`}
                onClick={() => onSelect(node)}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: 'pointer', opacity: dim ? 0.35 : 1 }}
              >
                <rect
                  width="152"
                  height="44"
                  rx="6"
                  fill="#0A0F1A"
                  stroke={isActive ? '#22D3EE' : node.is_superseded ? '#F59E0B66' : '#1E2A3F'}
                  strokeWidth={isActive ? 1.5 : 1}
                  strokeDasharray={node.is_superseded ? '3 3' : undefined}
                />
                <text x="10" y="17" style={{ fontSize: 10 }} className="fill-slate-200">
                  {node.label.length > 24 ? `${node.label.slice(0, 24)}…` : node.label}
                </text>
                <text x="10" y="30" style={{ fontSize: 8.5 }} className="fill-slate-500">
                  {(node.domain ?? '').slice(0, 28)}
                </text>
                <text x="10" y="39" style={{ fontSize: 8 }} className="fill-slate-600">
                  {(node.source_type ?? '').toUpperCase()} · auth {auth.toFixed(2)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <p className="mt-2 text-2xs text-slate-600">
        Edge width encodes relationship strength. Select any node to inspect its metadata and relationships.
      </p>
    </div>
  )
}
