import { useState, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, ScanLine, FileText, FlaskConical,
  Settings, Bomb, ChevronRight, Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

const NAV = [
  { to: '/',           icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/scan',       icon: ScanLine,        label: 'Scan' },
  { to: '/results',    icon: FileText,         label: 'History' },
  { to: '/evaluation', icon: FlaskConical,     label: 'Evaluation' },
  { to: '/settings',   icon: Settings,         label: 'Settings' },
]

export default function Layout() {
  const location = useLocation()
  const [clangOk, setClangOk] = useState<boolean | null>(null)
  const [clangVer, setClangVer] = useState('')

  useEffect(() => {
    api.health().then(r => {
      setClangOk(r.data.clang !== 'unavailable')
      setClangVer(r.data.clang)
    }).catch(() => setClangOk(false))
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-border bg-card/50">
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-border">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-red-600 text-base shadow-lg">
            💣
          </div>
          <div>
            <div className="text-xs font-bold tracking-tight text-foreground">UB Detector</div>
            <div className="text-[10px] text-muted-foreground">Time Bomb Analysis</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-0.5 p-2 pt-3">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-xs font-medium transition-all',
                  isActive
                    ? 'bg-primary/15 text-primary border border-primary/20'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )
              }
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Clang status */}
        <div className="border-t border-border p-3">
          <div className="flex items-center gap-2 rounded-md bg-secondary/50 px-3 py-2">
            <div className={cn(
              'h-1.5 w-1.5 rounded-full',
              clangOk === null ? 'bg-yellow-400 animate-pulse' :
              clangOk ? 'bg-green-400' : 'bg-red-400',
            )} />
            <div className="min-w-0">
              <div className="text-[10px] font-medium text-foreground truncate">
                {clangOk === null ? 'Checking clang…' : clangOk ? 'clang active' : 'clang missing'}
              </div>
              {clangVer && (
                <div className="text-[9px] text-muted-foreground truncate" title={clangVer}>
                  {clangVer.split(' ').slice(0, 4).join(' ')}
                </div>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-12 items-center gap-2 border-b border-border bg-card/30 px-5 shrink-0">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {location.pathname.split('/').filter(Boolean).map((seg, i, arr) => (
              <span key={i} className="flex items-center gap-1.5">
                {i > 0 && <ChevronRight className="h-3 w-3" />}
                <span className={i === arr.length - 1 ? 'text-foreground font-medium capitalize' : 'capitalize'}>
                  {seg}
                </span>
              </span>
            ))}
            {location.pathname === '/' && <span className="text-foreground font-medium">Dashboard</span>}
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">v1.0.0</span>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
              className="h-full"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  )
}
