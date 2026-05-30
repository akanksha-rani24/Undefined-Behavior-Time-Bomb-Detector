export interface UBBomb {
  id: number
  line: number
  col: number
  end_line: number
  func_name: string
  category: string
  category_label: string
  category_icon: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  confidence: number
  description: string
  o0_behavior: string
  o2_behavior: string
  o0_ir_snippet: string
  o2_ir_snippet: string
  suggestion: string
  ir_evidence: string
  compiler_reasoning: string
  source_snippet: string
  cwe: string
  cwe_url: string
}

export interface ScanSummary {
  total_bombs: number
  critical: number
  high: number
  medium: number
  low: number
  confidence_avg: number
  functions_changed: number
  blocks_eliminated: number
}

export interface FunctionDiff {
  name: string
  o0_lines: number
  o2_lines: number
  o0_blocks: number
  o2_blocks: number
  changed: boolean
  bombs: number
}

export interface CFGNode {
  id: string
  label: string
  kind: 'entry' | 'block' | 'exit' | 'eliminated'
  opt: 'o0' | 'o2'
}

export interface CFGEdge {
  source: string
  target: string
  kind: string
}

export interface CFGData {
  o0_nodes: CFGNode[]
  o0_edges: CFGEdge[]
  o2_nodes: CFGNode[]
  o2_edges: CFGEdge[]
  eliminated_nodes: string[]
  added_nodes: string[]
}

export interface ScanResult {
  id: string
  filename: string
  language: string
  source_code: string
  status: 'pending' | 'running' | 'completed' | 'error'
  created_at: string
  completed_at: string | null
  duration_ms: number | null
  opt_levels: string[]
  summary: ScanSummary | null
  bombs: UBBomb[]
  function_diffs: FunctionDiff[]
  o0_ir: string
  o2_ir: string
  o3_ir: string
  ir_diff: string
  cfg: CFGData | null
  compile_error: string | null
  has_clang: boolean
}

export interface ScanListItem {
  id: string
  filename: string
  language: string
  status: string
  created_at: string
  summary: ScanSummary | null
}

export interface GlobalStats {
  total_scans: number
  total_bombs: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  category_distribution: Record<string, number>
  recent_scans: ScanListItem[]
  avg_confidence: number
}

export interface EvalCase {
  id: number
  name: string
  filename: string
  reference: string
  expected_category: string
  expected_line: number
  description: string
  severity: string
}

export interface EvalResult {
  case: EvalCase
  detected: boolean
  detected_category: string | null
  detected_line: number | null
  confidence: number | null
  true_positive: boolean
  false_positive: boolean
  false_negative: boolean
  notes: string
}

export interface EvaluationReport {
  total_cases: number
  true_positives: number
  false_positives: number
  false_negatives: number
  precision: number
  recall: number
  f1: number
  results: EvalResult[]
}

export const SEVERITY_CONFIG = {
  critical: { color: '#ef4444', bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', label: 'CRITICAL' },
  high:     { color: '#f97316', bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', label: 'HIGH' },
  medium:   { color: '#eab308', bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', label: 'MEDIUM' },
  low:      { color: '#22c55e', bg: 'bg-green-500/15', text: 'text-green-400', border: 'border-green-500/30', label: 'LOW' },
} as const

export const CATEGORY_COLORS: Record<string, string> = {
  signed_integer_overflow:   '#f59e0b',
  null_pointer_dereference:  '#ef4444',
  strict_aliasing_violation: '#3b82f6',
  uninitialized_variable:    '#a855f7',
  shift_overflow:             '#06b6d4',
  out_of_bounds_access:      '#f97316',
  division_by_zero:           '#ec4899',
  lifetime_violation:         '#84cc16',
  type_punning:               '#6366f1',
  invalid_pointer_arithmetic: '#14b8a6',
}
