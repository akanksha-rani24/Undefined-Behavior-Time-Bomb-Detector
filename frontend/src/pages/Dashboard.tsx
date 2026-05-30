import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Shield, Bomb, AlertTriangle, TrendingUp, ScanLine,
  Clock, ChevronRight, Activity, Zap,
} from 'lucide-react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { cn, formatDate } from '@/lib/utils'
import type { GlobalStats } from '@/lib/types'
import { CATEGORY_COLORS, SEVERITY_CONFIG } from '@/lib/types'

const FADE_UP = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }
const STAGGER = { show: { transition: { staggerChildren: 0.07 } } }

export default function Dashboard() {
  const [stats, setStats] = useState<GlobalStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getStats().then(r => setStats(r.data)).catch(console.error).finally(() => setLoading(false))
  }, [])

  const categoryData = stats
    ? Object.entries(stats.category_distribution).map(([key, val]) => ({
        name: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        value: val,
        color: CATEGORY_COLORS[key] ?? '#888',
      }))
    : []

  const severityData = stats
    ? [
        { name: 'Critical', value: stats.critical_count, color: '#ef4444' },
        { name: 'High',     value: stats.high_count,     color: '#f97316' },
        { name: 'Medium',   value: stats.medium_count,   color: '#eab308' },
        { name: 'Low',      value: stats.low_count,      color: '#22c55e' },
      ]
    : []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Activity className="h-5 w-5 animate-pulse" />
          <span className="text-sm">Loading dashboard…</span>
        </div>
      </div>
    )
  }

  const StatCard = ({
    icon: Icon, label, value, sub, color, delay,
  }: {
    icon: any; label: string; value: string | number; sub?: string; color: string; delay?: number
  }) => (
    <motion.div variants={FADE_UP} transition={{ delay }}>
      <Card className="overflow-hidden">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-muted-foreground font-medium mb-1">{label}</p>
              <p className="text-2xl font-bold text-foreground">{value}</p>
              {sub && <p className="text-[11px] text-muted-foreground mt-1">{sub}</p>}
            </div>
            <div className={cn('flex h-9 w-9 items-center justify-center rounded-lg', color)}>
              <Icon className="h-4.5 w-4.5" />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-foreground flex items-center gap-2">
            <span className="text-xl">💣</span> Dashboard
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            UB Time Bomb Analysis Overview
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/scan">
            <ScanLine className="h-3.5 w-3.5" /> New Scan
          </Link>
        </Button>
      </div>

      {/* Stat cards */}
      <motion.div
        variants={STAGGER}
        initial="hidden"
        animate="show"
        className="grid grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <StatCard icon={ScanLine}      label="Total Scans"     value={stats?.total_scans ?? 0}    color="bg-blue-500/15 text-blue-400"   />
        <StatCard icon={Bomb}          label="UB Bombs Found"  value={stats?.total_bombs ?? 0}    color="bg-amber-500/15 text-amber-400" />
        <StatCard icon={AlertTriangle} label="Critical Issues" value={stats?.critical_count ?? 0} color="bg-red-500/15 text-red-400"     />
        <StatCard icon={TrendingUp}    label="Avg Confidence"  value={stats ? `${(stats.avg_confidence * 100).toFixed(0)}%` : '—'} color="bg-purple-500/15 text-purple-400" />
      </motion.div>

      {/* Charts + recent */}
      <div className="grid grid-cols-3 gap-4">

        {/* Category distribution */}
        <Card className="col-span-1">
          <CardHeader className="pb-2">
            <CardTitle>UB Categories</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            {categoryData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={categoryData} cx="50%" cy="50%" innerRadius={45} outerRadius={72}
                      dataKey="value" paddingAngle={2}>
                      {categoryData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} stroke="transparent" />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: '#161616', border: '1px solid #2a2a2a', borderRadius: 6, fontSize: 11 }}
                      labelStyle={{ color: '#e8e8e8' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-1.5 mt-2">
                  {categoryData.slice(0, 5).map((d, i) => (
                    <div key={i} className="flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <div className="h-2 w-2 rounded-full shrink-0" style={{ background: d.color }} />
                        <span className="text-muted-foreground truncate max-w-[130px]">{d.name}</span>
                      </div>
                      <span className="font-mono font-bold text-foreground">{d.value}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground gap-2">
                <Shield className="h-8 w-8 opacity-30" />
                <span className="text-xs">No data yet — run a scan</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Severity bar chart */}
        <Card className="col-span-1">
          <CardHeader className="pb-2">
            <CardTitle>Severity Distribution</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            {severityData.some(d => d.value > 0) ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={severityData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#888' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#888' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#161616', border: '1px solid #2a2a2a', borderRadius: 6, fontSize: 11 }}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {severityData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground gap-2">
                <Activity className="h-8 w-8 opacity-30" />
                <span className="text-xs">No issues found yet</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent scans */}
        <Card className="col-span-1">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle>Recent Scans</CardTitle>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/results" className="text-[10px] text-muted-foreground hover:text-foreground gap-1">
                  All <ChevronRight className="h-3 w-3" />
                </Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-2 pt-0">
            {(stats?.recent_scans ?? []).length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground gap-2 p-4">
                <Clock className="h-8 w-8 opacity-30" />
                <span className="text-xs text-center">No scans yet.<br />Try the Scan page!</span>
              </div>
            ) : (
              <div className="space-y-0.5">
                {(stats?.recent_scans ?? []).slice(0, 8).map(scan => (
                  <Link
                    key={scan.id}
                    to={`/results/${scan.id}`}
                    className="flex items-center gap-2 px-2 py-2 rounded-md hover:bg-accent transition-colors group"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-foreground truncate">{scan.filename}</div>
                      <div className="text-[10px] text-muted-foreground">{formatDate(scan.created_at)}</div>
                    </div>
                    {scan.summary && (
                      <Badge
                        variant={
                          scan.summary.critical > 0 ? 'critical' :
                          scan.summary.high > 0 ? 'high' :
                          scan.summary.medium > 0 ? 'medium' : 'low'
                        }
                        className="shrink-0"
                      >
                        {scan.summary.total_bombs}
                      </Badge>
                    )}
                    <ChevronRight className="h-3 w-3 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors shrink-0" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick start */}
      {(stats?.total_scans ?? 0) === 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
          <Card className="border-primary/20 bg-gradient-to-br from-amber-500/5 to-red-500/5">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="text-3xl">🚀</div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-1">Get started</h3>
                  <p className="text-xs text-muted-foreground mb-3">
                    Paste or upload C/C++ code to detect UB patterns that work at -O0 but break at -O2.
                    The tool compiles with clang, diffs the LLVM IR, and identifies optimizer-exploited UB.
                  </p>
                  <div className="flex gap-2">
                    <Button asChild size="sm">
                      <Link to="/scan"><Zap className="h-3.5 w-3.5" /> Start Scanning</Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link to="/evaluation"><FlaskConical className="h-3.5 w-3.5" /> Run Evaluation</Link>
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  )
}

function FlaskConical({ className }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2v6l3 3 2 6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2l2-6 3-3V2" /><path d="M6 2h12" />
    </svg>
  )
}
