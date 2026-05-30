import { useState } from 'react'
import { motion } from 'framer-motion'
import { Settings as SettingsIcon, Save, RotateCcw, Terminal, Cpu, Download, Info } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const DEFAULTS = {
  clangPath: 'clang',
  clangppPath: 'clang++',
  defaultOpts: ['O0', 'O2'],
  timeout: '60',
  exportFormat: 'json',
}

export default function Settings() {
  const [values, setValues] = useState(DEFAULTS)
  const [saved, setSaved] = useState(false)

  function set(k: string, v: any) {
    setValues(p => ({ ...p, [k]: v }))
    setSaved(false)
  }

  function save() {
    // In production this would POST to /api/v1/settings
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  function reset() {
    setValues(DEFAULTS)
    setSaved(false)
  }

  const Field = ({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) => (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-border/50 last:border-0">
      <div className="flex-1">
        <div className="text-xs font-medium text-foreground">{label}</div>
        {desc && <div className="text-[10px] text-muted-foreground mt-0.5">{desc}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )

  const Input = ({ value, onChange, placeholder }: any) => (
    <input
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-52 rounded-md border border-border bg-secondary px-3 py-1.5 text-xs text-foreground font-mono outline-none focus:border-primary transition-colors"
    />
  )

  return (
    <div className="p-6 max-w-2xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-sm font-bold text-foreground flex items-center gap-2">
            <SettingsIcon className="h-4 w-4" /> Settings
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">Configure compiler, analysis, and export preferences</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={reset}>
            <RotateCcw className="h-3.5 w-3.5" /> Reset
          </Button>
          <Button size="sm" onClick={save}>
            <Save className="h-3.5 w-3.5" />
            {saved ? 'Saved!' : 'Save'}
          </Button>
        </div>
      </div>

      {/* Compiler */}
      <Card>
        <CardHeader className="pb-0">
          <CardTitle className="flex items-center gap-2 text-xs">
            <Terminal className="h-3.5 w-3.5 text-primary" /> Compiler Configuration
          </CardTitle>
          <CardDescription>Paths to clang/clang++ binaries</CardDescription>
        </CardHeader>
        <CardContent className="p-5 pt-3">
          <Field label="clang path" desc="Path to clang binary (for C compilation)">
            <Input value={values.clangPath} onChange={(v: string) => set('clangPath', v)} placeholder="clang" />
          </Field>
          <Field label="clang++ path" desc="Path to clang++ binary (for C++ compilation)">
            <Input value={values.clangppPath} onChange={(v: string) => set('clangppPath', v)} placeholder="clang++" />
          </Field>
          <Field label="Compile timeout" desc="Maximum seconds to wait for compilation">
            <div className="flex items-center gap-2">
              <Input value={values.timeout} onChange={(v: string) => set('timeout', v)} placeholder="60" />
              <span className="text-xs text-muted-foreground">seconds</span>
            </div>
          </Field>
        </CardContent>
      </Card>

      {/* Analysis */}
      <Card>
        <CardHeader className="pb-0">
          <CardTitle className="flex items-center gap-2 text-xs">
            <Cpu className="h-3.5 w-3.5 text-primary" /> Analysis Defaults
          </CardTitle>
          <CardDescription>Default optimization levels for new scans</CardDescription>
        </CardHeader>
        <CardContent className="p-5 pt-3">
          <Field label="Default optimization levels" desc="Levels compared in each scan">
            <div className="flex gap-1.5">
              {['O0', 'O1', 'O2', 'O3'].map(opt => {
                const active = values.defaultOpts.includes(opt)
                return (
                  <button
                    key={opt}
                    onClick={() => {
                      if (opt === 'O0') return
                      set('defaultOpts', active
                        ? values.defaultOpts.filter(o => o !== opt)
                        : [...values.defaultOpts, opt])
                    }}
                    disabled={opt === 'O0'}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-mono font-bold border transition-all disabled:opacity-50 ${
                      active
                        ? 'bg-primary/15 border-primary/30 text-primary'
                        : 'border-border text-muted-foreground hover:bg-accent'
                    }`}
                  >
                    -{opt}
                  </button>
                )
              })}
            </div>
          </Field>
        </CardContent>
      </Card>

      {/* Export */}
      <Card>
        <CardHeader className="pb-0">
          <CardTitle className="flex items-center gap-2 text-xs">
            <Download className="h-3.5 w-3.5 text-primary" /> Export Preferences
          </CardTitle>
          <CardDescription>Report format and output options</CardDescription>
        </CardHeader>
        <CardContent className="p-5 pt-3">
          <Field label="Default export format" desc="Format used when clicking Export">
            <div className="flex gap-1.5">
              {['json', 'pdf'].map(fmt => (
                <button
                  key={fmt}
                  onClick={() => set('exportFormat', fmt)}
                  className={`px-3 py-1 rounded-md text-[11px] font-medium border uppercase tracking-wide transition-all ${
                    values.exportFormat === fmt
                      ? 'bg-primary/15 border-primary/30 text-primary'
                      : 'border-border text-muted-foreground hover:bg-accent'
                  }`}
                >
                  {fmt}
                </button>
              ))}
            </div>
          </Field>
        </CardContent>
      </Card>

      {/* Info */}
      <Card className="border-border/50 bg-secondary/20">
        <CardContent className="p-4 flex items-start gap-3">
          <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <div className="text-[11px] text-muted-foreground space-y-0.5">
            <div><strong className="text-foreground">UB Time Bomb Detector</strong> v1.0.0</div>
            <div>Backend: FastAPI + Python 3 · Frontend: React + TypeScript + Tailwind</div>
            <div>Analysis: LLVM/Clang · IR diff engine · NetworkX CFG · tree-sitter source parsing</div>
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              {['CWE-190', 'CWE-476', 'CWE-843', 'CWE-457', 'CWE-190'].map((c, i) => (
                <Badge key={i} variant="outline" className="text-[9px]">{c}</Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
