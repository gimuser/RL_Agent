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
BACKEND_LOG="/tmp/rl_agent_backend.log"
FRONTEND_LOG="/tmp/rl_agent_frontend.log"

die() { echo "ERROR: $1" >&2; exit 1; }
cleanup() {
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

[[ -n "$PYTHON" ]] || die "python3 not found."
[[ -n "$NPM" ]] || die "npm not found."
[[ -f "$ROOT_DIR/backend/main.py" ]] || die "backend/main.py not found."
[[ -f "$ROOT_DIR/frontend/package.json" ]] || die "frontend/package.json not found."

if ss -ltn 2>/dev/null | grep -q ":${BACKEND_PORT} "; then
    die "Backend port $BACKEND_PORT is already in use."
fi
if ss -ltn 2>/dev/null | grep -q ":${FRONTEND_PORT} "; then
    die "Frontend port $FRONTEND_PORT is already in use."
fi

if [[ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ]]; then
    (
        cd "$ROOT_DIR/frontend"
        if [[ -f package-lock.json ]]; then "$NPM" ci; else "$NPM" install; fi
    ) || die "Frontend dependency installation failed."
fi

export MONGO_URI
export DATABASE_NAME="soar_rl_agent"
export PYTHONPATH="$ROOT_DIR/backend:$ROOT_DIR"

rm -f "$BACKEND_LOG" "$FRONTEND_LOG"

"$PYTHON" -m uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

BACKEND_READY=0
for _ in {1..120}; do
    if curl -fsS --connect-timeout 1 --max-time 2 \
        "http://127.0.0.1:$BACKEND_PORT/" >/dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        cat "$BACKEND_LOG" >&2 || true
        die "Backend exited before becoming ready."
    fi
    sleep 0.5
done
[[ "$BACKEND_READY" -eq 1 ]] || { tail -n 100 "$BACKEND_LOG" >&2 || true; die "Backend did not become ready within 60 seconds."; }

(
    cd "$ROOT_DIR/frontend"
    "$NPM" run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

FRONTEND_READY=0
for _ in {1..60}; do
    if curl -fsS --connect-timeout 1 --max-time 2 \
        "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
        FRONTEND_READY=1
        break
    fi
    if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
        cat "$FRONTEND_LOG" >&2 || true
        die "Frontend exited before becoming ready."
    fi
    sleep 0.5
done
[[ "$FRONTEND_READY" -eq 1 ]] || { tail -n 100 "$FRONTEND_LOG" >&2 || true; die "Frontend did not become ready within 30 seconds."; }

echo "============================================================"
echo "RL_Agent READY"
echo "============================================================"
echo "Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo "Backend : http://127.0.0.1:$BACKEND_PORT"
echo "============================================================"
echo "Press CTRL+C to stop."

wait
