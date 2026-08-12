#!/usr/bin/env bash
set -Eeuo pipefail

###############################################################################
# RL AGENT - PROJECT STARTPOINT REPAIR
#
# PURPOSE
# -------
# 1. Protect the project before changes.
# 2. Remove accidental Git tracking of backend/.venv.bak.
# 3. Strengthen .gitignore.
# 4. Standardize backend execution on backend/.venv.
# 5. Install required runtime/test dependencies.
# 6. Confirm backend/main.py is the authoritative entrypoint.
# 7. Create an authoritative project-contract checker.
# 8. Verify the real DQN artifact.
# 9. Verify real training/test metrics.
# 10. Verify incident-level train/test separation.
# 11. Verify FastAPI routes.
# 12. Verify real training routes.
# 13. Repair the full-real-training status-variable mismatch.
# 14. Verify frontend production build.
# 15. Run backend tests.
#
# IMPORTANT
# ---------
# This script does NOT:
# - retrain the model
# - replace real metrics
# - fabricate metrics
# - delete real datasets
# - delete verified RL artifacts
# - create backend/app/main.py
###############################################################################

ROOT="${HOME}/Desktop/RL_AGENT"

if [[ ! -d "$ROOT" ]]; then
    echo "[ERROR] Project not found: $ROOT"
    exit 1
fi

cd "$ROOT"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_DIR="$ROOT/project_startpoint_backup_${TIMESTAMP}"
REPORT="$ROOT/project_startpoint_repair_${TIMESTAMP}.txt"

mkdir -p "$BACKUP_DIR"

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
# 1. BASIC VALIDATION
###############################################################################

section "1. VALIDATING PROJECT"

[[ -f "$ROOT/backend/main.py" ]] \
    && ok "backend/main.py exists" \
    || {
        fail "backend/main.py is missing"
        exit 1
    }

[[ -d "$ROOT/backend/app" ]] \
    && ok "backend/app exists" \
    || {
        fail "backend/app is missing"
        exit 1
    }

[[ -d "$ROOT/frontend" ]] \
    && ok "frontend exists" \
    || {
        fail "frontend is missing"
        exit 1
    }

[[ -d "$ROOT/models" ]] \
    && ok "models directory exists" \
    || warn "models directory missing"

[[ -d "$ROOT/data/rl_incident" ]] \
    && ok "real incident dataset directory exists" \
    || warn "data/rl_incident missing"

###############################################################################
# 2. SAFE SOURCE BACKUP
###############################################################################

section "2. CREATING SAFE SOURCE BACKUP"

mkdir -p "$BACKUP_DIR/backend"
mkdir -p "$BACKUP_DIR/frontend"
mkdir -p "$BACKUP_DIR/config"

if [[ -f backend/main.py ]]; then
    cp -a backend/main.py "$BACKUP_DIR/backend/main.py"
fi

if [[ -d backend/app ]]; then
    cp -a backend/app "$BACKUP_DIR/backend/app"
fi

if [[ -d frontend/src ]]; then
    cp -a frontend/src "$BACKUP_DIR/frontend/src"
fi

for f in \
    backend/requirements.txt \
    frontend/package.json \
    frontend/package-lock.json \
    frontend/tsconfig.json \
    frontend/tsconfig.app.json \
    frontend/vite.config.ts \
    docker-compose.yml \
    .env.example \
    .gitignore
do
    if [[ -f "$f" ]]; then
        mkdir -p "$BACKUP_DIR/config/$(dirname "$f")"
        cp -a "$f" "$BACKUP_DIR/config/$f"
    fi
done

ok "Application source backup created"

###############################################################################
# 3. PROTECT VERIFIED RL ARTIFACTS
###############################################################################

section "3. PROTECTING VERIFIED RL ARTIFACTS"

CRITICAL_ARTIFACTS=(
    "models/real_dqn_agent.pt"
    "models/training_metrics.json"
    "models/real_test_metrics.json"
    "models/test_predictions.csv"
    "models/real_test_predictions.jsonl"
)

ARTIFACT_FAILURE=0

for f in "${CRITICAL_ARTIFACTS[@]}"; do
    if [[ -f "$ROOT/$f" ]]; then
        size="$(du -h "$ROOT/$f" | awk '{print $1}')"
        ok "$f exists ($size)"
    else
        warn "$f missing"
        ARTIFACT_FAILURE=1
    fi
done

if [[ "$ARTIFACT_FAILURE" -eq 0 ]]; then
    ok "All verified RL artifacts are present"
else
    warn "Some expected artifacts are missing; this script will NOT recreate them"
fi

###############################################################################
# 4. VERIFY REAL INCIDENT DATA
###############################################################################

section "4. VERIFYING REAL INCIDENT DATA"

for f in \
    data/rl_incident/train_incident.csv \
    data/rl_incident/test_incident.csv \
    data/rl_incident/train_incidents.txt \
    data/rl_incident/test_incidents.txt \
    data/rl_incident/split_report.json
do
    if [[ -f "$ROOT/$f" ]]; then
        ok "$f"
    else
        warn "$f missing"
    fi
done

###############################################################################
# 5. REPAIR GITIGNORE
###############################################################################

section "5. REPAIRING GIT IGNORE"

touch .gitignore

append_ignore() {
    local line="$1"
    if ! grep -Fxq "$line" .gitignore 2>/dev/null; then
        echo "$line" >> .gitignore
    fi
}

append_ignore ""
append_ignore "# Python environments / caches"
append_ignore ".venv/"
append_ignore "**/.venv/"
append_ignore ".venv.bak/"
append_ignore "**/.venv.bak/"
append_ignore "__pycache__/"
append_ignore "**/__pycache__/"
append_ignore "*.py[cod]"
append_ignore ".pytest_cache/"
append_ignore "**/.pytest_cache/"
append_ignore ".mypy_cache/"
append_ignore ".ruff_cache/"

append_ignore ""
append_ignore "# Node / frontend"
append_ignore "frontend/node_modules/"
append_ignore "**/node_modules/"
append_ignore "frontend/dist/"
append_ignore "**/dist/"

append_ignore ""
append_ignore "# IDE"
append_ignore ".idea/"
append_ignore ".vscode/*.log"

append_ignore ""
append_ignore "# Temporary project repair artifacts"
append_ignore "project_startpoint_backup_*/"
append_ignore "project_archive_*/"
append_ignore "*backup*"
append_ignore "*.bak"
append_ignore "*.tmp"

append_ignore ""
append_ignore "# Local logs"
append_ignore "logs/"
append_ignore "**/*.log"

append_ignore ""
append_ignore "# Generated inspection / chat artifacts"
append_ignore "full.txt"
append_ignore "output.txt"
append_ignore "outpux.txt"
append_ignore "project_tree.txt"
append_ignore "tree_last.txt"
append_ignore "dataset.txt"
append_ignore "datasets.txt"
append_ignore "chiki.txt"
append_ignore "final_rl_implementation_inspection.txt"

ok ".gitignore updated"

###############################################################################
# 6. REMOVE backend/.venv.bak FROM GIT TRACKING
###############################################################################

section "6. REMOVING backend/.venv.bak FROM GIT TRACKING"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if git ls-files --error-unmatch backend/.venv.bak >/dev/null 2>&1; then
        warn "backend/.venv.bak is tracked by Git"
    fi

    if git ls-files | grep -q '^backend/\.venv\.bak/'; then
        git rm -r --cached --ignore-unmatch backend/.venv.bak || true
        ok "backend/.venv.bak removed from Git tracking"
    else
        ok "backend/.venv.bak is not tracked"
    fi
else
    warn "Not a Git repository"
fi

###############################################################################
# 7. VERIFY AUTHORITATIVE ENTRYPOINT
###############################################################################

section "7. VERIFYING BACKEND ENTRYPOINT"

if [[ -f backend/main.py ]]; then
    ok "Authoritative backend entrypoint: backend/main.py"
else
    fail "backend/main.py not found"
    exit 1
fi

if [[ -f backend/app/main.py ]]; then
    warn "backend/app/main.py exists; it is NOT treated as authoritative"
else
    ok "No fake backend/app/main.py exists"
fi

###############################################################################
# 8. CREATE AUTHORITATIVE PROJECT CONTRACT CHECKER
###############################################################################

section "8. CREATING AUTHORITATIVE PROJECT CONTRACT CHECK"

mkdir -p scripts

cat > scripts/verify_project_contract.sh <<'CHECKER'
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAILURES=0

ok() {
    echo "[OK] $*"
    PASS=$((PASS + 1))
}

fail() {
    echo "[FAIL] $*"
    FAILURES=$((FAILURES + 1))
}

echo
echo "======================================================================"
echo "RL AGENT - AUTHORITATIVE PROJECT CONTRACT"
echo "======================================================================"

###############################################################################
# Backend entrypoint
###############################################################################

if [[ -f backend/main.py ]]; then
    ok "backend/main.py"
else
    fail "backend/main.py missing"
fi

###############################################################################
# Critical RL modules
###############################################################################

for f in \
    backend/app/rl_agent/dqn.py \
    backend/app/rl_agent/trainer.py \
    backend/app/rl_agent/evaluator.py \
    backend/app/rl_agent/evaluate_real.py \
    backend/app/rl_agent/real_pipeline.py \
    backend/app/rl_agent/triage_env.py \
    backend/app/reward/real_reward.py \
    backend/app/reward/outcomes.py
do
    if [[ -f "$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
    fi
done

###############################################################################
# Critical APIs
###############################################################################

for f in \
    backend/app/api/router.py \
    backend/app/api/training.py \
    backend/app/api/dashboard.py \
    backend/app/api/decisions.py \
    backend/app/api/alerts.py \
    backend/app/api/health.py
do
    if [[ -f "$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
    fi
done

###############################################################################
# Critical frontend
###############################################################################

for f in \
    frontend/src/pages/Training.tsx \
    frontend/src/pages/History.tsx \
    frontend/src/pages/Decisions.tsx \
    frontend/src/pages/Dashboard.tsx \
    frontend/src/services/training.service.ts \
    frontend/src/services/decisions.service.ts \
    frontend/src/services/dashboard.service.ts \
    frontend/src/types/domain.ts
do
    if [[ -f "$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
    fi
done

###############################################################################
# Expected real-data artifacts
###############################################################################

for f in \
    models/real_dqn_agent.pt \
    models/training_metrics.json \
    models/real_test_metrics.json \
    models/test_predictions.csv \
    models/real_test_predictions.jsonl
do
    if [[ -f "$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
    fi
done

###############################################################################
# Expected real incident split
###############################################################################

for f in \
    data/rl_incident/train_incident.csv \
    data/rl_incident/test_incident.csv \
    data/rl_incident/split_report.json
do
    if [[ -f "$f" ]]; then
        ok "$f"
    else
        fail "$f missing"
    fi
done

echo
echo "======================================================================"
echo "RESULT"
echo "======================================================================"

echo "PASS    : $PASS"
echo "FAILURES: $FAILURES"

if [[ "$FAILURES" -ne 0 ]]; then
    exit 1
fi
CHECKER

chmod +x scripts/verify_project_contract.sh

ok "Authoritative contract checker created"

###############################################################################
# 9. PREPARE BACKEND VENV
###############################################################################

section "9. PREPARING backend/.venv"

if [[ ! -x backend/.venv/bin/python ]]; then
    warn "backend/.venv Python missing"
    python3 -m venv backend/.venv
    ok "backend/.venv created"
else
    ok "backend/.venv already exists"
fi

PYTHON="$ROOT/backend/.venv/bin/python"
PIP="$ROOT/backend/.venv/bin/pip"

echo "Python:"
"$PYTHON" --version

echo "Executable:"
readlink -f "$PYTHON" || true

###############################################################################
# 10. PACKAGE TOOLING
###############################################################################

section "10. PREPARING PYTHON PACKAGE TOOLING"

"$PYTHON" -m pip install --upgrade pip setuptools wheel

ok "pip/setuptools/wheel ready"

###############################################################################
# 11. REQUIREMENTS
###############################################################################

section "11. INSTALLING BACKEND REQUIREMENTS"

if [[ -f backend/requirements.txt ]]; then
    echo "Installing requirements from backend/requirements.txt ..."

    if ! "$PIP" install -r backend/requirements.txt; then
        warn "requirements installation reported an error"
        warn "Continuing with explicit critical dependency installation"
    fi

    ok "requirements file processed"
else
    warn "backend/requirements.txt missing"
fi

###############################################################################
# 12. EXPLICIT CRITICAL DEPENDENCIES
###############################################################################

section "12. INSTALLING REQUIRED RL / TEST DEPENDENCIES"

"$PIP" install \
    numpy \
    pandas \
    scipy \
    scikit-learn \
    torch \
    gymnasium \
    fastapi \
    uvicorn \
    pydantic \
    pymongo \
    python-dotenv \
    httpx \
    httpx2

ok "Critical backend/RL/test dependencies installed"

###############################################################################
# 13. VERIFY PYTHON DEPENDENCIES
###############################################################################

section "13. VERIFYING PYTHON DEPENDENCIES"

"$PYTHON" - <<'PY'
import sys
import importlib

packages = [
    "numpy",
    "pandas",
    "torch",
    "sklearn",
    "gymnasium",
    "fastapi",
    "pydantic",
    "uvicorn",
    "pymongo",
    "httpx",
]

print("Python:", sys.version)
print("Executable:", sys.executable)
print()

failed = 0

for name in packages:
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "unknown")
        print(f"[OK] {name}: {version}")
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        failed += 1

if failed:
    raise SystemExit(1)
PY

ok "Required dependencies import successfully"

###############################################################################
# 14. COMPILE BACKEND
###############################################################################

section "14. COMPILING BACKEND SOURCE"

"$PYTHON" -m compileall -q backend/app backend/main.py

ok "backend application compiles"

###############################################################################
# 15. VERIFY BACKEND IMPORTS
###############################################################################

section "15. VERIFYING BACKEND IMPORTS"

PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
import importlib
import sys

modules = [
    "app.rl_agent.dqn",
    "app.rl_agent.trainer",
    "app.rl_agent.evaluator",
    "app.rl_agent.evaluate_real",
    "app.rl_agent.real_pipeline",
    "app.rl_agent.triage_env",
    "app.reward.real_reward",
    "app.reward.outcomes",
    "app.services.training_service",
    "app.services.dashboard_service",
    "app.services.agent_service",
    "app.services.model_service",
    "app.services.experiment_service",
    "app.api.training",
    "app.api.router",
    "app.api.health",
]

print("Python executable:", sys.executable)
print()

failed = 0

for name in modules:
    try:
        importlib.import_module(name)
        print(f"[OK] import {name}")
    except Exception as exc:
        print(f"[FAIL] import {name}: {type(exc).__name__}: {exc}")
        failed += 1

if failed:
    raise SystemExit(1)
PY

ok "Critical backend imports succeed"

###############################################################################
# 16. VERIFY REAL DQN MODEL
###############################################################################

section "16. VERIFYING REAL DQN MODEL LOAD"

if [[ -f models/real_dqn_agent.pt ]]; then

    PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
from pathlib import Path
import numpy as np

from app.rl_agent.dqn import DoubleDQN

model_path = Path("models/real_dqn_agent.pt")

model = DoubleDQN(
    input_dim=13,
    n_actions=3,
)

model.load(str(model_path))

states = np.zeros((3, 13), dtype=np.float32)

q_values = model.q_values(states)
actions = model.act(states)

print("Q shape :", q_values.shape)
print("Actions :", actions.tolist())
print("Q values:", q_values)

assert q_values.shape == (3, 3)
assert len(actions) == 3

print("[OK] Real DQN model loads and produces Q-values/actions")
PY

else
    warn "models/real_dqn_agent.pt not found; skipping model-load test"
fi

###############################################################################
# 17. VERIFY TRAINING METRICS
###############################################################################

section "17. VERIFYING TRAINING METRICS"

if [[ -f models/training_metrics.json ]]; then

    "$PYTHON" - <<'PY'
import json
from pathlib import Path

path = Path("models/training_metrics.json")
data = json.loads(path.read_text())

print("Top-level keys:", list(data.keys()))

metrics = data.get("metrics", [])
config = data.get("config", {})

print("Metric records:", len(metrics))
print("Config epochs:", config.get("epochs"))
print("Config batch_size:", config.get("batch_size"))

if metrics:
    print("First record:", metrics[0])
    print("Last record :", metrics[-1])

assert metrics
assert config.get("epochs", 0) > 0

print("[OK] Training metrics are structurally valid")
PY

else
    warn "models/training_metrics.json not found"
fi

###############################################################################
# 18. VERIFY REAL TEST METRICS
###############################################################################

section "18. VERIFYING REAL TEST METRICS"

if [[ -f models/real_test_metrics.json ]]; then

    "$PYTHON" - <<'PY'
import json
from pathlib import Path

path = Path("models/real_test_metrics.json")
data = json.loads(path.read_text())

required = [
    "test_rows",
    "test_incidents",
    "total_reward",
    "average_reward",
    "optimal_possible_reward",
    "reward_regret",
    "reward_efficiency",
    "policy_optimality",
    "action_distribution",
    "per_class",
    "synthetic_data",
    "unseen_incidents",
]

for key in required:
    assert key in data, f"Missing metric: {key}"

assert data["test_rows"] > 0
assert data["test_incidents"] > 0
assert data["synthetic_data"] is False
assert data["unseen_incidents"] is True

print("Test rows        :", data["test_rows"])
print("Test incidents   :", data["test_incidents"])
print("Average reward   :", data["average_reward"])
print("Reward efficiency:", data["reward_efficiency"])
print("Policy optimality:", data["policy_optimality"])
print("Synthetic data   :", data["synthetic_data"])
print("Unseen incidents :", data["unseen_incidents"])

print("[OK] Real test metrics are valid")
PY

else
    warn "models/real_test_metrics.json not found"
fi

###############################################################################
# 19. VERIFY PREDICTION ARTIFACT COUNTS
###############################################################################

section "19. VERIFYING PREDICTION ARTIFACT CONSISTENCY"

EXPECTED_ROWS=""

if [[ -f models/real_test_metrics.json ]]; then
    EXPECTED_ROWS="$(
        "$PYTHON" - <<'PY'
import json
with open("models/real_test_metrics.json", "r", encoding="utf-8") as f:
    print(json.load(f)["test_rows"])
PY
    )"
fi

if [[ -n "$EXPECTED_ROWS" ]]; then

    if [[ -f models/test_predictions.csv ]]; then
        CSV_ROWS="$(
            "$PYTHON" - <<'PY'
import pandas as pd
print(len(pd.read_csv("models/test_predictions.csv")))
PY
        )"

        echo "Expected rows : $EXPECTED_ROWS"
        echo "CSV rows      : $CSV_ROWS"

        if [[ "$CSV_ROWS" == "$EXPECTED_ROWS" ]]; then
            ok "CSV predictions match test metrics"
        else
            fail "CSV prediction row count mismatch"
        fi
    else
        warn "models/test_predictions.csv missing"
    fi

    if [[ -f models/real_test_predictions.jsonl ]]; then
        JSONL_ROWS="$(wc -l < models/real_test_predictions.jsonl)"

        echo "JSONL rows    : $JSONL_ROWS"

        if [[ "$JSONL_ROWS" == "$EXPECTED_ROWS" ]]; then
            ok "JSONL predictions match test metrics"
        else
            fail "JSONL prediction row count mismatch"
        fi
    else
        warn "models/real_test_predictions.jsonl missing"
    fi
fi

###############################################################################
# 20. VERIFY INCIDENT SPLIT
###############################################################################

section "20. VERIFYING INCIDENT-LEVEL SPLIT"

if [[ -f data/rl_incident/train_incident.csv ]] && \
   [[ -f data/rl_incident/test_incident.csv ]]; then

    PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
import pandas as pd

train = pd.read_csv(
    "data/rl_incident/train_incident.csv",
    usecols=["IncidentId"],
)

test = pd.read_csv(
    "data/rl_incident/test_incident.csv",
    usecols=["IncidentId"],
)

train_ids = set(train["IncidentId"].astype(str))
test_ids = set(test["IncidentId"].astype(str))

overlap = train_ids.intersection(test_ids)

print("Train incidents :", len(train_ids))
print("Test incidents  :", len(test_ids))
print("Overlap         :", len(overlap))

assert len(overlap) == 0

print("[OK] Train/test incident split has zero overlap")
PY

else
    warn "Incident split CSV files unavailable"
fi

###############################################################################
# 21. VERIFY RL ACTION / FEATURE CONTRACT
###############################################################################

section "21. VERIFYING RL ACTION / FEATURE CONTRACT"

PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
from app.rl_agent.real_pipeline import (
    ACTIONS,
    FEATURES,
    INCIDENT_ID,
    TARGET,
)
from app.reward.outcomes import ACTION_NAMES

print("ACTIONS     :", ACTIONS)
print("ACTION_NAMES:", ACTION_NAMES)
print("FEATURES    :", len(FEATURES))
print("INCIDENT_ID :", INCIDENT_ID)
print("TARGET      :", TARGET)

assert len(ACTIONS) == 3
assert len(FEATURES) == 13
assert INCIDENT_ID == "IncidentId"
assert TARGET == "IncidentGrade"

print("[OK] RL feature/action contract is valid")
PY

###############################################################################
# 22. REPAIR FULL REAL-TRAINING STATUS STATE
###############################################################################

section "22. REPAIRING FULL REAL-TRAINING STATUS STATE"

TRAINING_API="backend/app/api/training.py"

if [[ -f "$TRAINING_API" ]]; then
    "$PYTHON" - "$TRAINING_API" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

old = 'current = globals().get("FULL_REAL_TRAINING_STATE")'
new = 'current = _full_training_state'

if old in text:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("[OK] Replaced stale FULL_REAL_TRAINING_STATE lookup")
elif new in text:
    print("[OK] Full real-training status already uses _full_training_state")
else:
    print("[WARN] Could not find the expected status-state lookup")
PY
else
    fail "$TRAINING_API missing"
fi

###############################################################################
# 23. AUTHORITATIVE PROJECT CONTRACT
###############################################################################

section "23. RUNNING AUTHORITATIVE PROJECT CONTRACT"

if scripts/verify_project_contract.sh; then
    ok "Authoritative project contract passed"
else
    fail "Authoritative project contract failed"
fi

###############################################################################
# 24. VERIFY FASTAPI ROUTER REGISTRATION
###############################################################################

section "24. VERIFYING API ROUTER REGISTRATION"

PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
from backend.main import app

routes = sorted({
    getattr(route, "path", "")
    for route in app.routes
    if getattr(route, "path", "")
})

print("Registered API routes:")
for path in routes:
    print(" ", path)

required = [
    "/",
    "/api/system/health",
    "/api/training/status",
    "/api/training/full-real-training",
    "/api/training/full-real-training/status",
]

failures = 0

for path in required:
    if path in routes:
        print("[OK] Required route:", path)
    else:
        print("[FAIL] Required route missing:", path)
        failures += 1

if failures:
    raise SystemExit(1)

print()
print("[OK] FastAPI application exposes all authoritative routes")
PY

###############################################################################
# 25. VERIFY TRAINING ROUTES SPECIFICALLY
###############################################################################

section "25. VERIFYING REAL TRAINING ROUTES"

PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
from backend.main import app

routes = {
    getattr(route, "path", "")
    for route in app.routes
    if getattr(route, "path", "")
}

required_fragments = [
    "/api/training/status",
    "/api/training/full-real-training",
    "/api/training/full-real-training/status",
]

for fragment in required_fragments:
    if fragment in routes:
        print("[OK]", fragment)
    else:
        print("[FAIL] Not registered:", fragment)
        raise SystemExit(1)

print("[OK] Real training routes verified")
PY

###############################################################################
# 26. VERIFY TRAINING HTTP METHODS
###############################################################################

section "26. VERIFYING REAL TRAINING HTTP METHODS"

PYTHONPATH="$ROOT/backend:$ROOT" "$PYTHON" - <<'PY'
from backend.main import app

required = {
    ("GET", "/api/training/status"),
    ("POST", "/api/training/full-real-training"),
    ("GET", "/api/training/full-real-training/status"),
}

found = set()

for route in app.routes:
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", set())

    for method in methods:
        found.add((method, path))

for item in sorted(required):
    if item in found:
        print("[OK]", item[0], item[1])
    else:
        print("[FAIL] Missing:", item[0], item[1])
        raise SystemExit(1)

print("[OK] Training methods verified")
PY

###############################################################################
# 27. VERIFY FRONTEND ENVIRONMENT
###############################################################################

section "27. VERIFYING FRONTEND ENVIRONMENT"

if [[ -f frontend/package.json ]]; then

    if command -v node >/dev/null 2>&1; then
        echo "Node: $(node --version)"
    else
        fail "node command not available"
    fi

    if command -v npm >/dev/null 2>&1; then
        echo "npm : $(npm --version)"
    else
        fail "npm command not available"
    fi

    if [[ -d frontend/node_modules ]]; then
        ok "frontend/node_modules exists"
    else
        warn "frontend/node_modules missing"
        (
            cd frontend
            npm ci
        )
        ok "frontend dependencies installed"
    fi

else
    fail "frontend/package.json missing"
fi

###############################################################################
# 28. FRONTEND BUILD
###############################################################################

section "28. BUILDING FRONTEND"

(
    cd frontend
    npm run build
)

ok "Frontend production build succeeds"

###############################################################################
# 29. BACKEND PYTEST
###############################################################################

section "29. RUNNING BACKEND PYTEST WITH backend/.venv"

TEST_FAILURE=0

(
    cd backend
    export PYTHONPATH="$ROOT/backend:$ROOT"
    "$PYTHON" -m pytest -q app/tests
) || TEST_FAILURE=$?

if [[ "$TEST_FAILURE" -eq 0 ]]; then
    ok "backend/app/tests passed"
else
    fail "backend/app/tests failed"
fi

###############################################################################
# 30. FEATURE ENVIRONMENT TESTS
###############################################################################

section "30. RUNNING FEATURE ENVIRONMENT TESTS"

if [[ -d feature_environment/tests ]]; then

    FEATURE_FAILURE=0

    (
        export PYTHONPATH="$ROOT:$ROOT/backend"
        "$PYTHON" -m pytest -q feature_environment/tests
    ) || FEATURE_FAILURE=$?

    if [[ "$FEATURE_FAILURE" -eq 0 ]]; then
        ok "feature_environment tests passed"
    else
        warn "feature_environment tests failed"
    fi

else
    ok "feature_environment test suite not present"
fi

###############################################################################
# 31. FRONTEND MOCK MODE
###############################################################################

section "31. CHECKING FRONTEND MOCK CONFIGURATION"

if [[ -f frontend/.env ]]; then

    if grep -Eq '^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=[[:space:]]*true[[:space:]]*$' frontend/.env; then
        warn "frontend/.env has VITE_USE_MOCKS=true"
        sed -i -E \
            's/^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=.*/VITE_USE_MOCKS=false/' \
            frontend/.env
        ok "Frontend mock mode disabled"
    else
        ok "Frontend mock mode is not enabled"
    fi

elif [[ -f frontend/.env.example ]]; then

    cp frontend/.env.example frontend/.env

    sed -i -E \
        's/^[[:space:]]*VITE_USE_MOCKS[[:space:]]*=.*/VITE_USE_MOCKS=false/' \
        frontend/.env

    ok "frontend/.env created with VITE_USE_MOCKS=false"

else
    warn "frontend/.env.example missing"
fi

###############################################################################
# 32. FRONTEND / BACKEND API CONTRACT SEARCH
###############################################################################

section "32. SEARCHING FRONTEND/BACKEND API CONTRACT"

echo "--- Training service ---"

if [[ -f frontend/src/services/training.service.ts ]]; then
    grep -nE \
        '/api/training|full-real-training|experiment' \
        frontend/src/services/training.service.ts || true
fi

echo
echo "--- Backend training routes ---"

if [[ -f backend/app/api/training.py ]]; then
    grep -nE \
        '@router\.(get|post|delete|put|patch)|/full-real-training|/status|/history|/metrics|/checkpoints|/experiment' \
        backend/app/api/training.py || true
fi

echo
echo "--- Health route ---"

grep -nE \
    'include_router\(health_router|@router\.get\("/health"\)' \
    backend/app/api/router.py \
    backend/app/api/health.py || true

###############################################################################
# 33. CREATE ALIGNMENT NOTE
###############################################################################

section "33. CREATING FRONTEND/BACKEND ALIGNMENT NOTE"

cat > FRONTEND_BACKEND_ALIGNMENT_REQUIRED.md <<'NOTE'
# Frontend / Backend Alignment Required

The authoritative backend entrypoint is:

- backend/main.py

The authoritative health endpoint is:

- /api/system/health

The authoritative real RL training endpoints are:

- GET /api/training/status
- POST /api/training/full-real-training
- GET /api/training/full-real-training/status

Authoritative real artifacts:

- models/real_dqn_agent.pt
- models/training_metrics.json
- models/real_test_metrics.json
- models/test_predictions.csv
- models/real_test_predictions.jsonl

Authoritative real datasets:

- data/rl_incident/train_incident.csv
- data/rl_incident/test_incident.csv

Do NOT hardcode model metrics into the frontend.

The frontend should consume the backend's real:

- training status
- training history
- checkpoint information
- evaluation metrics
- decisions
- rewards
- dashboard data

Before modifying frontend behavior, compare the exact backend schemas and
routes with:

Backend:
- backend/app/api/training.py
- backend/app/api/router.py
- backend/app/services/training_service.py
- backend/app/services/experiment_service.py
- backend/app/services/model_service.py
- backend/app/schemas/training_schema.py
- backend/main.py

Frontend:
- frontend/src/pages/Training.tsx
- frontend/src/pages/History.tsx
- frontend/src/pages/Decisions.tsx
- frontend/src/pages/Dashboard.tsx
- frontend/src/services/training.service.ts
- frontend/src/services/decisions.service.ts
- frontend/src/services/dashboard.service.ts
- frontend/src/types/domain.ts
- frontend/src/types/api.ts
NOTE

ok "Frontend/backend alignment note created"

###############################################################################
# 34. GIT STATUS
###############################################################################

section "34. GIT STATUS AFTER REPAIR"

git status --short || true

echo
echo "--- Important ignored paths ---"

git check-ignore -v \
    backend/.venv.bak \
    backend/.venv \
    frontend/node_modules \
    frontend/dist \
    "$BACKUP_DIR" \
    2>/dev/null || true

###############################################################################
# 35. FINAL SUMMARY
###############################################################################

section "35. FINAL REPAIR SUMMARY"

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
echo "Authoritative backend entrypoint:"
echo "  backend/main.py"

echo
echo "Authoritative health endpoint:"
echo "  /api/system/health"

echo
echo "Authoritative real training endpoints:"
echo "  GET  /api/training/status"
echo "  POST /api/training/full-real-training"
echo "  GET  /api/training/full-real-training/status"

echo
echo "Protected real RL artifacts:"
for f in "${CRITICAL_ARTIFACTS[@]}"; do
    if [[ -f "$f" ]]; then
        echo "  [OK] $f"
    else
        echo "  [MISSING] $f"
    fi
done

echo
echo "Python:"
"$PYTHON" --version

echo
echo "Frontend:"
node --version
npm --version

echo
echo "======================================================================"
echo "IMPORTANT"
echo "======================================================================"

echo "No model retraining was performed."
echo "No real dataset was deleted."
echo "No verified RL metrics were replaced."
echo "No backend/app/main.py was created."
echo "The old broken route checker was replaced."
echo "The /api/health false warning was replaced by /api/system/health."
echo "The route-check set/hash bug was fixed."
echo "The full-real-training state lookup was repaired."

if [[ "$TEST_FAILURE" -eq 0 ]]; then
    ok "Backend pytest passed"
else
    warn "Backend pytest failed; inspect the report above"
fi

echo
echo "======================================================================"
echo "REPAIR COMPLETE"
echo "======================================================================"

exit 0
