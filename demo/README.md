# Demo Screenshots & Walkthrough

## How to Run the Demo

1. Start the app: `./run.sh`
2. Open browser at http://localhost:5173

## Demo Walkthrough

### Step 1 — Scan Page (paste demo code)
Paste any code from `testcases/` into the Monaco editor and click **Analyze Code**.

### Step 2 — Progress Animation
Watch the 4-phase progress bar:
- **Compiling** → clang -O0 and -O2
- **IR Analysis** → parsing and diffing LLVM IR
- **UB Classification** → rule-based detection
- **CFG Analysis** → control flow graph construction

### Step 3 — Results Page
- Left: source with colored gutter markers (red = critical, orange = high)
- Right: BombCards with full findings, O0/O2 behavior, IR evidence, fix suggestion
- Bottom tabs: IR Diff viewer, CFG visualization

### Step 4 — Dashboard
After several scans, view aggregate statistics: pie chart of UB categories, severity bar chart, recent scan history.

### Step 5 — Evaluation Tab
Click **Run Evaluation** to benchmark all 5 test cases automatically and see precision/recall/F1.

## Screenshots

Add screenshots to this folder named:
- `01_scan_page.png` — Monaco editor with code
- `02_progress.png` — animated analysis progress
- `03_results_bombcard.png` — expanded BombCard showing findings
- `04_ir_diff.png` — IR diff viewer (green=added in O2, red=removed)
- `05_cfg_viewer.png` — CFG with eliminated block (red dashed)
- `06_dashboard.png` — statistics and charts
- `07_evaluation.png` — benchmark results with F1 scores
- `08_failure_case.png` — safe unsigned code showing 0 findings
