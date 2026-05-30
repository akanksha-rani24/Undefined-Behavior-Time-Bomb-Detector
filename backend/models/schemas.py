from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


# ── UB Classification ──────────────────────────────────────────────────────────

class UBBomb(BaseModel):
    id: int
    line: int
    col: int = 0
    end_line: int = 0
    func_name: str = ""
    category: str                    # machine key
    category_label: str              # human label
    category_icon: str = "💣"
    severity: str                    # critical | high | medium | low
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    o0_behavior: str
    o2_behavior: str
    o0_ir_snippet: str = ""
    o2_ir_snippet: str = ""
    suggestion: str
    ir_evidence: str = ""
    compiler_reasoning: str = ""
    source_snippet: str = ""
    cwe: str = ""
    cwe_url: str = ""


class ScanSummary(BaseModel):
    total_bombs: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    confidence_avg: float = 0.0
    functions_changed: int = 0
    blocks_eliminated: int = 0


class FunctionDiff(BaseModel):
    name: str
    o0_lines: int
    o2_lines: int
    o0_blocks: int
    o2_blocks: int
    changed: bool
    bombs: int


class CFGNode(BaseModel):
    id: str
    label: str
    kind: str = "block"  # entry | block | exit | eliminated
    opt: str             # "o0" | "o2" | "both"


class CFGEdge(BaseModel):
    source: str
    target: str
    kind: str = "branch"  # branch | fallthrough | back


class CFGData(BaseModel):
    o0_nodes: List[CFGNode] = []
    o0_edges: List[CFGEdge] = []
    o2_nodes: List[CFGNode] = []
    o2_edges: List[CFGEdge] = []
    eliminated_nodes: List[str] = []  # IDs in O0 but not O2
    added_nodes: List[str] = []       # IDs in O2 but not O0


# ── Scan ─────────────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    source_code: str
    filename: str = "source.c"
    language: str = "c"         # "c" | "cpp"
    opt_levels: List[str] = ["O0", "O2"]
    include_o3: bool = False


class ScanResult(BaseModel):
    id: str
    filename: str
    language: str
    source_code: str
    status: str                          # pending | running | completed | error
    created_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    opt_levels: List[str] = []
    summary: Optional[ScanSummary] = None
    bombs: List[UBBomb] = []
    function_diffs: List[FunctionDiff] = []
    o0_ir: str = ""
    o2_ir: str = ""
    o3_ir: str = ""
    ir_diff: str = ""                    # O0 vs O2 unified diff
    cfg: Optional[CFGData] = None
    compile_error: Optional[str] = None
    has_clang: bool = True


class ScanListItem(BaseModel):
    id: str
    filename: str
    language: str
    status: str
    created_at: datetime
    summary: Optional[ScanSummary] = None


# ── Evaluation ────────────────────────────────────────────────────────────────

class EvalCase(BaseModel):
    id: int
    name: str
    filename: str
    reference: str
    expected_category: str
    expected_line: int
    description: str
    severity: str


class EvalResult(BaseModel):
    case: EvalCase
    detected: bool
    detected_category: Optional[str]
    detected_line: Optional[int]
    confidence: Optional[float]
    true_positive: bool
    false_positive: bool
    false_negative: bool
    notes: str = ""


class EvaluationReport(BaseModel):
    total_cases: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    results: List[EvalResult]


# ── Stats ─────────────────────────────────────────────────────────────────────

class GlobalStats(BaseModel):
    total_scans: int = 0
    total_bombs: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    category_distribution: dict[str, int] = {}
    recent_scans: List[ScanListItem] = []
    avg_confidence: float = 0.0
