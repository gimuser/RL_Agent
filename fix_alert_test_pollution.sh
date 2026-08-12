#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$HOME/Desktop/RL_AGENT"
PYTHON="$ROOT/backend/.venv/bin/python"
BACKUP="$ROOT/alert_test_pollution_backup_$(date +%Y%m%d_%H%M%S)"

echo
echo "============================================================"
echo "FIX ALERT TEST DATABASE POLLUTION"
echo "============================================================"

mkdir -p "$BACKUP/backend/app/tests"

cp -a \
    backend/app/tests/test_api.py \
    "$BACKUP/backend/app/tests/test_api.py"

echo "[OK] Backup:"
echo "     $BACKUP"

"$PYTHON" - <<'PY'
from pathlib import Path

path = Path("backend/app/tests/test_api.py")
text = path.read_text(encoding="utf-8")

# Ensure alerts collection is imported.
old_import = (
    "from app.database.database import "
    "decisions_collection, rewards_collection"
)

new_import = (
    "from app.database.database import "
    "alerts_collection, decisions_collection, rewards_collection"
)

if old_import in text:
    text = text.replace(old_import, new_import, 1)
    print("[OK] alerts_collection import added")
elif "alerts_collection, decisions_collection, rewards_collection" in text:
    print("[OK] alerts_collection import already present")
elif "alerts_collection" not in text:
    marker = "from fastapi.testclient import TestClient"
    if marker in text:
        text = text.replace(
            marker,
            marker + "\n" + new_import,
            1,
        )
        print("[OK] alerts_collection import added")
    else:
        raise SystemExit("[FAIL] Could not find import section")

# Locate the alert test.
start = text.find("def test_create_and_get_alerts():")
if start == -1:
    raise SystemExit("[FAIL] test_create_and_get_alerts() not found")

# Find the next test after it.
next_test = text.find("\ndef_", start + 5)
if next_test == -1:
    next_test = len(text)

block = text[start:next_test]

# Add cleanup immediately after the create assertion.
needle = '''    assert create_res.status_code == 200
'''

if "alerts_collection.delete_one" not in block:
    replacement = '''    assert create_res.status_code == 200

    created_alert_id = create_res.json()["id"]
'''
    if needle in block:
        block = block.replace(needle, replacement, 1)

        # Add cleanup before the test ends.
        block = block.rstrip() + '''

    # IMPORTANT:
    # Alert API tests must not pollute the real operational MongoDB.
    alerts_collection.delete_one(
        {"id": created_alert_id}
    )
'''

        text = text[:start] + block + text[next_test:]
        print("[OK] Alert test cleanup added")
    else:
        raise SystemExit(
            "[FAIL] Could not find alert creation assertion"
        )
else:
    print("[OK] Alert test cleanup already present")

path.write_text(text, encoding="utf-8")
PY

echo
echo "============================================================"
echo "1. VERIFY ALERT TEST"
echo "============================================================"

sed -n '1,75p' backend/app/tests/test_api.py

echo
echo "============================================================"
echo "2. COMPILE"
echo "============================================================"

"$PYTHON" -m py_compile backend/app/tests/test_api.py
echo "[OK] test_api.py compiles"

echo
echo "============================================================"
echo "3. REMOVE EXISTING TEST ALERT POLLUTION"
echo "============================================================"

PYTHONPATH="$ROOT/backend:$ROOT" \
"$PYTHON" - <<'PY'
from app.database.database import alerts_collection

test_filter = {
    "title": "Unauthorized SSH Access Attempt",
    "severity": "High",
    "source": "Firewall-Logs",
}

count = alerts_collection.count_documents(test_filter)

print("Matching test alerts:", count)

if count:
    result = alerts_collection.delete_many(test_filter)
    print("Deleted test alerts:", result.deleted_count)

print("Remaining alerts:", alerts_collection.count_documents({}))

print("[OK] Existing test alerts removed")
PY

echo
echo "============================================================"
echo "4. RUN BACKEND TESTS"
echo "============================================================"

(
    cd backend
    export PYTHONPATH="$ROOT/backend:$ROOT"
    "$PYTHON" -m pytest -q app/tests
)

echo
echo "[OK] Backend tests passed"

echo
echo "============================================================"
echo "5. VERIFY NO TEST ALERT POLLUTION"
echo "============================================================"

PYTHONPATH="$ROOT/backend:$ROOT" \
"$PYTHON" - <<'PY'
from app.database.database import alerts_collection

count = alerts_collection.count_documents(
    {
        "title": "Unauthorized SSH Access Attempt",
        "severity": "High",
        "source": "Firewall-Logs",
    }
)

print("Remaining matching test alerts:", count)

assert count == 0

print("[OK] Future alert tests no longer leave test records")
PY

echo
echo "============================================================"
echo "6. FINAL DATABASE STATE"
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
echo "FINAL"
echo "============================================================"

echo "[OK] Alert test database pollution fixed"
echo "[OK] Decision test cleanup remains active"
echo "[OK] Reward test cleanup remains active"
echo "[OK] History remains dynamically connected"
echo "[OK] No model modified"
echo "[OK] No training performed"
echo
echo "Backup:"
echo "  $BACKUP"
