import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import Editor, { type Monaco, type OnMount } from '@monaco-editor/react'
import {
  ArrowLeft, Download, Trash2, Clock, Cpu, Layers,
  ChevronRight, AlertCircle, BarChart3, Loader2,
} from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import BombCard from '@/components/BombCard'
import IRDiffViewer from '@/components/IRDiffViewer'
import CFGViewer from '@/components/CFGViewer'
import { api } from '@/lib/api'
import { cn, formatDate, formatDuration, formatPct } from '@/lib/utils'
import type { ScanResult, UBBomb } from '@/lib/types'
import { SEVERITY_CONFIG } from '@/lib/types'

export default function Results() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeBomb, setActiveBomb] = useState<UBBomb | null>(null)
  const [cfgMode, setCfgMode] = useState<'o0' | 'o2'>('o0')

  const monacoRef = useRef<Monaco | null>(null)
  const editorRef = useRef<any>(null)
  const decorations = useRef<string[]>([])

  useEffect(() => {
    if (!id) { setLoading(false); return }
    api.getScan(id)
      .then(r => setScan(r.data))
      .catch(e => setError(e?.response?.data?.detail || 'Scan not found'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!scan) return
    applyDecorations(scan.bombs, activeBomb?.id)
  }, [scan, activeBomb])

  function applyDecorations(bombs: UBBomb[], activeBombId?: number) {
    const editor = editorRef.current
    const monaco = monacoRef.current
    if (!editor || !monaco) return

    const newDecorations: any[] = []

    for (const bomb of bombs) {
      if (bomb.line <= 0) continue
      const isActive = bomb.id === activeBombId
      const sev = bomb.severity

      newDecorations.push({
        range: new monaco.Range(bomb.line, 1, bomb.line, 1),
        options: {
          isWholeLine: true,
          className: cn(
            sev === 'critical' ? 'ub-line-critical' :
            sev === 'high'     ? 'ub-line-high'     : 'ub-line-medium',
            isActive ? '!bg-primary/15' : '',
          ),
          glyphMarginClassName: cn(
            sev === 'critical' ? 'ub-gutter-critical' :
            sev === 'high'     ? 'ub-gutter-high'     : 'ub-gutter-medium',
          ),
          overviewRuler: { color: SEVERITY_CONFIG[sev]?.color ?? '#888', position: 1 },
          minimap: { color: SEVERITY_CONFIG[sev]?.color ?? '#888', position: 1 },
        },
      })
    }

    decorations.current = editor.deltaDecorations(decorations.current, newDecorations)
  }

  function jumpToLine(line: number) {
    const editor = editorRef.current
    const monaco = monacoRef.current
    if (!editor || !monaco || line <= 0) return
    editor.revealLineInCenter(line)
    editor.setPosition({ lineNumber: line, column: 1 })
  }

  async function handleDelete() {
    if (!scan || !confirm('Delete this scan?')) return
    await api.deleteScan(scan.id)
    navigate('/results')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading scan…</span>
        </div>
      </div>
    )
  }

  // List view (no :id)
  if (!id) return <ScanList />

  if (error || !scan) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <AlertCircle className="h-8 w-8 text-red-400" />
        <p className="text-sm text-muted-foreground">{error ?? 'Scan not found'}</p>
        <Button variant="outline" size="sm" asChild>
          <Link to="/results"><ArrowLeft className="h-3.5 w-3.5" /> Back</Link>
        </Button>
      </div>
    )
  }

  const s = scan.summary

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center gap-3 border-b border-border px-5 py-2.5 bg-card/30 shrink-0">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/results"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground truncate">{scan.filename}</span>
            <Badge variant="outline" className="text-[9px]">{scan.language.toUpperCase()}</Badge>
            {scan.compile_error && <Badge variant="critical" className="text-[9px]">Compile Error</Badge>}
          </div>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-0.5">
            <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{formatDate(scan.created_at)}</span>
            <span className="flex items-center gap-1"><Cpu className="h-3 w-3" />{formatDuration(scan.duration_ms)}</span>
            <span className="flex items-center gap-1"><Layers className="h-3 w-3" />{scan.opt_levels.join(', ')}</span>
          </div>
        </div>

        {/* Summary badges */}
        {s && s.total_bombs > 0 && (
          <div className="flex items-center gap-1.5">
            {s.critical > 0 && <Badge variant="critical">{s.critical} critical</Badge>}
            {s.high > 0 && <Badge variant="high">{s.high} high</Badge>}
            {s.medium > 0 && <Badge variant="medium">{s.medium} medium</Badge>}
          </div>
        )}
        {s && s.total_bombs === 0 && (
          <Badge variant="low" className="text-[10px]">✓ No bombs</Badge>
        )}

        {/* Actions */}
        <div className="flex gap-1.5">
          <Button variant="outline" size="sm" onClick={() => api.exportJson(scan.id)}>
            <Download className="h-3.5 w-3.5" /> JSON
          </Button>
          <Button variant="outline" size="sm" onClick={() => api.exportPdf(scan.id)}>
            <Download className="h-3.5 w-3.5" /> PDF
          </Button>
          <Button variant="ghost" size="icon" onClick={handleDelete} className="text-red-400 hover:text-red-300">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Compile error */}
      {scan.compile_error && (
        <div className="mx-5 mt-3 shrink-0 rounded-lg border border-red-500/30 bg-red-500/8 p-3">
          <p className="text-[10px] font-bold uppercase text-red-400 mb-1">Compile Error</p>
          <pre className="text-[11px] font-mono text-red-300 whitespace-pre-wrap">{scan.compile_error}</pre>
        </div>
      )}

      {/* Main split view */}
      <div className="flex-1 grid grid-cols-2 overflow-hidden min-h-0">

        {/* LEFT: Code editor with bomb list below */}
        <div className="flex flex-col border-r border-border overflow-hidden">
          {/* Editor */}
          <div className="flex-1 overflow-hidden">
            <Editor
              height="100%"
              language={scan.language === 'cpp' ? 'cpp' : 'c'}
              value={scan.source_code}
              theme="vs-dark"
              options={{
                readOnly: true,
                fontSize: 12,
                fontFamily: 'JetBrains Mono, Fira Code, monospace',
                fontLigatures: true,
                lineNumbers: 'on',
                glyphMargin: true,
                minimap: { enabled: true, maxColumn: 50 },
                scrollBeyondLastLine: false,
                padding: { top: 8 },
                automaticLayout: true,
                overviewRulerLanes: 3,
              }}
              onMount={(editor, monaco) => {
                editorRef.current = editor
                monacoRef.current = monaco
                if (scan) applyDecorations(scan.bombs, activeBomb?.id)
              }}
            />
          </div>

          {/* Bomb list */}
          <div className="border-t border-border bg-card/30 flex flex-col" style={{ maxHeight: '38%' }}>
            <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                UB Time Bombs ({scan.bombs.length})
              </span>
              {s && <span className="text-[10px] text-muted-foreground">· avg confidence {formatPct(s.confidence_avg)}</span>}
            </div>
            <div className="overflow-y-auto flex-1 p-2 space-y-1.5">
              {scan.bombs.length === 0 ? (
                <div className="flex items-center justify-center h-16 text-xs text-muted-foreground gap-2">
                  ✓ No UB time bombs detected
                </div>
              ) : (
                scan.bombs.map(bomb => (
                  <BombCard
                    key={bomb.id}
                    bomb={bomb}
                    compact
                    isActive={activeBomb?.id === bomb.id}
                    onClick={() => {
                      setActiveBomb(bomb)
                      jumpToLine(bomb.line)
                    }}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: Analysis tabs */}
        <div className="flex flex-col overflow-hidden">
          <Tabs defaultValue="analysis" className="flex flex-col h-full">
            <div className="border-b border-border bg-card/30 px-4 py-2 shrink-0">
              <TabsList>
                <TabsTrigger value="analysis">Analysis</TabsTrigger>
                <TabsTrigger value="ir">IR Diff</TabsTrigger>
                <TabsTrigger value="cfg">CFG</TabsTrigger>
                <TabsTrigger value="functions">Functions</TabsTrigger>
              </TabsList>
            </div>

            {/* Analysis tab */}
            <TabsContent value="analysis" className="flex-1 overflow-y-auto m-0 p-4 space-y-3">
              {activeBomb ? (
                <motion.div key={activeBomb.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
                  <BombCard bomb={activeBomb} />
                </motion.div>
              ) : (
                scan.bombs.map(bomb => (
                  <motion.div key={bomb.id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>
                    <BombCard bomb={bomb} onClick={() => { setActiveBomb(bomb); jumpToLine(bomb.line) }} />
                  </motion.div>
                ))
              )}
              {activeBomb && (
                <Button variant="ghost" size="sm" onClick={() => setActiveBomb(null)} className="w-full">
                  Show all findings
                </Button>
              )}
              {scan.bombs.length === 0 && (
                <div className="flex flex-col items-center justify-center h-48 text-center gap-3 text-muted-foreground">
                  <span className="text-4xl">✅</span>
                  <p className="text-sm font-medium">No UB time bombs detected</p>
                  <p className="text-xs max-w-xs">No patterns found where optimizer assumptions at -O2 differ from -O0 behavior.</p>
                </div>
              )}
            </TabsContent>

            {/* IR Diff tab */}
            <TabsContent value="ir" className="flex-1 overflow-hidden m-0 p-3">
              <IRDiffViewer
                o0_ir={scan.o0_ir}
                o2_ir={scan.o2_ir}
                ir_diff={scan.ir_diff}
                o3_ir={scan.o3_ir || undefined}
              />
            </TabsContent>

            {/* CFG tab */}
            <TabsContent value="cfg" className="flex-1 overflow-hidden m-0 p-3 flex flex-col gap-2">
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-xs text-muted-foreground">CFG View:</span>
                <div className="flex gap-1">
                  {(['o0', 'o2'] as const).map(m => (
                    <button
                      key={m}
                      onClick={() => setCfgMode(m)}
                      className={cn(
                        'text-[11px] px-2.5 py-1 rounded-md border transition-all font-mono',
                        cfgMode === m
                          ? 'bg-primary/15 border-primary/30 text-primary'
                          : 'border-border text-muted-foreground hover:bg-accent',
                      )}
                    >
                      -{m.toUpperCase()}
                    </button>
                  ))}
                </div>
                {scan.cfg && scan.cfg.eliminated_nodes.length > 0 && (
                  <Badge variant="critical" className="text-[9px]">
                    {scan.cfg.eliminated_nodes.length} block(s) eliminated
                  </Badge>
                )}
              </div>
              <div className="flex-1 overflow-hidden">
                {scan.cfg ? (
                  <CFGViewer cfg={scan.cfg} mode={cfgMode} />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    No CFG data available
                  </div>
                )}
              </div>
            </TabsContent>

            {/* Functions tab */}
            <TabsContent value="functions" className="flex-1 overflow-auto m-0 p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-3">
                Function Analysis ({scan.function_diffs.length})
              </p>
              <div className="space-y-2">
                {scan.function_diffs.map((fd, i) => (
                  <Card key={i} className={cn(fd.bombs > 0 ? 'border-amber-500/30' : '')}>
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <code className="text-xs font-mono font-bold text-foreground">{fd.name}()</code>
                        {fd.bombs > 0 && <Badge variant="high" className="text-[9px]">💣 {fd.bombs} bomb{fd.bombs > 1 ? 's' : ''}</Badge>}
                        {fd.changed ? (
                          <Badge variant="medium" className="text-[9px]">changed</Badge>
                        ) : (
                          <Badge variant="outline" className="text-[9px]">unchanged</Badge>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="text-[10px] space-y-0.5">
                          <div className="text-muted-foreground font-bold">-O0</div>
                          <div className="text-foreground">{fd.o0_blocks} blocks, {fd.o0_lines} IR lines</div>
                        </div>
                        <div className="text-[10px] space-y-0.5">
                          <div className="text-muted-foreground font-bold">-O2</div>
                          <div className={cn('text-foreground', fd.o2_blocks < fd.o0_blocks && 'text-orange-400')}>
                            {fd.o2_blocks} blocks, {fd.o2_lines} IR lines
                            {fd.o0_blocks !== fd.o2_blocks && (
                              <span className="ml-1 text-red-400">({fd.o2_blocks - fd.o0_blocks})</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
                {scan.function_diffs.length === 0 && (
                  <p className="text-xs text-muted-foreground">No function data available</p>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}

// ── Scan list (no :id) ─────────────────────────────────────────────────────

function ScanList() {
  const [scans, setScans] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listScans().then(r => setScans(r.data)).finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-bold text-foreground">Scan History</h1>
        <Button size="sm" asChild><Link to="/scan"><BarChart3 className="h-3.5 w-3.5" /> New Scan</Link></Button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /><span className="text-sm">Loading…</span></div>
      ) : scans.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <span className="text-4xl block mb-3">📭</span>
          <p className="text-sm">No scans yet. <Link to="/scan" className="text-primary hover:underline">Run your first scan.</Link></p>
        </div>
      ) : (
        <div className="space-y-2">
          {scans.map(scan => (
            <Link key={scan.id} to={`/results/${scan.id}`}>
              <Card className="hover:border-primary/30 transition-colors cursor-pointer">
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground truncate">{scan.filename}</span>
                      <Badge variant="outline" className="text-[9px]">{scan.language.toUpperCase()}</Badge>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{formatDate(scan.created_at)}</div>
                  </div>
                  {scan.summary && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      {scan.summary.critical > 0 && <Badge variant="critical">{scan.summary.critical} critical</Badge>}
                      {scan.summary.high > 0 && <Badge variant="high">{scan.summary.high} high</Badge>}
                      {scan.summary.total_bombs === 0 && <Badge variant="low">Clean</Badge>}
                    </div>
                  )}
                  <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
