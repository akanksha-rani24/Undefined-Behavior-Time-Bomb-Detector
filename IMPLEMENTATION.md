# IMPLEMENTATION — UB Time Bomb Detector

## 1. LLVM IR Differential Analysis

### 1.1 Compilation Pipeline

The entry point is `backend/core/compiler.py`. For each analysis request the tool invokes clang twice via `asyncio.get_event_loop().run_in_executor()` (offloads the blocking subprocess to a thread pool):

```python
# Simplified from compiler.py
async def compile_differential(source: str, language: str, opt_level: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        src_file = write_source(tmpdir, source, language)

        # Two compilations: O0 and the requested opt level
        ir_o0 = await _compile_async(src_file, "O0", tmpdir)
        ir_opt = await _compile_async(src_file, opt_level, tmpdir)

        return ir_o0, ir_opt

def _compile_sync(src_path, opt_flag, out_path):
    result = subprocess.run([
        "clang", f"-{opt_flag}", "-S", "-emit-llvm",
        "-fno-discard-value-names",   # preserve variable names in IR
        "-Wno-everything",            # suppress warnings — we want IR, not lint
        str(src_path), "-o", str(out_path)
    ], capture_output=True, text=True, timeout=30)
    return out_path.read_text()
```

The `-fno-discard-value-names` flag is critical: without it, clang replaces named variables with anonymous `%0`, `%1`, … making function-level matching between O0 and O2 harder.

### 1.2 IR Parsing

`backend/core/ir_analyzer.py` parses the textual LLVM IR (`.ll` format) using Python `re`.

**Function extraction** — LLVM IR functions follow this pattern:
```
define i32 @function_name(...) {
  ; basic blocks
}
```

The parser groups all lines between `define` and the matching closing `}` into a per-function dictionary.

**Key IR signals detected:**

| IR Construct | What It Means | Example |
|---|---|---|
| `nsw` flag | "No Signed Wrap" — optimizer assumed no signed overflow | `add nsw i32 %x, 1` |
| `nuw` flag | "No Unsigned Wrap" | `add nuw i32 %x, 1` |
| `undef` | Uninitialized value | `%status = load i32, i32* %p, ... undef` |
| `poison` | Poison value (stronger than undef) | `%r = shl i32 %x, poison` |
| `!tbaa` metadata | Type-Based Alias Analysis annotation | `load float, float* %p, !tbaa !5` |
| `icmp eq ... null` | Null comparison instruction | `%cmp = icmp eq i32* %ptr, null` |
| Basic block count | Number of labeled sections in function | Decrease → eliminated branches |

**IRDiff dataclass:**
```python
@dataclass
class IRDiff:
    function_name: str
    o0_blocks: int          # basic block count at O0
    o2_blocks: int          # basic block count at O2
    nsw_added: bool         # nsw appeared at O2 but not O0
    undef_present: bool     # undef in O2 IR
    null_icmp_removed: bool # null comparison present at O0, gone at O2
    tbaa_added: bool        # !tbaa metadata appeared at O2
    poison_present: bool    # poison value in O2
    o0_lines: list[str]     # raw O0 IR lines for this function
    o2_lines: list[str]     # raw O2 IR lines for this function
```

### 1.3 UB Classification

`backend/core/ub_classifier.py` maps IR signals to UB categories using rule chains:

```python
def detect_from_ir_diff(diff: IRDiff) -> list[UBBomb]:
    findings = []

    # Rule 1: Signed integer overflow
    if diff.nsw_added and (diff.o2_blocks < diff.o0_blocks):
        findings.append(UBBomb(
            type="signed_integer_overflow",
            confidence=0.96,
            severity="critical",
            ir_evidence=find_nsw_line(diff.o2_lines),
            o0_behavior="Runtime arithmetic — overflow wraps on hardware",
            o2_behavior="InstCombine adds nsw; SimplifyCFG folds overflow branch to dead code",
            compiler_reasoning="LLVM InstCombine marks arithmetic nsw assuming UB never occurs; "
                               "SimplifyCFG then proves overflow-checking branches are unreachable.",
            ...
        ))

    # Rule 2: Null pointer dereference (null check eliminated)
    if diff.null_icmp_removed:
        findings.append(UBBomb(
            type="null_pointer_dereference",
            confidence=0.94,
            ...
        ))

    # Rule 3: Strict aliasing
    if diff.tbaa_added:
        findings.append(UBBomb(type="strict_aliasing_violation", confidence=0.89, ...))

    # Rule 4: Uninitialized variable
    if diff.undef_present:
        findings.append(UBBomb(type="uninitialized_variable", confidence=0.85, ...))

    # Rule 5: Shift overflow
    if diff.poison_present and has_shift_instruction(diff.o2_lines):
        findings.append(UBBomb(type="shift_amount_overflow", confidence=0.94, ...))

    return findings
```

Source-level detection (`detect_from_source`) uses regex patterns as a fallback and to assign accurate line numbers:

```python
SOURCE_PATTERNS = {
    "signed_integer_overflow": [
        r'\b(\w+)\s*\+\s*1\s*[<>]\s*\1\b',          # x+1 > x
        r'\b(\w+)\s*\*\s*(\w+)\s*[<>]\s*(?:\1|\2)\b', # count*size < count
    ],
    "null_pointer_dereference": [
        r'\*\s*\w+\s*;[^;]*if\s*\(\s*\w+\s*==\s*NULL',  # deref then null check
    ],
    "uninitialized_variable": [
        r'\b(int|char|float|double|long)\s+(\w+)\s*;(?![^;]*=)',  # declared, not initialized
    ],
    ...
}
```

---

## 2. Control Flow Graph Analysis

### 2.1 CFG Construction (NetworkX)

`backend/core/cfg_analyzer.py` builds a `networkx.DiGraph` from IR basic blocks:

```python
def build_cfg_from_ir(ir_text: str) -> nx.DiGraph:
    G = nx.DiGraph()
    current_block = None

    for line in ir_text.splitlines():
        # Basic block label (entry point)
        if label_match := re.match(r'^(\w+):', line):
            current_block = label_match.group(1)
            G.add_node(current_block)

        # Branch instruction → edges
        elif 'br i1' in line:
            targets = re.findall(r'label %(\w+)', line)
            for t in targets:
                G.add_edge(current_block, t)

        elif m := re.match(r'\s*br label %(\w+)', line):
            G.add_edge(current_block, m.group(1))

    return G
```

### 2.2 Eliminated Block Detection

```python
def find_eliminated_blocks(g_o0: nx.DiGraph, g_o2: nx.DiGraph) -> list[str]:
    o0_nodes = set(g_o0.nodes())
    o2_nodes = set(g_o2.nodes())
    return list(o0_nodes - o2_nodes)   # blocks present at O0 but gone at O2
```

Eliminated blocks are returned as `eliminated_blocks` in the `CFGData` schema and rendered with red dashed borders in the frontend `CFGViewer.tsx`.

### 2.3 BFS Layout

Nodes are positioned using BFS from the entry block to give a top-down tree layout, suitable for SVG rendering without a graph layout library on the frontend:

```python
def bfs_layout(G: nx.DiGraph) -> dict[str, tuple[float, float]]:
    entry = list(G.nodes())[0] if G.nodes() else "entry"
    pos = {}
    for depth, node in bfs_with_depth(G, entry):
        siblings = [n for n, d in bfs_with_depth(G, entry) if d == depth]
        x = siblings.index(node) / max(len(siblings), 1)
        pos[node] = (x, -depth * 0.2)
    return pos
```

---

## 3. API Layer

### 3.1 Main Analysis Endpoint

`backend/routers/analysis.py` — `POST /api/v1/analyze`:

```python
@router.post("/analyze", response_model=ScanResult)
async def analyze(req: AnalysisRequest, db: AsyncSession = Depends(get_db)):
    # 1. Compile
    ir_o0, ir_o2 = await compile_differential(req.source, req.language, req.opt_level)

    # 2. Parse and diff IR
    diffs = compare_functions(parse_ir_functions(ir_o0), parse_ir_functions(ir_o2))

    # 3. Classify UB
    bombs = classify_all(diffs, req.source)

    # 4. Build CFG
    cfg_data = build_cfg_data(ir_o0, ir_o2)

    # 5. Persist
    record = ScanRecord(source=req.source, result=result.model_dump_json())
    db.add(record)
    await db.commit()

    return result
```

### 3.2 Data Schemas (Pydantic v2)

```python
class UBBomb(BaseModel):
    type: str                    # e.g. "signed_integer_overflow"
    line: int                    # source line number
    confidence: float            # 0.0 – 1.0
    severity: str                # "critical" | "high" | "medium" | "low"
    description: str
    o0_behavior: str
    o2_behavior: str
    compiler_reasoning: str
    ir_evidence: str             # the specific IR line proving the finding
    cwe: str                     # e.g. "CWE-190"
    suggestion: str              # fix recommendation

class ScanResult(BaseModel):
    id: str
    source: str
    language: str
    opt_level: str
    bombs: list[UBBomb]
    ir_o0: str                   # full O0 IR text
    ir_o2: str                   # full O2 IR text
    function_diffs: list[FunctionDiff]
    cfg: CFGData
    analysis_time_ms: float
    timestamp: datetime
```

---

## 4. Frontend Implementation

### 4.1 Monaco Editor Integration (Scan.tsx)

```typescript
// Gutter decorations for UB findings (Results.tsx)
const decorations = bombs.map(bomb => ({
    range: new monaco.Range(bomb.line, 1, bomb.line, 1),
    options: {
        isWholeLine: true,
        glyphMarginClassName: severityGlyph(bomb.severity),  // CSS class
        overviewRulerColor: severityColor(bomb.severity),
        overviewRulerLane: monaco.editor.OverviewRulerLane.Right,
    }
}));
editorRef.current.deltaDecorations([], decorations);
```

### 4.2 CFG SVG Renderer (CFGViewer.tsx)

Pure SVG — no D3 or graph library dependency on the frontend:

```typescript
// Nodes
{nodes.map(node => (
  <g key={node.id}>
    <rect
      x={node.x} y={node.y} width={NODE_W} height={NODE_H}
      fill={node.eliminated ? "transparent" : "#1e293b"}
      stroke={node.eliminated ? "#ef4444" : "#06b6d4"}
      strokeDasharray={node.eliminated ? "6,3" : "0"}
    />
    <text x={node.x + NODE_W/2} y={node.y + NODE_H/2}>{node.label}</text>
  </g>
))}
// Edges as <line> elements with arrowhead markers
```

### 4.3 IR Diff Highlighting (IRDiffViewer.tsx)

```typescript
function highlightDiff(o0: string, o2: string): DiffLine[] {
    const o0Lines = new Set(o0.split('\n'));
    const o2Lines = new Set(o2.split('\n'));
    return [
        ...o0Lines.difference(o2Lines).map(l => ({ line: l, type: 'removed' })),
        ...o2Lines.difference(o0Lines).map(l => ({ line: l, type: 'added'   })),
    ];
}
```

---

## 5. Database Layer

SQLAlchemy async with SQLite:

```python
class ScanRecord(Base):
    __tablename__ = "scans"
    id         = Column(String, primary_key=True, default=lambda: str(uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    language   = Column(String)
    opt_level  = Column(String)
    bomb_count = Column(Integer)
    result_json= Column(Text)    # full ScanResult as JSON blob
```

Async engine uses `aiosqlite` driver:
```python
engine = create_async_engine("sqlite+aiosqlite:///./ub_detector.db", echo=False)
```

---

## 6. LLVM Pass Reference

| LLVM Pass | What It Does | UB It Exploits |
|---|---|---|
| **InstCombine** | Constant folds + canonicalizes instructions; adds `nsw`/`nuw` flags | Signed overflow |
| **SimplifyCFG** | Eliminates unreachable basic blocks | Overflow checks folded dead by InstCombine |
| **GVN** (Global Value Numbering) | Deduplicates values; hoists non-null proof from dereferences | Null pointer checks |
| **TBAA** (Type-Based Alias Analysis) | Annotates loads/stores with type info to enable reordering | Strict aliasing casts |
| **CorrelatedValuePropagation** | Propagates value constraints across branches | Uninitialized/undef propagation |
| **LoopSimplify + LICM** | Loop canonicalization + invariant hoisting | Signed-overflow loops turned infinite |

---

## 7. Running Tests

```bash
# Unit tests for the backend analysis pipeline
cd backend
python -m pytest ../tests/ -v

# Manual single-file analysis via API
curl -X POST http://localhost:8001/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"source": "int f(int x){return x+1>x;}", "language": "c", "opt_level": "O2"}'
```
