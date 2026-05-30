import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FlaskConical, Play, CheckCircle2, XCircle, AlertCircle,
  Loader2, TrendingUp, Target, BarChart3,
} from 'lucide-react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { formatPct } from '@/lib/utils'
import type { EvaluationReport, EvalResult } from '@/lib/types'

const BENCHMARK_CASES = [
  { id: 1, name: 'Signed Overflow Check',        ref: 'CWE-190 / GCC PR#30475',     cat: 'signed_integer_overflow',  sev: 'critical', file: '01_signed_overflow.c' },
  { id: 2, name: 'Null Check After Dereference', ref: 'Linux CVE-2011-1078',         cat: 'null_pointer_dereference', sev: 'critical', file: '02_null_deref.c' },
  { id: 3, name: 'Strict Aliasing Type Pun',     ref: 'Quake III / OpenSSL',         cat: 'strict_aliasing_violation',sev: 'high',     file: '03_strict_aliasing.c' },
  { id: 4, name: 'Uninitialized Auth Bypass',    ref: 'CVE-2014-0977 / CWE-457',    cat: 'uninitialized_variable',   sev: 'critical', file: '04_uninitialized.c' },
  { id: 5, name: 'Shift/Parser Overflow',        ref: 'CVE-2016-10190 (FFmpeg)',     cat: 'signed_integer_overflow',  sev: 'critical', file: '05_shift_overflow.c' },
]

export default function Evaluation() {
  const [report, setReport] = useState<EvaluationReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)

  async function runEval() {
    setLoading(true)
    setProgress(0)
    setReport(null)
    const tick = setInterval(() => setProgress(p => Math.min(p + 4, 90)), 500)
    try {
      const { data } = await api.runEvaluation()
      setReport(data)
      setProgress(100)
    } finally {
      clearInterval(tick)
      setLoading(false)
    }
  }

  const metricsData = report
    ? [
        { metric: 'Precision', value: report.precision * 100 },
        { metric: 'Recall',    value: report.recall * 100 },
        { metric: 'F1 Score',  value: report.f1 * 100 },
      ]
    : []

  const resultById = new Map(report?.results.map(r => [r.case.id, r]))

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-bold text-foreground flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-primary" /> Real-World Evaluation
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            5 benchmark cases from CVEs, GCC/Clang bug trackers, and security advisories
          </p>
        </div>
        <Button size="sm" onClick={runEval} disabled={loading}>
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          {loading ? 'Running…' : 'Run Evaluation'}
        </Button>
      </div>

      {loading && (
        <div className="space-y-1">
          <Progress value={progress} className="h-1" indicatorClassName="bg-gradient-to-r from-blue-500 to-purple-500" />
          <p className="text-[10px] text-muted-foreground">Compiling and analyzing {BENCHMARK_CASES.length} test cases…</p>
        </div>
      )}

      {/* Benchmark table (always shown) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Benchmark Dataset</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground w-6">#</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Name</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Reference</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Category</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Severity</th>
                <th className="text-left px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Result</th>
              </tr>
            </thead>
            <tbody>
              {BENCHMARK_CASES.map(bc => {
                const result = resultById.get(bc.id)
                return (
                  <tr key={bc.id} className="border-b border-border/50 hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-3 text-muted-foreground font-mono">{bc.id}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-foreground">{bc.name}</div>
                      <div className="text-[10px] text-muted-foreground font-mono">{bc.file}</div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{bc.ref}</td>
                    <td className="px-4 py-3">
                      <code className="text-[10px] text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded">
                        {bc.cat.replace(/_/g, '_')}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={bc.sev as any}>{bc.sev}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      {!result ? (
                        <span className="text-[10px] text-muted-foreground">—</span>
                      ) : result.true_positive ? (
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                          <span className="text-[10px] text-green-400 font-medium">TP</span>
                          {result.confidence && (
                            <span className="text-[10px] text-muted-foreground">· {formatPct(result.confidence)}</span>
                          )}
                        </div>
                      ) : result.false_positive ? (
                        <div className="flex items-center gap-1.5">
                          <AlertCircle className="h-3.5 w-3.5 text-orange-400" />
                          <span className="text-[10px] text-orange-400 font-medium">FP</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <XCircle className="h-3.5 w-3.5 text-red-400" />
                          <span className="text-[10px] text-red-400 font-medium">FN</span>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Results section */}
      <AnimatePresence>
        {report && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">

            {/* Metric cards */}
            <div className="grid grid-cols-3 gap-4">
              <MetricCard
                icon={<Target className="h-4 w-4 text-blue-400" />}
                label="Precision"
                value={formatPct(report.precision)}
                sub={`${report.true_positives} TP / ${report.true_positives + report.false_positives} detected`}
                color="text-blue-400"
              />
              <MetricCard
                icon={<TrendingUp className="h-4 w-4 text-green-400" />}
                label="Recall"
                value={formatPct(report.recall)}
                sub={`${report.true_positives} TP / ${report.total_cases} total cases`}
                color="text-green-400"
              />
              <MetricCard
                icon={<BarChart3 className="h-4 w-4 text-purple-400" />}
                label="F1 Score"
                value={formatPct(report.f1)}
                sub="Harmonic mean of precision & recall"
                color="text-purple-400"
              />
            </div>

            {/* Confusion matrix + radar */}
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-2"><CardTitle>Confusion Matrix</CardTitle></CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-4 text-center">
                      <div className="text-3xl font-bold text-green-400">{report.true_positives}</div>
                      <div className="text-[10px] text-muted-foreground mt-1">True Positives</div>
                      <div className="text-[9px] text-green-400/70">Correctly detected</div>
                    </div>
                    <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-center">
                      <div className="text-3xl font-bold text-red-400">{report.false_negatives}</div>
                      <div className="text-[10px] text-muted-foreground mt-1">False Negatives</div>
                      <div className="text-[9px] text-red-400/70">Missed detections</div>
                    </div>
                    <div className="rounded-lg bg-orange-500/10 border border-orange-500/20 p-4 text-center">
                      <div className="text-3xl font-bold text-orange-400">{report.false_positives}</div>
                      <div className="text-[10px] text-muted-foreground mt-1">False Positives</div>
                      <div className="text-[9px] text-orange-400/70">Wrong category</div>
                    </div>
                    <div className="rounded-lg bg-secondary p-4 text-center">
                      <div className="text-3xl font-bold text-muted-foreground">
                        {report.total_cases - report.true_positives - report.false_positives - report.false_negatives}
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-1">True Negatives</div>
                      <div className="text-[9px] text-muted-foreground/70">Correctly rejected</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2"><CardTitle>Performance Metrics</CardTitle></CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={metricsData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                      <XAxis dataKey="metric" tick={{ fontSize: 10, fill: '#888' }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#888' }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{ background: '#161616', border: '1px solid #2a2a2a', borderRadius: 6, fontSize: 11 }}
                        formatter={(v: number) => [`${v.toFixed(1)}%`, '']}
                      />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {metricsData.map((_, i) => (
                          <Cell key={i} fill={['#3b82f6', '#22c55e', '#a855f7'][i]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>

            {/* Per-case notes */}
            <Card>
              <CardHeader className="pb-2"><CardTitle>Detection Notes</CardTitle></CardHeader>
              <CardContent className="space-y-2 p-4 pt-0">
                {report.results.map(r => (
                  <div key={r.case.id} className="flex items-start gap-3 text-xs">
                    {r.true_positive ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-400 mt-0.5 shrink-0" />
                    ) : r.false_negative ? (
                      <XCircle className="h-3.5 w-3.5 text-red-400 mt-0.5 shrink-0" />
                    ) : (
                      <AlertCircle className="h-3.5 w-3.5 text-orange-400 mt-0.5 shrink-0" />
                    )}
                    <div>
                      <span className="font-medium text-foreground">{r.case.name}</span>
                      {r.detected_line && <span className="text-muted-foreground"> · line {r.detected_line}</span>}
                      {r.confidence && <span className="text-muted-foreground"> · {formatPct(r.confidence)}</span>}
                      <span className="text-muted-foreground block">{r.notes}</span>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function MetricCard({ icon, label, value, sub, color }: any) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className="rounded-lg bg-secondary p-2">{icon}</div>
        </div>
        <div className={`text-2xl font-bold font-mono ${color}`}>{value}</div>
        <div className="text-xs text-muted-foreground font-medium mt-0.5">{label}</div>
        <div className="text-[10px] text-muted-foreground/70 mt-1">{sub}</div>
      </CardContent>
    </Card>
  )
}
