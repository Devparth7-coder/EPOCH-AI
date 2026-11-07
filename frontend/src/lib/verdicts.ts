export type VerdictKey =
  | 'VERIFIED' | 'PARTIALLY_OUTDATED' | 'OUTDATED' | 'CONTRADICTED' | 'UNVERIFIED' | 'CONFLICTING'

export const VERDICT_META: Record<
  VerdictKey,
  { label: string; short: string; color: string; bg: string; border: string; description: string }
> = {
  VERIFIED: {
    label: 'Verified', short: 'VER', color: '#34D399', bg: 'rgba(52,211,153,0.12)', border: 'rgba(52,211,153,0.35)',
    description: 'Current, independent, authoritative evidence supports the claim.',
  },
  PARTIALLY_OUTDATED: {
    label: 'Partially outdated', short: 'PAR', color: '#FBBF24', bg: 'rgba(251,191,36,0.12)', border: 'rgba(251,191,36,0.35)',
    description: 'The core holds but a material part has been superseded.',
  },
  OUTDATED: {
    label: 'Outdated', short: 'OUT', color: '#F59E0B', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.35)',
    description: 'Was accurate once; newer evidence shows it has changed.',
  },
  CONTRADICTED: {
    label: 'Contradicted', short: 'CON', color: '#F43F5E', bg: 'rgba(244,63,94,0.12)', border: 'rgba(244,63,94,0.35)',
    description: 'Credible sources state an incompatible value.',
  },
  UNVERIFIED: {
    label: 'Unverified', short: 'UNV', color: '#94A3B8', bg: 'rgba(148,163,184,0.12)', border: 'rgba(148,163,184,0.30)',
    description: 'Evidence is insufficient, so no verdict is asserted.',
  },
  CONFLICTING: {
    label: 'Conflicting', short: 'CFL', color: '#A78BFA', bg: 'rgba(167,139,250,0.12)', border: 'rgba(167,139,250,0.35)',
    description: 'Credible sources disagree and recency does not resolve it.',
  },
}

export const VERDICT_ORDER: VerdictKey[] = [
  'VERIFIED', 'PARTIALLY_OUTDATED', 'OUTDATED', 'CONTRADICTED', 'CONFLICTING', 'UNVERIFIED',
]

export function verdictMeta(verdict?: string | null) {
  if (verdict && verdict in VERDICT_META) return VERDICT_META[verdict as VerdictKey]
  return VERDICT_META.UNVERIFIED
}

export const STANCE_META: Record<string, { label: string; color: string }> = {
  supports: { label: 'Supports', color: '#34D399' },
  contradicts: { label: 'Contradicts', color: '#F43F5E' },
  supersedes: { label: 'Supersedes', color: '#FBBF24' },
  context_only: { label: 'Context', color: '#64748B' },
  temporal: { label: 'Temporal', color: '#8B5CF6' },
}
