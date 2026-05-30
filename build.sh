#!/usr/bin/env bash
# build.sh — Install all dependencies for UB Time Bomb Detector
# Usage: ./build.sh
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${CYAN}[build]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $*"; }
err()   { echo -e "${RED}[error]${NC} $*" >&2; exit 1; }

# ── 1. Check prerequisites ─────────────────────────────────────────────────────
info "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || err "python3 not found. Install Python 3.10+"
command -v node    >/dev/null 2>&1 || err "node not found. Install Node.js 18+"
command -v npm     >/dev/null 2>&1 || err "npm not found."

CLANG_BIN=""
for candidate in clang clang-15 clang-14 clang-16 clang-17; do
    if command -v "$candidate" >/dev/null 2>&1; then
        CLANG_BIN="$candidate"
        break
    fi
done
[ -z "$CLANG_BIN" ] && err "clang not found. Install with: brew install llvm  OR  apt install clang"
ok "clang found: $CLANG_BIN ($(${CLANG_BIN} --version | head -1))"

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python version: $PYTHON_VER"

# ── 2. Backend ─────────────────────────────────────────────────────────────────
info "Installing backend Python dependencies..."
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    info "Created virtual environment at backend/.venv"
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
ok "Backend dependencies installed"

# Verify key packages
python3 -c "import fastapi, sqlalchemy, reportlab, networkx" \
    && ok "Backend package imports verified" \
    || err "Backend package verification failed"

deactivate
cd ..

# ── 3. Frontend ────────────────────────────────────────────────────────────────
info "Installing frontend Node dependencies..."
cd frontend
npm install --silent
ok "Frontend dependencies installed ($(ls node_modules | wc -l | tr -d ' ') packages)"
cd ..

# ── 4. Verify clang can compile C ─────────────────────────────────────────────
info "Verifying clang IR compilation..."
TMPFILE=$(mktemp /tmp/ub_test_XXXX.c)
echo 'int f(int x){return x+1>x;}' > "$TMPFILE"
$CLANG_BIN -O2 -S -emit-llvm "$TMPFILE" -o /dev/null 2>/dev/null \
    && ok "clang IR compilation verified" \
    || err "clang could not compile test file"
rm -f "$TMPFILE"

# ── 5. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Build complete. Run ./run.sh to start the app ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
