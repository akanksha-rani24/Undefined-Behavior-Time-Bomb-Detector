import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Editor from '@monaco-editor/react'
import {
  Upload, Play, ChevronDown, X, FileCode, AlertCircle, Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn, EXAMPLE_SOURCES } from '@/lib/utils'
import { api } from '@/lib/api'

const OPT_LEVELS = [
  { id: 'O0', label: '-O0', desc: 'No optimization (baseline)' },
  { id: 'O1', label: '-O1', desc: 'Basic optimizations' },
  { id: 'O2', label: '-O2', desc: 'Standard release (default)' },
  { id: 'O3', label: '-O3', desc: 'Aggressive optimization' },
]

type Phase = 'compiling' | 'analyzing' | 'classifying' | 'done'
const PHASES: Phase[] = ['compiling', 'analyzing', 'classifying', 'done']
const PHASE_LABELS: Record<Phase, string> = {
  compiling:   'Compiling at -O0 and -O2…',
  analyzing:   'Diffing LLVM IR…',
  classifying: 'Classifying UB patterns…',
  done:        'Complete',
}

export default function Scan() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [source, setSource] = useState(EXAMPLE_SOURCES[0].code)
  const [filename, setFilename] = useState('source.c')
  const [language, setLanguage] = useState<'c' | 'cpp'>('c')
  const [optLevels, setOptLevels] = useState<string[]>(['O0', 'O2'])
  const [includeO3, setIncludeO3] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [phase, setPhase] = useState<Phase>('compiling')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [exampleOpen, setExampleOpen] = useState(false)

  function toggleOpt(id: string) {
    if (id === 'O0') return // always required
    setOptLevels(prev =>
      prev.includes(id) ? prev.filter(o => o !== id) : [...prev, id],
    )
  }

  async function runScan() {
    if (!source.trim()) return
    setError(null)
    setLoading(true)
    setPhase('compiling')
    setProgress(10)

    const ticker = setInterval(() => {
      setProgress(p => {
        if (p >= 85) return p
        const phaseIdx = Math.floor((p - 10) / 25)
        if (phaseIdx < PHASES.length - 1) setPhase(PHASES[phaseIdx])
        return p + 3
      })
    }, 400)

    try {
      const { data } = await api.analyze({
        source_code: source,
        filename,
        language,
        opt_levels: optLevels,
        include_o3: includeO3,
      })
      clearInterval(ticker)
      setProgress(100)
      setPhase('done')
      setTimeout(() => navigate(`/results/${data.id}`), 300)
    } catch (err: any) {
      clearInterval(ticker)
      setError(err?.response?.data?.detail || err?.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (!file) return
    handleFile(file)
  }

  function handleFile(file: File) {
    const lang = file.name.endsWith('.cpp') || file.name.endsWith('.cc') ? 'cpp' : 'c'
    setLanguage(lang)
    setFilename(file.name)
    file.text().then(setSource)
  }

  return (
    <div className="h-full flex flex-col p-5 gap-4">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-sm font-bold text-foreground">New Scan</h1>
          <p className="text-xs text-muted-foreground">Paste code, upload a file, or pick an example</p>
        </div>
        <div className="flex gap-2">
          {/* Example picker */}
          <div className="relative">
            <Button variant="outline" size="sm" onClick={() => setExampleOpen(o => !o)}>
              Examples <ChevronDown className="h-3.5 w-3.5" />
            </Button>
            <AnimatePresence>
              {exampleOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute right-0 top-full mt-1 z-50 w-72 rounded-lg border border-border bg-card shadow-xl"
                >
                  {EXAMPLE_SOURCES.map((ex, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setSource(ex.code)
                        setLanguage(ex.lang as any)
                        setFilename(`example${i + 1}.${ex.lang}`)
                        setExampleOpen(false)
                      }}
                      className="w-full text-left px-4 py-3 border-b border-border last:border-0 hover:bg-accent transition-colors"
                    >
                      <div className="text-xs font-medium text-foreground">{ex.name}</div>
                      <div className="text-[10px] text-muted-foreground mt-0.5 uppercase tracking-wide">{ex.lang}</div>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Upload */}
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-3.5 w-3.5" /> Upload
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".c,.cpp,.cc,.cxx,.h,.hpp"
            className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
          />

          {/* Analyze */}
          <Button size="sm" onClick={runScan} disabled={loading || !source.trim()}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {loading ? PHASE_LABELS[phase] : 'Analyze'}
          </Button>
        </div>
      </div>

      {/* Progress bar */}
      <AnimatePresence>
        {loading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Progress value={progress} className="h-1" indicatorClassName="bg-gradient-to-r from-amber-500 to-red-500" />
            <p className="text-[10px] text-muted-foreground mt-1">{PHASE_LABELS[phase]}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3"
          >
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
            <pre className="text-xs text-red-300 whitespace-pre-wrap flex-1 font-mono">{error}</pre>
            <button onClick={() => setError(null)}><X className="h-4 w-4 text-red-400" /></button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main area */}
      <div className="flex-1 grid grid-cols-[1fr_220px] gap-4 overflow-hidden min-h-0">

        {/* Editor */}
        <div
          className={cn(
            'relative rounded-lg border overflow-hidden transition-colors',
            isDragging ? 'border-primary border-pulse' : 'border-border',
          )}
          onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          {isDragging && (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
              <div className="text-center">
                <Upload className="h-8 w-8 text-primary mx-auto mb-2" />
                <p className="text-sm font-medium text-primary">Drop to load file</p>
              </div>
            </div>
          )}

          {/* File header */}
          <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-1.5">
            <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={filename}
              onChange={e => setFilename(e.target.value)}
              className="bg-transparent text-xs text-foreground outline-none flex-1 font-mono"
              placeholder="filename.c"
            />
            <Badge variant="outline" className="text-[9px]">{language.toUpperCase()}</Badge>
          </div>

          <Editor
            height="calc(100% - 34px)"
            language={language === 'cpp' ? 'cpp' : 'c'}
            value={source}
            onChange={v => setSource(v ?? '')}
            theme="vs-dark"
            options={{
              fontSize: 12.5,
              fontFamily: 'JetBrains Mono, Fira Code, monospace',
              fontLigatures: true,
              lineNumbers: 'on',
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              renderWhitespace: 'none',
              padding: { top: 12, bottom: 12 },
              wordWrap: 'off',
              automaticLayout: true,
            }}
          />
        </div>

        {/* Settings panel */}
        <div className="space-y-4 overflow-y-auto">

          {/* Language */}
          <Card>
            <CardContent className="p-4 space-y-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Language</p>
              <div className="grid grid-cols-2 gap-1">
                {(['c', 'cpp'] as const).map(l => (
                  <button
                    key={l}
                    onClick={() => { setLanguage(l); setFilename(f => f.replace(/\.(c|cpp)$/, '.' + l)) }}
                    className={cn(
                      'rounded-md py-1.5 text-xs font-medium transition-all border',
                      language === l
                        ? 'bg-primary/15 text-primary border-primary/30'
                        : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent',
                    )}
                  >
                    {l === 'cpp' ? 'C++' : 'C'}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Optimization levels */}
          <Card>
            <CardContent className="p-4 space-y-2">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Optimization Levels</p>
              <div className="space-y-1.5">
                {OPT_LEVELS.map(opt => {
                  const active = optLevels.includes(opt.id) || opt.id === 'O0'
                  return (
                    <button
                      key={opt.id}
                      onClick={() => toggleOpt(opt.id)}
                      disabled={opt.id === 'O0'}
                      className={cn(
                        'w-full flex items-center gap-2 rounded-md px-2.5 py-2 text-left transition-all border',
                        active
                          ? 'bg-primary/10 border-primary/25 text-primary'
                          : 'border-border text-muted-foreground hover:bg-accent hover:text-foreground',
                        opt.id === 'O0' && 'opacity-60 cursor-default',
                      )}
                    >
                      <div className={cn('h-2 w-2 rounded-full shrink-0 border', active ? 'bg-primary border-primary' : 'border-muted-foreground')} />
                      <div>
                        <div className="text-[11px] font-bold font-mono">{opt.label}</div>
                        <div className="text-[9px] text-muted-foreground">{opt.desc}</div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          {/* Info */}
          <Card className="border-amber-500/20 bg-amber-500/5">
            <CardContent className="p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-amber-500 mb-1.5">How it works</p>
              <ol className="text-[10px] text-muted-foreground space-y-1.5 list-decimal list-inside leading-relaxed">
                <li>Compiles code at each opt level</li>
                <li>Diffs the LLVM IR output</li>
                <li>Detects structural changes (removed branches, nsw flags, const folding)</li>
                <li>Classifies into UB categories</li>
                <li>Reports source-level findings</li>
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
