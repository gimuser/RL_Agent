#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$HOME/Desktop/RL_AGENT"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="$BACKEND/.venv/bin/python"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo
    echo "============================================================"
    echo "CLEANUP"
    echo "============================================================"

    if [[ -n "${FRONTEND_PID:-}" ]]; then
        echo "Stopping frontend PID $FRONTEND_PID"
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi

    if [[ -n "${BACKEND_PID:-}" ]]; then
        echo "Stopping backend PID $BACKEND_PID"
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT

echo
echo "============================================================"
echo "FINAL FRONTEND <-> BACKEND INTEGRATION SMOKE TEST"
echo "============================================================"

cd "$ROOT"

###############################################################################
# 1. VERIFY EXISTING FILES
###############################################################################

echo
echo "============================================================"
echo "1. VERIFYING INTEGRATION FILES"
echo "============================================================"

for f in \
    backend/main.py \
    backend/app/api/router.py \
    backend/app/api/training.py \
    backend/app/api/dashboard.py \
    backend/app/api/health.py \
    frontend/vite.config.ts \
    frontend/src/services/api.ts \
    frontend/src/services/training.service.ts \
    frontend/src/services/dashboard.service.ts \
    frontend/src/services/decisions.service.ts \
    frontend/src/pages/Training.tsx \
    frontend/src/pages/History.tsx \
    frontend/src/pages/Dashboard.tsx \
    frontend/src/pages/Decisions.tsx
do
    if [[ -f "$ROOT/$f" ]]; then
        echo "[OK] $f"
    else
        echo "[FAIL] Missing $f"
        exit 1
    fi
done

###############################################################################
# 2. VERIFY REAL API BASE CONFIG
###############################################################################

echo
echo "============================================================"
echo "2. VERIFYING FRONTEND API CONFIG"
echo "============================================================"

grep -nE \
    'VITE_API_BASE_URL|VITE_USE_MOCKS' \
    frontend/.env frontend/.env.example 2>/dev/null || true

if grep -Eq \
    '^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=[[:space:]]*true' \
    frontend/.env 2>/dev/null
then
    echo "[FAIL] VITE_USE_MOCKS=true"
    exit 1
else
    echo "[OK] Frontend mock mode is disabled"
fi

if grep -Fq \
    'const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\\/$/, "");' \
    frontend/src/services/api.ts
then
    echo "[OK] Frontend uses VITE_API_BASE_URL with same-origin fallback"
else
    echo "[WARN] API base implementation differs from expected pattern"
fi

###############################################################################
# 3. VERIFY VITE PROXY
###############################################################################

echo
echo "============================================================"
echo "3. VERIFYING VITE /api PROXY"
echo "============================================================"

if grep -nE \
    'proxy:|"/api"|localhost:8000|127.0.0.1:8000' \
    frontend/vite.config.ts
then
    echo "[OK] Vite /api proxy configuration found"
else
    echo "[FAIL] Vite /api proxy configuration not found"
    exit 1
fi

###############################################################################
# 4. BUILD FRONTEND
###############################################################################

echo
echo "============================================================"
echo "4. BUILDING FRONTEND"
echo "============================================================"

(
    cd "$FRONTEND"
    npm run build
)

echo "[OK] Frontend production build passed"

###############################################################################
# 5. START BACKEND
###############################################################################

echo
echo "============================================================"
echo "5. STARTING BACKEND"
echo "============================================================"

(
    cd "$BACKEND"
    export PYTHONPATH="$ROOT/backend:$ROOT"

    exec "$PYTHON" -m uvicorn main:app \
        --host 127.0.0.1 \
        --port 8000 \
        --log-level warning
) > /tmp/rl_agent_backend_smoke.log 2>&1 &

BACKEND_PID=$!

for _ in {1..40}; do
    if curl -fsS \
        http://127.0.0.1:8000/api/system/health \
        >/dev/null 2>&1
    then
        echo "[OK] Backend ready on :8000"
        break
    fi

    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "[FAIL] Backend stopped unexpectedly"
        cat /tmp/rl_agent_backend_smoke.log
        exit 1
    fi

    sleep 0.25
done

if ! curl -fsS \
    http://127.0.0.1:8000/api/system/health \
    >/dev/null
then
    echo "[FAIL] Backend health unavailable"
    cat /tmp/rl_agent_backend_smoke.log
    exit 1
fi

###############################################################################
# 6. START VITE DEV SERVER
###############################################################################

echo
echo "============================================================"
echo "6. STARTING VITE DEV SERVER"
echo "============================================================"

(
    cd "$FRONTEND"

    exec npm run dev -- \
        --host 127.0.0.1 \
        --port 5173
) > /tmp/rl_agent_frontend_smoke.log 2>&1 &

FRONTEND_PID=$!

for _ in {1..40}; do
    if curl -fsS \
        http://127.0.0.1:5173 \
        >/dev/null 2>&1
    then
        echo "[OK] Vite ready on :5173"
        break
    fi

    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "[FAIL] Vite stopped unexpectedly"
        cat /tmp/rl_agent_frontend_smoke.log
        exit 1
    fi

    sleep 0.25
done

if ! curl -fsS \
    http://127.0.0.1:5173 \
    >/dev/null
then
    echo "[FAIL] Vite server unavailable"
    cat /tmp/rl_agent_frontend_smoke.log
    exit 1
fi

###############################################################################
# 7. TEST ACTUAL FRONTEND -> BACKEND PROXY
###############################################################################

echo
echo "============================================================"
echo "7. TESTING FRONTEND -> BACKEND /api PROXY"
echo "============================================================"

declare -a proxy_paths=(
    "/api/system/health"
    "/api/training/status"
    "/api/training/history"
    "/api/training/checkpoints"
    "/api/training/metrics"
    "/api/training/full-real-training/status"
    "/api/decisions"
    "/api/dashboard/summary"
)

PROXY_FAILURES=0

for path in "${proxy_paths[@]}"; do

    body="$(mktemp)"

    status="$(
        curl -sS \
            -o "$body" \
            -w "%{http_code}" \
            "http://127.0.0.1:5173${path}" \
            || true
    )"

    echo
    echo "$path -> HTTP $status"

    if [[ "$status" == "200" ]]; then
        echo "[OK] Frontend proxy -> backend works"
        head -c 500 "$body"
        echo
    else
        echo "[FAIL] Frontend proxy failed"
        cat "$body" || true
        PROXY_FAILURES=$((PROXY_FAILURES + 1))
    fi

    rm -f "$body"
done

if [[ "$PROXY_FAILURES" -ne 0 ]]; then
    exit 1
fi

###############################################################################
# 8. VERIFY TRAINING PAGE USES REAL ENDPOINT
###############################################################################

echo
echo "============================================================"
echo "8. VERIFYING TRAINING PAGE"
echo "============================================================"

if grep -q \
    'getAuthoritativeFullTrainingStatus' \
    frontend/src/pages/Training.tsx
then
    echo "[OK] Training page reads real training status"
else
    echo "[FAIL] Training page does not read authoritative training status"
    exit 1
fi

if grep -q \
    'startAuthoritativeFullTraining' \
    frontend/src/pages/Training.tsx
then
    echo "[OK] Training page starts real full-data training endpoint"
else
    echo "[FAIL] Training page does not start authoritative training endpoint"
    exit 1
fi

###############################################################################
# 9. VERIFY HISTORY PAGE
###############################################################################

echo
echo "============================================================"
echo "9. VERIFYING HISTORY PAGE"
echo "============================================================"

for endpoint in \
    "/api/alerts" \
    "/api/decisions" \
    "/api/rewards"
do
    if grep -Fq "$endpoint" frontend/src/pages/History.tsx; then
        echo "[OK] History page consumes $endpoint"
    else
        echo "[FAIL] History page missing $endpoint"
        exit 1
    fi
done

if grep -q \
    'getAuthoritativeFullTrainingStatus' \
    frontend/src/pages/History.tsx
then
    echo "[OK] History page consumes authoritative training results"
else
    echo "[FAIL] History page missing authoritative training status"
    exit 1
fi

###############################################################################
# 10. VERIFY DASHBOARD
###############################################################################

echo
echo "============================================================"
echo "10. VERIFYING DASHBOARD"
echo "============================================================"

if grep -Fq \
    'getSummary' \
    frontend/src/services/dashboard.service.ts
then
    echo "[OK] Dashboard service uses /api/dashboard/summary"
else
    echo "[FAIL] Dashboard summary service missing"
    exit 1
fi

if grep -q \
    'dashboardService' \
    frontend/src/pages/Dashboard.tsx
then
    echo "[OK] Dashboard page uses dashboard service"
else
    echo "[WARN] Dashboard page wiring is not obvious from static search"
fi

###############################################################################
# 11. VERIFY DECISIONS
###############################################################################

echo
echo "============================================================"
echo "11. VERIFYING DECISIONS"
echo "============================================================"

if grep -Fq \
    '/api/decisions' \
    frontend/src/services/decisions.service.ts
then
    echo "[OK] Decisions service uses real backend endpoint"
else
    echo "[FAIL] Decisions service missing real endpoint"
    exit 1
fi

if grep -q \
    'decisionsService' \
    frontend/src/pages/Decisions.tsx
then
    echo "[OK] Decisions page uses decisions service"
else
    echo "[WARN] Decisions page wiring is not obvious from static search"
fi

###############################################################################
# 12. CHECK CURRENT BACKEND/FRONTEND STATUS CONSISTENCY
###############################################################################

echo
echo "============================================================"
echo "12. CHECKING TRAINING STATUS CONSISTENCY"
echo "============================================================"

backend_training="$(
    curl -fsS \
    http://127.0.0.1:5173/api/training/status
)"

full_training="$(
    curl -fsS \
    http://127.0.0.1:5173/api/training/full-real-training/status
)"

echo "Training status:"
echo "$backend_training"

echo
echo "Full training status:"
echo "$full_training"

if echo "$backend_training" | grep -q '"status":"completed"'; then
    echo "[OK] /api/training/status reports completed"
else
    echo "[WARN] /api/training/status is not completed"
fi

if echo "$full_training" | grep -q '"status":"completed"'; then
    echo "[OK] /api/training/full-real-training/status reports completed"
else
    echo "[WARN] Full training status is not completed"
fi

###############################################################################
# 13. IMPORTANT DASHBOARD NOTE
###############################################################################

echo
echo "============================================================"
echo "13. DASHBOARD TRAINING STATUS NOTE"
echo "============================================================"

dashboard_response="$(
    curl -fsS \
    http://127.0.0.1:5173/api/dashboard/summary
)"

echo "$dashboard_response"

if echo "$dashboard_response" | grep -q \
    '"training_status":"not_trained"'
then
    echo
    echo "[WARN] Dashboard summary says training_status=not_trained"
    echo "[WARN] while /api/training/status reports the real model as completed."
    echo
    echo "[ACTION] This is a backend/dashboard data-contract mismatch."
    echo "[ACTION] The training page can still show the authoritative real result."
else
    echo "[OK] Dashboard training status is not contradictory"
fi

###############################################################################
# 14. FINAL
###############################################################################

echo
echo "============================================================"
echo "FINAL RESULT"
echo "============================================================"

echo "[OK] Backend is reachable"
echo "[OK] Frontend is reachable"
echo "[OK] Vite /api proxy reaches FastAPI"
echo "[OK] Training page is connected to real training endpoints"
echo "[OK] History page is connected to real backend records"
echo "[OK] Decisions page has real API service"
echo "[OK] Dashboard has real API service"
echo "[OK] TypeScript build passes"
echo "[OK] No training was started"
echo "[OK] No RL artifact was modified"

echo
echo "URLs:"
echo "  Frontend: http://127.0.0.1:5173"
echo "  Backend : http://127.0.0.1:8000"
echo
echo "Open the frontend at:"
echo "  http://127.0.0.1:5173"

exit 0
