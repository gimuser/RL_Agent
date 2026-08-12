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
