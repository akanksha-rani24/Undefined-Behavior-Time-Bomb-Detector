import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ExternalLink, Copy, CheckCheck, AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn, formatPct } from '@/lib/utils'
import type { UBBomb } from '@/lib/types'
import { SEVERITY_CONFIG } from '@/lib/types'

interface BombCardProps {
  bomb: UBBomb
  isActive?: boolean
  onClick?: () => void
  compact?: boolean
}

export default function BombCard({ bomb, isActive, onClick, compact }: BombCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const sev = SEVERITY_CONFIG[bomb.severity] ?? SEVERITY_CONFIG.low

  function handleCopy(e: React.MouseEvent) {
    e.stopPropagation()
    navigator.clipboard.writeText(bomb.suggestion)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function handleToggle() {
    setExpanded(x => !x)
    onClick?.()
  }

  if (compact) {
    return (
      <button
        onClick={handleToggle}
        className={cn(
          'w-full text-left rounded-md border px-3 py-2.5 transition-all',
          'hover:border-primary/40',
          isActive ? 'border-primary/50 bg-primary/5' : 'border-border bg-card',
        )}
      >
        <div className="flex items-center gap-2">
          <span className="text-base shrink-0">{bomb.category_icon}</span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Badge variant={bomb.severity as any} className="text-[9px] py-0">{bomb.severity}</Badge>
              {bomb.line > 0 && (
                <span className="text-[10px] text-muted-foreground font-mono">L{bomb.line}</span>
              )}
            </div>
            <div className="text-xs text-foreground/80 truncate">{bomb.category_label}</div>
          </div>
          <div className={cn('text-[10px] font-mono shrink-0', sev.text)}>
            {formatPct(bomb.confidence)}
          </div>
        </div>
      </button>
    )
  }

  return (
    <motion.div
      layout
      className={cn(
        'rounded-lg border overflow-hidden transition-colors',
        isActive ? 'border-primary/50' : 'border-border',
        'hover:border-primary/30',
      )}
    >
      {/* Header */}
      <button
        onClick={handleToggle}
        className="w-full text-left px-4 py-3 bg-card hover:bg-card/80 transition-colors"
      >
        <div className="flex items-start gap-3">
          <span className="text-lg mt-0.5 shrink-0">{bomb.category_icon}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <Badge variant={bomb.severity as any}>{bomb.severity}</Badge>
              <span className="text-xs font-semibold text-foreground">{bomb.category_label}</span>
              {bomb.line > 0 && (
                <span className="text-[10px] font-mono text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
                  line {bomb.line}{bomb.func_name ? ` · ${bomb.func_name}()` : ''}
                </span>
              )}
              {bomb.cwe && (
                <a
                  href={bomb.cwe_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={e => e.stopPropagation()}
                  className="text-[10px] text-blue-400 hover:underline flex items-center gap-0.5"
                >
                  {bomb.cwe} <ExternalLink className="h-2.5 w-2.5" />
                </a>
              )}
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{bomb.description}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <div className="text-right">
              <div className={cn('text-xs font-bold font-mono', sev.text)}>
                {formatPct(bomb.confidence)}
              </div>
              <div className="text-[10px] text-muted-foreground">confidence</div>
            </div>
            <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform', expanded && 'rotate-180')} />
          </div>
        </div>
      </button>

      {/* Expanded body */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-border bg-background px-4 py-4 space-y-4">
              {/* O0 vs O2 comparison */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-blue-500/20 bg-blue-500/5 p-3">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-blue-400 mb-1.5">
                    −O0 Behavior
                  </div>
                  <p className="text-xs text-foreground/80 leading-relaxed">{bomb.o0_behavior}</p>
                </div>
                <div className="rounded-md border border-red-500/20 bg-red-500/5 p-3">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-red-400 mb-1.5">
                    −O2 Behavior
                  </div>
                  <p className="text-xs text-foreground/80 leading-relaxed">{bomb.o2_behavior}</p>
                </div>
              </div>

              {/* Compiler reasoning */}
              {bomb.compiler_reasoning && (
                <div className="rounded-md border border-border bg-secondary/30 p-3">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Compiler Reasoning (LLVM)
                  </div>
                  <p className="text-xs text-foreground/70 leading-relaxed">{bomb.compiler_reasoning}</p>
                </div>
              )}

              {/* IR evidence */}
              {bomb.ir_evidence && (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                    IR Evidence
                  </div>
                  <pre className="text-[11px] font-mono text-violet-300 bg-background rounded-md border border-border p-2.5 overflow-x-auto whitespace-pre-wrap">
                    {bomb.ir_evidence}
                  </pre>
                </div>
              )}

              {/* Source snippet */}
              {bomb.source_snippet && (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-1.5">
                    Source Context
                  </div>
                  <pre className="text-[11px] font-mono text-foreground/80 bg-background rounded-md border border-border p-2.5 overflow-x-auto">
                    {bomb.source_snippet}
                  </pre>
                </div>
              )}

              {/* Fix suggestion */}
              <div className="flex items-start gap-3 rounded-md border border-green-500/25 bg-green-500/8 p-3">
                <AlertTriangle className="h-4 w-4 text-green-400 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-green-400 mb-1">
                    Recommended Fix
                  </div>
                  <p className="text-xs text-green-300/90 leading-relaxed">{bomb.suggestion}</p>
                </div>
                <button
                  onClick={handleCopy}
                  className="shrink-0 flex items-center gap-1 text-[10px] text-green-400 hover:text-green-300 transition-colors"
                >
                  {copied ? <CheckCheck className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
