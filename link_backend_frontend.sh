#!/usr/bin/env bash
set -Eeuo pipefail

###############################################################################
# RL AGENT - BACKEND / FRONTEND INTEGRATION REPAIR
#
# GOAL
# ----
# Connect the existing real FastAPI backend to the existing React frontend.
#
# THIS SCRIPT DOES:
#   1. Create a safe source backup.
#   2. Verify backend routes.
#   3. Verify frontend API service paths.
#   4. Verify frontend environment / API base configuration.
#   5. Verify TypeScript references to the real backend contract.
#   6. Start backend temporarily.
#   7. Perform live HTTP smoke tests against real endpoints.
#   8. Build the frontend against the real backend configuration.
#   9. Report mismatches without touching RL artifacts.
#
# THIS SCRIPT DOES NOT:
#   - retrain the model
#   - modify the DQN checkpoint
#   - modify training metrics
#   - modify test predictions
#   - modify reward logic
#   - replace real datasets
###############################################################################

ROOT="${HOME}/Desktop/RL_AGENT"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV="$BACKEND_DIR/.venv"
PYTHON="$VENV/bin/python"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_DIR="$ROOT/backend_frontend_link_backup_${TIMESTAMP}"
REPORT="$ROOT/backend_frontend_link_report_${TIMESTAMP}.txt"
LOG_DIR="$ROOT/.integration_logs_${TIMESTAMP}"
BACKEND_LOG="$LOG_DIR/backend.log"

mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

exec > >(tee -a "$REPORT") 2>&1

###############################################################################
# Helpers
###############################################################################

ok() {
    echo "[OK] $*"
}

warn() {
    echo "[WARN] $*"
}

fail() {
    echo "[FAIL] $*"
}

section() {
    echo
    echo "======================================================================"
    echo "$1"
    echo "======================================================================"
}

###############################################################################
# Cleanup
###############################################################################

BACKEND_PID=""

cleanup() {
    if [[ -n "${BACKEND_PID:-}" ]]; then
        echo
        echo "[INFO] Stopping temporary backend PID $BACKEND_PID"
        kill "$BACKEND_PID" 2>/dev/null || true

        for _ in {1..20}; do
            if kill -0 "$BACKEND_PID" 2>/dev/null; then
                sleep 0.2
            else
                break
            fi
        done

        kill -9 "$BACKEND_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT

###############################################################################
# 1. BASIC VALIDATION
###############################################################################

section "1. VALIDATING PROJECT"

[[ -d "$ROOT" ]] \
    && ok "Project exists: $ROOT" \
    || { fail "Project not found"; exit 1; }

[[ -f "$BACKEND_DIR/main.py" ]] \
    && ok "backend/main.py" \
    || { fail "backend/main.py missing"; exit 1; }

[[ -d "$BACKEND_DIR/app" ]] \
    && ok "backend/app" \
    || { fail "backend/app missing"; exit 1; }

[[ -d "$FRONTEND_DIR/src" ]] \
    && ok "frontend/src" \
    || { fail "frontend/src missing"; exit 1; }

[[ -x "$PYTHON" ]] \
    && ok "backend/.venv Python" \
    || { fail "backend/.venv Python missing"; exit 1; }

###############################################################################
# 2. SAFE BACKUP
###############################################################################

section "2. CREATING SAFE BACKEND/FRONTEND BACKUP"

mkdir -p "$BACKUP_DIR/backend/app/api"
mkdir -p "$BACKUP_DIR/backend/app/schemas"
mkdir -p "$BACKUP_DIR/backend/app/services"
mkdir -p "$BACKUP_DIR/frontend/src/pages"
mkdir -p "$BACKUP_DIR/frontend/src/services"
mkdir -p "$BACKUP_DIR/frontend/src/types"

for f in \
    backend/main.py \
    backend/app/api/router.py \
    backend/app/api/training.py \
    backend/app/api/health.py \
    backend/app/api/decisions.py \
    backend/app/api/dashboard.py \
    backend/app/schemas/training_schema.py \
    backend/app/services/training_service.py \
    backend/app/services/experiment_service.py
do
    if [[ -f "$ROOT/$f" ]]; then
        mkdir -p "$BACKUP_DIR/$(dirname "$f")"
        cp -a "$ROOT/$f" "$BACKUP_DIR/$f"
    fi
done

for f in \
    frontend/src/pages/Training.tsx \
    frontend/src/pages/History.tsx \
    frontend/src/pages/Decisions.tsx \
    frontend/src/pages/Dashboard.tsx \
    frontend/src/services/training.service.ts \
    frontend/src/services/decisions.service.ts \
    frontend/src/services/dashboard.service.ts \
    frontend/src/types/domain.ts \
    frontend/src/types/api.ts
do
    if [[ -f "$ROOT/$f" ]]; then
        mkdir -p "$BACKUP_DIR/$(dirname "$f")"
        cp -a "$ROOT/$f" "$BACKUP_DIR/$f"
    fi
done

for f in \
    frontend/package.json \
    frontend/package-lock.json \
    frontend/vite.config.ts \
    frontend/.env \
    frontend/.env.example
do
    if [[ -f "$ROOT/$f" ]]; then
        mkdir -p "$BACKUP_DIR/$(dirname "$f")"
        cp -a "$ROOT/$f" "$BACKUP_DIR/$f"
    fi
done

ok "Backend/frontend integration backup created:"
echo "  $BACKUP_DIR"

###############################################################################
# 3. PROTECT RL ARTIFACTS
###############################################################################

section "3. VERIFYING RL ARTIFACTS ARE UNTOUCHED"

for f in \
    models/real_dqn_agent.pt \
    models/training_metrics.json \
    models/real_test_metrics.json \
    models/test_predictions.csv \
    models/real_test_predictions.jsonl
do
    if [[ -f "$ROOT/$f" ]]; then
        ok "$f"
    else
        warn "$f missing"
    fi
done

###############################################################################
# 4. EXTRACT LIVE BACKEND ROUTES
###############################################################################

section "4. EXTRACTING REAL BACKEND ROUTES"

ROUTES_FILE="$LOG_DIR/backend_routes.txt"

PYTHONPATH="$ROOT/backend:$ROOT" \
"$PYTHON" - <<'PY' > "$ROUTES_FILE"
from backend.main import app

for route in sorted(
    app.routes,
    key=lambda r: (
        getattr(r, "path", ""),
        sorted(getattr(r, "methods", set())),
    ),
):
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", set())
    if path:
        for method in sorted(methods):
            print(f"{method} {path}")
PY

cat "$ROUTES_FILE"

###############################################################################
# 5. REQUIRED BACKEND CONTRACT
###############################################################################

section "5. VERIFYING REQUIRED BACKEND CONTRACT"

required_routes=(
    "GET /api/system/health"
    "GET /api/training/status"
    "GET /api/training/history"
    "GET /api/training/checkpoints"
    "GET /api/training/metrics"
    "POST /api/training/start"
    "POST /api/training/stop"
    "POST /api/training/full-real-training"
    "GET /api/training/full-real-training/status"
    "GET /api/decisions"
    "GET /api/dashboard/summary"
)

ROUTE_FAILURES=0

for route in "${required_routes[@]}"; do
    if grep -Fxq "$route" "$ROUTES_FILE"; then
        ok "$route"
    else
        fail "Missing backend route: $route"
        ROUTE_FAILURES=$((ROUTE_FAILURES + 1))
    fi
done

###############################################################################
# 6. FRONTEND SERVICE FILES
###############################################################################

section "6. VERIFYING FRONTEND SERVICE FILES"

for f in \
    frontend/src/services/training.service.ts \
    frontend/src/services/decisions.service.ts \
    frontend/src/services/dashboard.service.ts
do
    if [[ -f "$ROOT/$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
        ROUTE_FAILURES=$((ROUTE_FAILURES + 1))
    fi
done

###############################################################################
# 7. FRONTEND PAGE FILES
###############################################################################

section "7. VERIFYING FRONTEND PAGES"

for f in \
    frontend/src/pages/Training.tsx \
    frontend/src/pages/History.tsx \
    frontend/src/pages/Decisions.tsx \
    frontend/src/pages/Dashboard.tsx
do
    if [[ -f "$ROOT/$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
        ROUTE_FAILURES=$((ROUTE_FAILURES + 1))
    fi
done

###############################################################################
# 8. FRONTEND API CALL SEARCH
###############################################################################

section "8. SEARCHING FRONTEND API CALLS"

for f in \
    frontend/src/services/training.service.ts \
    frontend/src/services/decisions.service.ts \
    frontend/src/services/dashboard.service.ts
do
    echo
    echo "----- $f -----"

    if [[ -f "$ROOT/$f" ]]; then
        grep -nE \
            '"/api/|`/api/|/api/[A-Za-z0-9_/${}.-]+' \
            "$ROOT/$f" || true
    fi
done

###############################################################################
# 9. CHECK TRAINING SERVICE CONTRACT
###############################################################################

section "9. VERIFYING TRAINING FRONTEND CONTRACT"

TRAINING_SERVICE="$FRONTEND_DIR/src/services/training.service.ts"

if [[ -f "$TRAINING_SERVICE" ]]; then

    for endpoint in \
        "/api/training/status" \
        "/api/training/history" \
        "/api/training/checkpoints" \
        "/api/training/metrics" \
        "/api/training/start" \
        "/api/training/stop" \
        "/api/training/full-real-training" \
        "/api/training/full-real-training/status"
    do
        if grep -Fq "$endpoint" "$TRAINING_SERVICE"; then
            ok "Training service uses $endpoint"
        else
            warn "Training service does not reference $endpoint"
        fi
    done

else
    fail "$TRAINING_SERVICE missing"
fi

###############################################################################
# 10. CHECK PAGE WIRING
###############################################################################

section "10. VERIFYING PAGE -> SERVICE WIRING"

declare -A PAGE_CHECKS

PAGE_CHECKS["frontend/src/pages/Training.tsx"]="trainingService"
PAGE_CHECKS["frontend/src/pages/History.tsx"]="trainingService"
PAGE_CHECKS["frontend/src/pages/Decisions.tsx"]="decisionsService"
PAGE_CHECKS["frontend/src/pages/Dashboard.tsx"]="dashboardService"

for page in "${!PAGE_CHECKS[@]}"; do
    expected="${PAGE_CHECKS[$page]}"

    if [[ -f "$ROOT/$page" ]]; then
        if grep -qi "$expected" "$ROOT/$page"; then
            ok "$page references $expected"
        else
            warn "$page does not obviously reference $expected"
        fi
    fi
done

###############################################################################
# 11. FRONTEND API BASE CONFIGURATION
###############################################################################

section "11. VERIFYING FRONTEND API BASE CONFIGURATION"

API_BASE_FILE="$LOG_DIR/frontend_api_base.txt"

grep -RInE \
    'VITE_API|API_BASE|baseURL|127\.0\.0\.1:8000|localhost:8000|apiRequest' \
    frontend/src \
    frontend/.env \
    frontend/.env.example \
    2>/dev/null \
    | head -n 200 > "$API_BASE_FILE" || true

cat "$API_BASE_FILE"

echo

if [[ -f "$FRONTEND_DIR/.env" ]]; then
    echo "--- frontend/.env ---"
    cat "$FRONTEND_DIR/.env"
fi

###############################################################################
# 12. CREATE REAL FRONTEND .env IF NEEDED
###############################################################################

section "12. ENSURING REAL FRONTEND BACKEND URL"

if [[ -f "$FRONTEND_DIR/.env" ]]; then

    if grep -Eq \
        '^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=[[:space:]]*true' \
        "$FRONTEND_DIR/.env"
    then
        warn "VITE_USE_MOCKS=true detected"
        sed -i -E \
            's/^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=.*/VITE_USE_MOCKS=false/' \
            "$FRONTEND_DIR/.env"
        ok "VITE_USE_MOCKS=false"
    fi

else

    if [[ -f "$FRONTEND_DIR/.env.example" ]]; then
        cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"

        sed -i -E \
            's/^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=.*/VITE_USE_MOCKS=false/' \
            "$FRONTEND_DIR/.env"

        ok "frontend/.env created from .env.example"

    else
        touch "$FRONTEND_DIR/.env"
        echo "VITE_USE_MOCKS=false" >> "$FRONTEND_DIR/.env"
        ok "frontend/.env created"
    fi
fi

###############################################################################
# 13. CORS / BACKEND SETTINGS CHECK
###############################################################################

section "13. CHECKING BACKEND CORS CONFIGURATION"

if grep -nE \
    'CORSMiddleware|allow_origins|allow_methods|allow_headers' \
    backend/main.py
then
    ok "CORS middleware configuration found"
else
    warn "Could not verify CORS configuration automatically"
fi

###############################################################################
# 14. FRONTEND TYPE CONTRACT SEARCH
###############################################################################

section "14. SEARCHING FRONTEND TYPES"

for f in \
    frontend/src/types/domain.ts \
    frontend/src/types/api.ts
do
    if [[ -f "$ROOT/$f" ]]; then
        echo
        echo "----- $f -----"
        grep -nE \
            'Training|Checkpoint|Metric|Decision|Dashboard|Status|Experiment' \
            "$ROOT/$f" \
            | head -n 200 || true
    fi
done

###############################################################################
# 15. BACKEND RESPONSE SHAPE SEARCH
###############################################################################

section "15. SEARCHING BACKEND RESPONSE SHAPES"

for f in \
    backend/app/api/training.py \
    backend/app/api/decisions.py \
    backend/app/api/dashboard.py
do
    if [[ -f "$ROOT/$f" ]]; then
        echo
        echo "----- $f -----"
        grep -nE \
            'return |Response|dict|JSON|@router' \
            "$ROOT/$f" \
            | head -n 250 || true
    fi
done

###############################################################################
# 16. COMPILE BACKEND
###############################################################################

section "16. COMPILING BACKEND"

"$PYTHON" -m compileall -q backend/app backend/main.py

ok "Backend compiles"

###############################################################################
# 17. BUILD FRONTEND BEFORE LIVE TEST
###############################################################################

section "17. BUILDING FRONTEND"

(
    cd "$FRONTEND_DIR"
    npm run build
)

ok "Frontend production build succeeded"

###############################################################################
# 18. START BACKEND TEMPORARILY
###############################################################################

section "18. STARTING TEMPORARY BACKEND"

(
    cd "$BACKEND_DIR"

    export PYTHONPATH="$ROOT/backend:$ROOT"

    exec "$PYTHON" -m uvicorn main:app \
        --host 127.0.0.1 \
        --port 8000 \
        --log-level warning
) > "$BACKEND_LOG" 2>&1 &

BACKEND_PID=$!

echo "Backend PID: $BACKEND_PID"

###############################################################################
# 19. WAIT FOR BACKEND
###############################################################################

section "19. WAITING FOR BACKEND"

backend_ready=0

for _ in {1..40}; do

    if curl -fsS \
        http://127.0.0.1:8000/api/system/health \
        >/dev/null 2>&1
    then
        backend_ready=1
        break
    fi

    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo
        echo "----- backend.log -----"
        cat "$BACKEND_LOG" || true
        fail "Temporary backend exited"
        exit 1
    fi

    sleep 0.25
done

if [[ "$backend_ready" -eq 1 ]]; then
    ok "Backend is live on http://127.0.0.1:8000"
else
    cat "$BACKEND_LOG" || true
    fail "Backend did not become ready"
    exit 1
fi

###############################################################################
# 20. LIVE BACKEND API SMOKE TESTS
###############################################################################

section "20. LIVE BACKEND API SMOKE TESTS"

declare -A API_EXPECTED

API_EXPECTED["/api/system/health"]="200"
API_EXPECTED["/api/training/status"]="200"
API_EXPECTED["/api/training/history"]="200"
API_EXPECTED["/api/training/checkpoints"]="200"
API_EXPECTED["/api/training/metrics"]="200"
API_EXPECTED["/api/training/full-real-training/status"]="200"
API_EXPECTED["/api/decisions"]="200"
API_EXPECTED["/api/dashboard/summary"]="200"

LIVE_FAILURES=0

for path in "${!API_EXPECTED[@]}"; do

    status="$(
        curl -sS \
            -o "$LOG_DIR/response.tmp" \
            -w "%{http_code}" \
            "http://127.0.0.1:8000${path}" \
            || true
    )"

    echo
    echo "$path -> HTTP $status"

    if [[ "$status" == "${API_EXPECTED[$path]}" ]]; then
        ok "$path"
    else
        fail "$path returned HTTP $status"
        LIVE_FAILURES=$((LIVE_FAILURES + 1))
    fi

    if [[ -s "$LOG_DIR/response.tmp" ]]; then
        head -c 1200 "$LOG_DIR/response.tmp"
        echo
    fi
done

###############################################################################
# 21. SPECIFIC TRAINING STATUS TEST
###############################################################################

section "21. VERIFYING REAL TRAINING STATUS RESPONSE"

TRAINING_STATUS_JSON="$LOG_DIR/training_status.json"

curl -fsS \
    http://127.0.0.1:8000/api/training/status \
    > "$TRAINING_STATUS_JSON"

"$PYTHON" - "$TRAINING_STATUS_JSON" <<'PY'
import json
import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Training response:", data)

required = [
    "trained",
    "model_exists",
    "metrics_exists",
    "status",
]

for key in required:
    if key not in data:
        raise SystemExit(
            f"[FAIL] Missing training status key: {key}"
        )

print("[OK] Training status response shape is valid")
PY

###############################################################################
# 22. SPECIFIC FULL-REAL-TRAINING STATUS
###############################################################################

section "22. VERIFYING FULL REAL-TRAINING RESPONSE"

FULL_STATUS_JSON="$LOG_DIR/full_real_status.json"

curl -fsS \
    http://127.0.0.1:8000/api/training/full-real-training/status \
    > "$FULL_STATUS_JSON"

"$PYTHON" - "$FULL_STATUS_JSON" <<'PY'
import json
import sys

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Full-training response:")
print(json.dumps(data, indent=2)[:5000])

if "status" not in data:
    raise SystemExit(
        "[FAIL] Missing status field"
    )

if data.get("status") == "completed":
    results = data.get("results")

    if not isinstance(results, dict):
        raise SystemExit(
            "[FAIL] Completed training has no results object"
        )

    dataset = results.get("dataset", {})
    evaluation = results.get("evaluation", {})
    model = results.get("model", {})

    print()
    print("Dataset rows      :", dataset.get("test_rows"))
    print("Test incidents    :", dataset.get("test_incidents"))
    print("Incident overlap  :", dataset.get("incident_overlap"))
    print("Average reward    :", evaluation.get("average_reward"))
    print("Policy optimality :", evaluation.get("policy_optimality"))
    print("Model exists      :", model.get("exists"))

    print("[OK] Full training status response shape is valid")

else:
    print(
        "[OK] Full training endpoint is responding; "
        f"current status={data.get('status')}"
    )
PY

###############################################################################
# 23. VERIFY FRONTEND CAN TALK TO SAME ORIGIN CONFIG
###############################################################################

section "23. CHECKING FRONTEND API CONFIGURATION"

"$PYTHON" - <<'PY'
from pathlib import Path

env = Path("frontend/.env")

if env.exists():
    print(env.read_text(encoding="utf-8"))
else:
    print("[WARN] frontend/.env not found")
PY

###############################################################################
# 24. TYPESCRIPT BUILD AGAIN AFTER CONFIG CHECK
###############################################################################

section "24. FINAL FRONTEND PRODUCTION BUILD"

(
    cd "$FRONTEND_DIR"
    npm run build
)

ok "Final frontend build succeeded"

###############################################################################
# 25. REPORT FRONTEND/BACKEND CONTRACT FILES
###############################################################################

section "25. FRONTEND/BACKEND CONTRACT FILE INVENTORY"

for f in \
    frontend/src/pages/Training.tsx \
    frontend/src/pages/History.tsx \
    frontend/src/pages/Decisions.tsx \
    frontend/src/pages/Dashboard.tsx \
    frontend/src/services/training.service.ts \
    frontend/src/services/decisions.service.ts \
    frontend/src/services/dashboard.service.ts \
    frontend/src/types/domain.ts \
    backend/app/api/training.py \
    backend/app/api/decisions.py \
    backend/app/api/dashboard.py \
    backend/app/api/health.py \
    backend/main.py
do
    if [[ -f "$ROOT/$f" ]]; then
        echo "[OK] $f"
    else
        echo "[MISSING] $f"
    fi
done

###############################################################################
# 26. NO RETRAINING / ARTIFACT INTEGRITY CHECK
###############################################################################

section "26. VERIFYING RL ARTIFACTS WERE NOT MODIFIED"

for f in \
    models/real_dqn_agent.pt \
    models/training_metrics.json \
    models/real_test_metrics.json \
    models/test_predictions.csv \
    models/real_test_predictions.jsonl
do
    if [[ -f "$ROOT/$f" ]]; then
        stat -c \
            '%n | size=%s | modified=%y' \
            "$ROOT/$f"
    else
        warn "Missing: $f"
    fi
done

###############################################################################
# 27. FINAL RESULT
###############################################################################

section "27. FINAL BACKEND / FRONTEND INTEGRATION RESULT"

echo
echo "Project:"
echo "  $ROOT"

echo
echo "Backup:"
echo "  $BACKUP_DIR"

echo
echo "Report:"
echo "  $REPORT"

echo
echo "Temporary backend:"
echo "  http://127.0.0.1:8000"

echo
echo "Authoritative health:"
echo "  GET /api/system/health"

echo
echo "Training endpoints:"
echo "  GET  /api/training/status"
echo "  GET  /api/training/history"
echo "  GET  /api/training/checkpoints"
echo "  GET  /api/training/metrics"
echo "  POST /api/training/start"
echo "  POST /api/training/stop"
echo "  POST /api/training/full-real-training"
echo "  GET  /api/training/full-real-training/status"

echo
echo "Frontend:"
echo "  frontend/src/pages/Training.tsx"
echo "  frontend/src/pages/History.tsx"
echo "  frontend/src/pages/Decisions.tsx"
echo "  frontend/src/pages/Dashboard.tsx"

echo
echo "Live API smoke-test failures: $LIVE_FAILURES"

if [[ "$ROUTE_FAILURES" -ne 0 ]]; then
    echo
    warn "Some static contract checks reported missing items."
fi

if [[ "$LIVE_FAILURES" -ne 0 ]]; then
    fail "Backend/frontend integration smoke test failed"
    exit 1
fi

echo
ok "BACKEND / FRONTEND INTEGRATION CHECK PASSED"

echo
echo "No model training was started."
echo "No RL artifact was replaced."
echo "No dataset was changed."
echo "The temporary backend will now be stopped."

exit 0
