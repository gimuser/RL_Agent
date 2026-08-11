#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
MONGO_URI="${MONGO_URI:-mongodb://127.0.0.1:27017}"
PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python3}"
NPM="${NPM:-$(command -v npm || true)}"

log() {
  printf '\n==> %s\n' "$1"
}

die() {
  printf '\nERROR: %s\n' "$1" >&2
  exit 1
}

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "$PYTHON" ]]; then
  log "Local venv Python not found at $PYTHON; falling back to system python3"
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON" ]]; then
  die "Python 3 is not available. Install Python 3 or set PYTHON to a valid interpreter."
fi
if ! "$PYTHON" --version >/dev/null 2>&1; then
  die "Python 3 is not available. Install Python 3 or set PYTHON to a valid interpreter."
fi
if [[ -z "$NPM" ]]; then
  die "npm is not installed. Install Node.js and npm to start the frontend."
fi
if [[ ! -f "$ROOT_DIR/frontend/package.json" ]]; then
  die "Could not find frontend/package.json. Run this script from the project root."
fi

log "Starting local backend and frontend"
log "Backend port: $BACKEND_PORT"
log "Frontend port: $FRONTEND_PORT"
log "Mongo URI: $MONGO_URI"

export MONGO_URI
export DATABASE_NAME="soar_rl_agent"

cd "$ROOT_DIR"
"$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port "$BACKEND_PORT" >/tmp/rl_agent_backend.log 2>&1 &
BACKEND_PID=$!
log "Backend started (PID=$BACKEND_PID)"

cd "$ROOT_DIR/frontend"
"$NPM" run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" >/tmp/rl_agent_frontend.log 2>&1 &
FRONTEND_PID=$!
log "Frontend started (PID=$FRONTEND_PID)"

log "Local project started successfully."
log "Backend: http://127.0.0.1:$BACKEND_PORT"
log "Frontend: http://127.0.0.1:$FRONTEND_PORT"
log "Press CTRL+C to stop both services."

wait
