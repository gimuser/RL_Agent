#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
MONGO_URI="${MONGO_URI:-mongodb://127.0.0.1:27017}"

PYTHON="${PYTHON:-$(command -v python3 || true)}"
NPM="${NPM:-$(command -v npm || true)}"

BACKEND_PID=""
FRONTEND_PID=""

log() {
    printf '\n==> %s\n' "$1"
}

die() {
    printf '\nERROR: %s\n' "$1" >&2
    exit 1
}

cleanup() {
    if [[ -n "${FRONTEND_PID:-}" ]]; then
        kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    fi

    if [[ -n "${BACKEND_PID:-}" ]]; then
        kill "$BACKEND_PID" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT INT TERM

echo
echo "============================================================"
echo " RL AGENT — LOCAL START"
echo "============================================================"

# ---------------------------------------------------------------------------
# Basic checks
# ---------------------------------------------------------------------------

if [[ -z "$PYTHON" ]]; then
    die "python3 was not found. Install Python 3 or set PYTHON=/path/to/python3."
fi

if [[ -z "$NPM" ]]; then
    die "npm was not found. Install Node.js/npm."
fi

if [[ ! -f "$ROOT_DIR/frontend/package.json" ]]; then
    die "frontend/package.json was not found."
fi

if [[ ! -f "$ROOT_DIR/backend/main.py" ]]; then
    die "backend/main.py was not found."
fi

# ---------------------------------------------------------------------------
# Frontend dependency check
#
# IMPORTANT:
# No Python packages are installed here.
# No Torch download is triggered.
# ---------------------------------------------------------------------------

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
    log "Frontend dependencies not found."

    if [[ -f "$ROOT_DIR/frontend/package-lock.json" ]]; then
        log "Running npm ci"
        (
            cd "$ROOT_DIR/frontend"
            "$NPM" ci
        ) || die "npm ci failed."
    else
        log "package-lock.json not found; running npm install"
        (
            cd "$ROOT_DIR/frontend"
            "$NPM" install
        ) || die "npm install failed."
    fi
else
    log "Frontend dependencies already installed."
fi

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
    die "Vite is still unavailable after npm dependency setup."
fi

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

export MONGO_URI
export DATABASE_NAME="soar_rl_agent"
export PYTHONPATH="$ROOT_DIR/backend:$ROOT_DIR"

log "Python: $PYTHON"
log "npm: $NPM"
log "Backend: http://127.0.0.1:$BACKEND_PORT"
log "Frontend: http://127.0.0.1:$FRONTEND_PORT"
log "MongoDB: $MONGO_URI"

# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

"$PYTHON" -m uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    >/tmp/rl_agent_backend.log 2>&1 &

BACKEND_PID=$!

log "Backend process started (PID=$BACKEND_PID)"

BACKEND_READY=0

for _ in {1..40}; do
    if curl -fsS \
        "http://127.0.0.1:$BACKEND_PORT/api/training-control" \
        >/dev/null 2>&1
    then
        BACKEND_READY=1
        break
    fi

    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        echo
        echo "============================================================"
        echo " BACKEND FAILED"
        echo "============================================================"
        cat /tmp/rl_agent_backend.log 2>/dev/null || true
        die "Backend exited before becoming ready."
    fi

    sleep 0.25
done

if [[ "$BACKEND_READY" -ne 1 ]]; then
    echo
    cat /tmp/rl_agent_backend.log 2>/dev/null || true
    die "Backend did not become ready on port $BACKEND_PORT."
fi

log "Backend is ready."

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

cd "$ROOT_DIR/frontend"

"$NPM" run dev -- \
    --host 0.0.0.0 \
    --port "$FRONTEND_PORT" \
    >/tmp/rl_agent_frontend.log 2>&1 &

FRONTEND_PID=$!

log "Frontend process started (PID=$FRONTEND_PID)"

FRONTEND_READY=0

for _ in {1..40}; do
    if curl -fsS \
        "http://127.0.0.1:$FRONTEND_PORT/" \
        >/dev/null 2>&1
    then
        FRONTEND_READY=1
        break
    fi

    if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
        echo
        echo "============================================================"
        echo " FRONTEND FAILED"
        echo "============================================================"
        cat /tmp/rl_agent_frontend.log 2>/dev/null || true
        die "Frontend exited before becoming ready."
    fi

    sleep 0.25
done

if [[ "$FRONTEND_READY" -ne 1 ]]; then
    echo
    cat /tmp/rl_agent_frontend.log 2>/dev/null || true
    die "Frontend did not become ready on port $FRONTEND_PORT."
fi

echo
echo "============================================================"
echo " LOCAL PROJECT STARTED SUCCESSFULLY"
echo "============================================================"
echo "Backend : http://127.0.0.1:$BACKEND_PORT"
echo "Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo "MongoDB : $MONGO_URI"
echo
echo "Backend log : /tmp/rl_agent_backend.log"
echo "Frontend log: /tmp/rl_agent_frontend.log"
echo
echo "Press CTRL+C to stop both services."
echo "============================================================"

wait
