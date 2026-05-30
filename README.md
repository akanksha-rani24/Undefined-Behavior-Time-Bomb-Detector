#  UB Time Bomb Detector
**Research-grade static analysis tool** that detects C/C++ undefined behavior patterns that appear harmless at `-O0` but are silently exploited by compiler optimizations at `-O2/-O3`.

```
int f(int x) { return x + 1 > x; }
//  -O0: runtime comparison (can return false when x == INT_MAX)
//  -O2: InstCombine adds nsw → folds to constant true → ALWAYS returns 1
```

## Architecture

```
ub-detector/
├── backend/                  # FastAPI + Python 3
│   ├── main.py               # App entry point, lifespan, CORS
│   ├── config.py             # Env-based configuration
│   ├── core/
│   │   ├── compiler.py       # Differential compilation engine (clang)
│   │   ├── ir_analyzer.py    # LLVM IR parser + structural differ
│   │   ├── ub_classifier.py  # UB pattern classifier (IR + source)
│   │   ├── cfg_analyzer.py   # CFG builder (NetworkX)
│   │   └── report_generator.py # JSON + PDF export
│   ├── models/
│   │   ├── database.py       # SQLAlchemy async (SQLite)
│   │   └── schemas.py        # Pydantic v2 models
│   └── routers/
│       ├── analysis.py       # POST /api/v1/analyze
│       ├── scans.py          # GET/DELETE /api/v1/scans
│       └── evaluation.py     # GET /api/v1/evaluation
├── frontend/                 # React 18 + TypeScript + Vite
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.tsx  # Stats overview + charts
│       │   ├── Scan.tsx       # Monaco editor + analysis controls
│       │   ├── Results.tsx    # Split-screen analysis results
│       │   ├── Evaluation.tsx # Benchmark evaluation
│       │   └── Settings.tsx   # Configuration
│       └── components/
│           ├── IRDiffViewer.tsx  # Side-by-side IR diff
│           ├── CFGViewer.tsx     # SVG CFG visualization
│           └── BombCard.tsx      # UB finding card
├── datasets/
│   ├── real_world/           # 5 real-world UB test cases
│   └── evaluation/           # Expected results + benchmark config
└── docker-compose.yml
```

## Quick Start

### Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

### Docker (Production)
```bash
docker-compose up --build
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/api/docs
```

## What It Detects

| UB Category | CWE | Confidence | Mechanism |
|---|---|---|---|
| Signed integer overflow | CWE-190 | 96% | `nsw` flag + branch elimination |
| Null check after dereference | CWE-476 | 94% | GVN non-null propagation |
| Strict aliasing violation | CWE-843 | 88-91% | TBAA load reordering |
| Uninitialized variable use | CWE-457 | 85% | `undef`/`poison` propagation |
| Shift amount overflow | CWE-190 | 94% | Poison propagation |
| Out-of-bounds access | CWE-125 | 72% | `inbounds` GEP assumption |

## Real-World Benchmark Cases

| # | Pattern | Reference | Category |
|---|---|---|---|
| 1 | `x+1 > x` overflow check | CWE-190, GCC PR#30475 | signed_integer_overflow |
| 2 | Null check after deref | Linux CVE-2011-1078 | null_pointer_dereference |
| 3 | Fast inv sqrt type pun | Quake III / OpenSSL | strict_aliasing_violation |
| 4 | Uninit auth bypass | CVE-2014-0977 / CWE-457 | uninitialized_variable |
| 5 | FFmpeg URL parser | CVE-2016-10190 | signed_integer_overflow |

## API Reference

```
POST   /api/v1/analyze           # Analyze source code
GET    /api/v1/scans             # List scan history
GET    /api/v1/scans/{id}        # Get single scan
DELETE /api/v1/scans/{id}        # Delete scan
GET    /api/v1/scans/{id}/export/json  # JSON export
GET    /api/v1/scans/{id}/export/pdf   # PDF export
GET    /api/v1/stats             # Dashboard statistics
GET    /api/v1/evaluation        # Run benchmark evaluation
GET    /api/v1/health            # Health check + clang version
GET    /api/docs                 # Interactive Swagger UI
```

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy async (SQLite), networkx, clang/LLVM
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Monaco Editor, Recharts, Framer Motion
- **Analysis**: LLVM IR structural diffing, NetworkX CFG analysis, source-level pattern matching
- **Deployment**: Docker + docker-compose, Nginx

## Example Output

```json
{
  "type": "signed_integer_overflow",
  "line": 42,
  "confidence": 0.96,
  "severity": "critical",
  "description": "'overflow_check': Comparison folded to constant [true]. Optimizer added nsw and eliminated conditional logic.",
  "o0_behavior": "Runtime comparison — can return false when x == INT_MAX",
  "o2_behavior": "InstCombine folds to constant 'true' using nsw assumption",
  "compiler_reasoning": "LLVM InstCombine marks arithmetic with nsw; SimplifyCFG eliminates overflow-guarding branches as provably dead.",
  "cwe": "CWE-190",
  "suggestion": "Use unsigned arithmetic or __builtin_add_overflow()"
}
```
