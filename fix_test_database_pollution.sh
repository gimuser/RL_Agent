#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$HOME/Desktop/RL_AGENT"
PYTHON="$ROOT/backend/.venv/bin/python"

BACKUP="$ROOT/test_database_pollution_backup_$(date +%Y%m%d_%H%M%S)"

echo
echo "============================================================"
echo "FIX TEST DATABASE POLLUTION"
echo "============================================================"

mkdir -p "$BACKUP/backend/app/tests"

cp -a \
    backend/app/tests/test_api.py \
    "$BACKUP/backend/app/tests/test_api.py"

echo "[OK] Test backup created:"
echo "     $BACKUP"

###############################################################################
# PATCH TEST FILE
###############################################################################

"$PYTHON" - <<'PY'
from pathlib import Path

path = Path("backend/app/tests/test_api.py")
text = path.read_text(encoding="utf-8")

# Add database collection imports.
if "from app.database.database import" not in text:
    marker = "from fastapi.testclient import TestClient"
    if marker in text:
        text = text.replace(
            marker,
            marker
            + '\n'
            + 'from app.database.database import decisions_collection, rewards_collection',
            1,
        )
    else:
        raise SystemExit(
            "[FAIL] Could not find test import section"
        )

# ------------------------------------------------------------------
# Decisions test cleanup
# ------------------------------------------------------------------

old = '''    post_res = client.post("/api/decisions", json=decision_payload)
    assert post_res.status_code == 200
    assert post_res.json()["action"] == "BLOCK_IP"

    # جلب القرارات
    get_res = client.get("/api/decisions")
    assert get_res.status_code == 200
    assert isinstance(get_res.json(), list)
'''

new = '''    post_res = client.post("/api/decisions", json=decision_payload)
    assert post_res.status_code == 200
    assert post_res.json()["action"] == "BLOCK_IP"

    created_decision_id = post_res.json()["id"]

    # جلب القرارات
    get_res = client.get("/api/decisions")
    assert get_res.status_code == 200
    assert isinstance(get_res.json(), list)

    # IMPORTANT:
    # Tests must not pollute the real operational MongoDB.
    decisions_collection.delete_one(
        {"id": created_decision_id}
    )
'''

if old in text:
    text = text.replace(old, new, 1)
    print("[OK] Decision test cleanup added")
elif "created_decision_id" in text:
    print("[OK] Decision test cleanup already present")
else:
    print("[WARN] Decision test pattern not found")

# ------------------------------------------------------------------
# Reward test cleanup
# ------------------------------------------------------------------

old = '''    post_res = client.post("/api/rewards", json=reward_payload)
    assert post_res.status_code == 200
    assert post_res.json()["reward_value"] == 8.5

    # إحصائيات المكافآت
    stats_res = client.get("/api/rewards/statistics")
    assert stats_res.status_code == 200
    assert "mean_reward" in stats_res.json()
'''

new = '''    post_res = client.post("/api/rewards", json=reward_payload)
    assert post_res.status_code == 200
    assert post_res.json()["reward_value"] == 8.5

    created_reward_id = post_res.json()["id"]

    # إحصائيات المكافآت
    stats_res = client.get("/api/rewards/statistics")
    assert stats_res.status_code == 200
    assert "mean_reward" in stats_res.json()

    # IMPORTANT:
    # Tests must not pollute the real operational MongoDB.
    rewards_collection.delete_one(
        {"id": created_reward_id}
    )
'''

if old in text:
    text = text.replace(old, new, 1)
    print("[OK] Reward test cleanup added")
elif "created_reward_id" in text:
    print("[OK] Reward test cleanup already present")
else:
    print("[WARN] Reward test pattern not found")

path.write_text(text, encoding="utf-8")
PY

###############################################################################
# COMPILE
###############################################################################

echo
echo "============================================================"
echo "1. COMPILE TEST FILE"
echo "============================================================"

"$PYTHON" -m py_compile backend/app/tests/test_api.py

echo "[OK] test_api.py compiles"

###############################################################################
# REMOVE OLD TEST POLLUTION
###############################################################################

echo
echo "============================================================"
echo "2. REMOVING EXISTING TEST POLLUTION"
echo "============================================================"

PYTHONPATH="$ROOT/backend:$ROOT" \
"$PYTHON" - <<'PY'
from app.database.database import (
    decisions_collection,
    rewards_collection,
)

# These records exactly match the test payloads that were repeatedly
# inserted into the real database.

decision_filter = {
    "incident_id": 101,
    "action": "BLOCK_IP",
}

reward_filter = {
    "decision_id": 1,
    "reward_value": 8.5,
    "metrics.latency_reduction": 0.4,
}

decision_count = decisions_collection.count_documents(
    decision_filter
)

reward_count = rewards_collection.count_documents(
    reward_filter
)

print("Matching test decisions:", decision_count)
print("Matching test rewards   :", reward_count)

if decision_count:
    result = decisions_collection.delete_many(
        decision_filter
    )
    print(
        "Deleted test decisions:",
        result.deleted_count,
    )

if reward_count:
    result = rewards_collection.delete_many(
        reward_filter
    )
    print(
        "Deleted test rewards:",
        result.deleted_count,
    )

print()
print(
    "Remaining decisions:",
    decisions_collection.count_documents({})
)

print(
    "Remaining rewards:",
    rewards_collection.count_documents({})
)

print()
print(
    "[OK] Existing repeated test records removed"
)
PY

###############################################################################
# RUN TESTS
###############################################################################

echo
echo "============================================================"
echo "3. RUNNING BACKEND TESTS"
echo "============================================================"

(
    cd backend
    export PYTHONPATH="$ROOT/backend:$ROOT"
    "$PYTHON" -m pytest -q app/tests
)

echo
echo "[OK] Backend tests passed"

###############################################################################
# VERIFY TESTS NO LONGER POLLUTE
###############################################################################

echo
echo "============================================================"
echo "4. VERIFYING TEST DATABASE CLEANLINESS"
echo "============================================================"

PYTHONPATH="$ROOT/backend:$ROOT" \
"$PYTHON" - <<'PY'
from app.database.database import (
    decisions_collection,
    rewards_collection,
)

decision_count = decisions_collection.count_documents(
    {
        "incident_id": 101,
        "action": "BLOCK_IP",
    }
)

reward_count = rewards_collection.count_documents(
    {
        "decision_id": 1,
        "reward_value": 8.5,
        "metrics.latency_reduction": 0.4,
    }
)

print(
    "Remaining test-style decisions:",
    decision_count,
)

print(
    "Remaining test-style rewards:",
    reward_count,
)

assert decision_count == 0
assert reward_count == 0

print()
print(
    "[OK] Tests no longer leave test decision/reward records"
)
PY

###############################################################################
# FINAL COUNTS
###############################################################################

echo
echo "============================================================"
echo "5. FINAL OPERATIONAL COUNTS"
echo "============================================================"

PYTHONPATH="$ROOT/backend:$ROOT" \
"$PYTHON" - <<'PY'
from app.database.database import (
    alerts_collection,
    decisions_collection,
    rewards_collection,
)

print("Alerts    :", alerts_collection.count_documents({}))
print("Decisions :", decisions_collection.count_documents({}))
print("Rewards   :", rewards_collection.count_documents({}))
PY

echo
echo "============================================================"
echo "FINAL RESULT"
echo "============================================================"

echo "[OK] Test database pollution fixed"
echo "[OK] Existing repeated test records removed"
echo "[OK] Future decision tests clean up after themselves"
echo "[OK] Future reward tests clean up after themselves"
echo "[OK] History remains dynamically connected to MongoDB"
echo "[OK] No RL model changed"
echo "[OK] No training performed"

echo
echo "Backup:"
echo "  $BACKUP"
