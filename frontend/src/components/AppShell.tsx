import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity, Command, FileSearch, Gauge, History, Moon, Plus, Search, Sun, Waypoints,
} from 'lucide-react'
import { api, type Health } from '../lib/api'
import { useTheme } from '../lib/theme'
import { ModeBadge } from './ui'

const NAV = [
  { to: '/app', label: 'Dashboard', icon: Gauge, end: true },
  { to: '/app/workspace', label: 'Research workspace', icon: FileSearch },
  { to: '/app/evidence', label: 'Evidence explorer', icon: Waypoints },
  { to: '/app/history', label: 'Research history', icon: History },
  { to: '/app/system', label: 'Observability', icon: Activity },
]

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-8 w-8 place-items-center rounded-lg border border-ink-600 bg-ink-850">
        <svg viewBox="0 0 32 32" className="h-5 w-5">
          <circle cx="16" cy="16" r="9.5" fill="none" stroke="#22D3EE" strokeWidth="1.6" opacity="0.9" />
          <circle cx="16" cy="16" r="3.2" fill="#22D3EE" opacity="0.25" />
          <line x1="16" y1="6.5" x2="16" y2="16" stroke="#8B5CF6" strokeWidth="1.6" />
          <line x1="16" y1="16" x2="22.5" y2="19.5" stroke="#34D399" strokeWidth="1.6" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-tight">
          <div className="text-[0.95rem] font-semibold tracking-[0.14em] text-slate-100">EPOCH</div>
          <div className="text-[0.5625rem] uppercase tracking-[0.22em] text-slate-500">Temporal intelligence</div>
        </div>
      )}
    </div>
  )
}

export default function AppShell() {
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [health, setHealth] = useState<Health | null>(null)
  const [query, setQuery] = useState('')

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [location.pathname])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    navigate(`/app/history?q=${encodeURIComponent(query.trim())}`)
    setQuery('')
  }

  return (
    <div className="flex min-h-screen bg-ink-900 text-slate-200">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-ink-700/70 bg-ink-850/60 px-3.5 py-4 lg:flex">
        <NavLink to="/" className="mb-6 px-1.5">
          <Logo />
        </NavLink>

        <button className="btn-ghost mb-5 w-full justify-start" onClick={() => navigate('/app/workspace')}>
          <Plus size={15} /> New research
        </button>

        <nav className="flex flex-1 flex-col gap-0.5">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[0.8125rem] transition-colors ${
                  isActive
                    ? 'bg-cyan-epoch/10 text-cyan-200'
                    : 'text-slate-400 hover:bg-ink-800 hover:text-slate-200'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={15} className={isActive ? 'text-cyan-300' : 'text-slate-500 group-hover:text-slate-300'} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 space-y-3 border-t border-ink-700/70 pt-3.5">
          <div className="flex items-center justify-between">
            <ModeBadge mode={health?.runtime_mode} />
          </div>
          <div className="space-y-1.5 text-2xs text-slate-500">
            <div className="flex items-center justify-between">
              <span>Database</span>
              <span className={health?.database.ok ? 'text-verdict-verified' : 'text-verdict-contradicted'}>
                {health?.database.ok ? health.database.engine : 'unreachable'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Gateway</span>
              <span className="text-slate-400">{health?.model_routing.gateway ?? '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Version</span>
              <span className="mono text-slate-400">{health?.version ?? '—'}</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-ink-700/70 bg-ink-900/85 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-2.5 sm:px-6">
            <div className="lg:hidden">
              <Logo compact />
            </div>
            <form onSubmit={submit} className="relative flex-1 max-w-xl">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search investigations, claims, domains…"
                className="input py-2 pl-9 pr-16 text-[0.8125rem]"
                aria-label="Global search"
              />
              <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 items-center gap-1 rounded border border-ink-600 bg-ink-800 px-1.5 py-0.5 text-[0.625rem] text-slate-500 sm:flex">
                <Command size={9} /> K
              </kbd>
            </form>
            <div className="ml-auto flex items-center gap-2">
              <div className="hidden lg:block">
                <ModeBadge mode={health?.runtime_mode} />
              </div>
              <button
                onClick={toggle}
                className="btn-ghost h-8 w-8 !px-0"
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              >
                {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
              </button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-ink-700/50 px-3 py-1.5 lg:hidden">
            {NAV.map(({ to, label, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-2.5 py-1 text-xs ${
                    isActive ? 'bg-cyan-epoch/10 text-cyan-200' : 'text-slate-400'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </header>

        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-5 sm:px-6 sm:py-6"
        >
          <Outlet context={{ health }} />
        </motion.main>

        <footer className="border-t border-ink-800 px-4 py-3 text-2xs text-slate-600 sm:px-6">
          <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-2">
            <span>EPOCH AI · Information has a lifespan. EPOCH measures it.</span>
            <span className="mono">
              {health?.runtime_mode ?? '—'} · {health?.model_routing.gateway ?? '—'} · v{health?.version ?? '1.0.0'}
            </span>
          </div>
        </footer>
      </div>
    </div>
  )
}
