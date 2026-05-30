# DESIGN — UB Time Bomb Detector

## 1. Problem Statement

C and C++ compilers are permitted by the language standard to treat **undefined behavior (UB)** as impossible. Modern optimizers (clang/GCC at `-O2`/`-O3`) exploit this assumption aggressively: they delete null-pointer checks, fold overflow guards to constants, reorder type-punned memory accesses, and eliminate entire code paths. The result is code that *appears correct* under debug builds (`-O0`) but silently misbehaves in production (`-O2`/`-O3`).

No existing lightweight tool directly shows **which compiler optimization pass exploited which UB, and why**. Static analyzers like Clang's `scan-build` detect likely UB in source code but do not show the optimizer's decision; sanitizers (UBSan, ASan) require runtime execution with triggering inputs.

**Goal:** Build a tool that detects *time-bomb UB patterns* — specifically those that change observable behavior between optimization levels — by differentially analyzing LLVM IR output.

---

## 2. Approach

### 2.1 Core Idea: Differential IR Analysis

Compile the same source **twice**:

```
clang -O0 -S -emit-llvm src.c -o src_O0.ll
clang -O2 -S -emit-llvm src.c -o src_O2.ll
```

Then structurally diff the two IR files. Differences in IR reveal exactly **what the optimizer changed** and, by cross-referencing known LLVM pass behavior, **why**.

This approach is:
- **Sound for detection**: if IR differs in a UB-indicative way, UB is present
- **No runtime needed**: purely static, works on any code fragment
- **Explainable**: every finding links to a specific LLVM pass and IR construct

### 2.2 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      React Frontend                          │
│  Monaco Editor → POST /api/v1/analyze → Results Page        │
│  Dashboard (Recharts) │ Evaluation │ Scan History            │
└───────────────────────────────┬──────────────────────────────┘
                                │ HTTP/JSON
┌───────────────────────────────▼──────────────────────────────┐
│                   FastAPI Backend (Python)                    │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ compiler.py │  │ ir_analyzer  │  │ ub_classifier.py │   │
│  │             │  │     .py      │  │                  │   │
│  │ clang -O0   │→│ parse_ir()   │→│ detect_from_ir() │   │
│  │ clang -O2   │  │ compare()    │  │ detect_from_src  │   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
│                                             │                │
│  ┌──────────────┐  ┌──────────────────┐    │                │
│  │cfg_analyzer  │  │report_generator  │◄───┘                │
│  │(NetworkX)    │  │(reportlab PDF)   │                     │
│  └──────────────┘  └──────────────────┘                     │
│                                                              │
│  SQLite + SQLAlchemy async (scan history, stats)            │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Detection Strategy

Detection uses two complementary signals:

| Signal Type | How Collected | What It Detects |
|---|---|---|
| **IR structural diff** | Parse both `.ll` files, compare per-function | `nsw` flags, eliminated blocks, `undef`/`poison`, null icmp removal, TBAA metadata |
| **Source pattern match** | Regex on C/C++ source text | Suspicious constructs (e.g., `x+1>x`, deref-then-null-check) |

Both signals are combined in `ub_classifier.py` with weighted confidence scoring.

---

## 3. Design Decisions

### 3.1 Why LLVM IR (not AST or binary)?

| Option | Pros | Cons |
|---|---|---|
| **Source AST** (clang-tidy, cppcheck) | No compiler needed | Cannot see optimizer decisions; high false-positive rate |
| **LLVM IR** ✓ | Shows exact optimizer output; LLVM passes are well-documented | Requires clang; IR format changes across versions |
| **Binary disassembly** | Sees final output | No debug symbols, hard to map back to source |
| **Runtime sanitizers** | Exact; no false positives | Requires execution and triggering inputs |

LLVM IR is the sweet spot: it is **post-parse, pre-machine-code**, making optimizer decisions visible in a readable text format.

### 3.2 Why differential compilation (not single-pass analysis)?

Analyzing only `-O2` IR misses the key insight: a construct is a *time bomb* specifically because it **behaves differently at two optimization levels**. Diffing makes this explicit and maps directly to what a developer would observe (debug vs. production build divergence).

### 3.3 Why FastAPI + async SQLAlchemy?

- The compilation step is I/O bound (subprocess calls, file reads). Async allows multiple concurrent analysis requests without thread overhead.
- FastAPI auto-generates OpenAPI docs (`/api/docs`), making the API self-documenting for graders.

### 3.4 Why Monaco Editor (not `<textarea>`)?

Monaco provides gutter decorations — colored margin markers on specific line numbers. This is critical for the tool: findings need to be **spatially located** in the source, not just listed.

### 3.5 Why NetworkX for CFG?

- Zero-dependency graph library in Python
- `DiGraph` with BFS layout gives a clean tree-like CFG display
- Allows direct node comparison between O0 and O2 CFGs to identify eliminated blocks

---

## 4. Alternatives Considered

### 4.1 Use tree-sitter for source parsing

**Considered:** Use `tree-sitter` (incremental parser) for precise C/C++ AST analysis instead of regex.

**Rejected:** `tree-sitter-c` and `tree-sitter-cpp` packages had installation compatibility issues on Apple Silicon. Regex patterns for the target UB constructs are precise enough for the 6 categories in scope and avoid the dependency.

### 4.2 Use clang's `-fsanitize=undefined` (UBSan) output

**Considered:** Instrument with UBSan and run the code.

**Rejected:** Requires execution with inputs that actually trigger the UB path. For time bombs, the UB may only manifest under specific optimization assumptions — UBSan at `-O0` won't show what `-O2` eliminates.

### 4.3 Use Python LLVM bindings (`llvmlite`)

**Considered:** Use `llvmlite` to parse IR programmatically instead of regex.

**Rejected:** `llvmlite` ships its own LLVM build (large binary, ~100MB), and its IR parsing API is oriented toward IR *generation*, not analysis. Text parsing of the `-S -emit-llvm` output is simpler and sufficient for the flag/instruction patterns we need.

### 4.4 Batch compilation with `compile_commands.json`

**Considered:** Accept a full project (compile commands database) instead of single-file snippets.

**Deferred:** Single-file analysis covers the core research use case and simplifies the demo. Multi-file support would require a CMake/Bear integration layer — good future work.

### 4.5 Graph database for scan storage

**Considered:** Neo4j or similar for storing CFG relationships.

**Rejected:** Overkill for scan history. SQLite stores the CFG as a JSON blob; the graph is only needed for per-scan visualization, not cross-scan querying.

---

## 5. UB Category Coverage

| Category | CWE | LLVM Pass Exploited | Detection Signal |
|---|---|---|---|
| Signed integer overflow | CWE-190 | InstCombine + SimplifyCFG | `nsw` flag added; block count drops |
| Null pointer dereference | CWE-476 | GVN | Null `icmp` removed |
| Strict aliasing violation | CWE-843 | TBAA (alias analysis) | `!tbaa` metadata added to loads |
| Uninitialized variable | CWE-457 | CorrelatedValuePropagation | `undef`/`poison` in IR |
| Shift amount overflow | CWE-190 | InstCombine | `poison` on shift |
| Out-of-bounds access | CWE-125 | GEP `inbounds` | `inbounds` flag added |

---

## 6. Security and Scope

- Input code is written to a sandboxed temp directory (`/tmp`) and compiled only — never executed.
- The tool is intended for local development use; the API has no authentication by design (single-user tool).
- CORS is restricted to `localhost` origins in production configuration.
