#!/usr/bin/env bash
# run.sh — Start the UB Time Bomb Detector (backend + frontend)
# Usage: ./run.sh
#        ./run.sh --backend-only
#        ./run.sh --frontend-only
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${CYAN}[run]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
err()   { echo -e "${RED}[err]${NC}  $*" >&2; }

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8001
FRONTEND_PORT=5173
MODE="both"

[ "${1:-}" = "--backend-only"  ] && MODE="backend"
[ "${1:-}" = "--frontend-only" ] && MODE="frontend"

# ── Cleanup on exit ────────────────────────────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
    echo ""
    info "Shutting down..."
    [ -n "$BACKEND_PID"  ] && kill "$BACKEND_PID"  2>/dev/null && info "Backend stopped"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && info "Frontend stopped"
    exit 0
}
trap cleanup INT TERM

# ── Backend ────────────────────────────────────────────────────────────────────
start_backend() {
    info "Starting backend on port $BACKEND_PORT..."
    cd "$REPO_ROOT/backend"

    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif command -v uvicorn >/dev/null 2>&1; then
        : # system uvicorn
    else
        err "backend/.venv not found. Run ./build.sh first."
        exit 1
    fi

    python -m uvicorn main:app --reload --port "$BACKEND_PORT" --host 0.0.0.0 \
        --log-level warning &
    BACKEND_PID=$!
    cd "$REPO_ROOT"

    # Wait for backend to be ready
    MAX_WAIT=15
    for i in $(seq 1 $MAX_WAIT); do
        if curl -sf "http://localhost:$BACKEND_PORT/api/v1/health" >/dev/null 2>&1; then
            ok "Backend ready at http://localhost:$BACKEND_PORT"
            ok "API docs at     http://localhost:$BACKEND_PORT/api/docs"
            return 0
        fi
        sleep 1
    done
    warn "Backend did not respond after ${MAX_WAIT}s — check logs above"
}

# ── Frontend ───────────────────────────────────────────────────────────────────
start_frontend() {
    info "Starting frontend on port $FRONTEND_PORT..."
    cd "$REPO_ROOT/frontend"

    if [ ! -d "node_modules" ]; then
        err "frontend/node_modules not found. Run ./build.sh first."
        exit 1
    fi

    npm run dev -- --port "$FRONTEND_PORT" --host 0.0.0.0 2>&1 | \
        grep -v "^>" | grep -v "^$" &
    FRONTEND_PID=$!
    cd "$REPO_ROOT"

    # Wait for frontend
    MAX_WAIT=20
    for i in $(seq 1 $MAX_WAIT); do
        if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
            ok "Frontend ready at http://localhost:$FRONTEND_PORT"
            return 0
        fi
        sleep 1
    done
    warn "Frontend did not respond after ${MAX_WAIT}s — it may still be building"
}

# ── Main ───────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  💣 UB Time Bomb Detector            ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

case "$MODE" in
    both)     start_backend; start_frontend ;;
    backend)  start_backend ;;
    frontend) start_frontend ;;
esac

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
[ "$MODE" != "backend"  ] && echo -e "  App UI:   ${GREEN}http://localhost:$FRONTEND_PORT${NC}"
[ "$MODE" != "frontend" ] && echo -e "  API:      ${GREEN}http://localhost:$BACKEND_PORT${NC}"
[ "$MODE" != "frontend" ] && echo -e "  API docs: ${GREEN}http://localhost:$BACKEND_PORT/api/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop"
echo ""

# Keep script alive until Ctrl+C
wait
