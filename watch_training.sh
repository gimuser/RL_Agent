#!/usr/bin/env bash

set -u

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
STATUS_URL="$BASE_URL/api/training/full-real-training/status"
INTERVAL="${INTERVAL:-3}"

echo "============================================================"
echo " RL AGENT — FULL TRAINING MONITOR"
echo "============================================================"
echo
echo "[INFO] Backend: $BASE_URL"
echo "[INFO] Status : $STATUS_URL"
echo "[INFO] Refresh: ${INTERVAL}s"
echo

if ! curl -fsS "$BASE_URL/docs" >/dev/null 2>&1; then
    echo "[ERROR] Backend is not reachable at $BASE_URL"
    echo
    echo "Start the project first:"
    echo "  ./run_local.sh"
    exit 1
fi

echo "[OK] Backend is reachable."
echo "[INFO] Waiting for training status..."
echo

while true; do
    RESPONSE=$(curl -fsS "$STATUS_URL" 2>/dev/null || true)

    if [ -z "$RESPONSE" ]; then
        echo "[WARN] Could not retrieve training status."
        sleep "$INTERVAL"
        continue
    fi

    clear

    echo "============================================================"
    echo " RL AGENT — FULL TRAINING MONITOR"
    echo "============================================================"
    echo
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Backend: $BASE_URL"
    echo

    if command -v python3 >/dev/null 2>&1; then
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    else
        echo "$RESPONSE"
    fi

    echo
    echo "------------------------------------------------------------"
    echo "Refreshing every ${INTERVAL}s — Ctrl+C to stop"
    echo "------------------------------------------------------------"

    LOWER=$(echo "$RESPONSE" | tr '[:upper:]' '[:lower:]')

    if echo "$LOWER" | grep -Eq '"(status|state)"[[:space:]]*:[[:space:]]*"(completed|complete|finished|success|failed|error|cancelled)"'; then
        echo
        echo "[INFO] Training reached a terminal state."
        echo
        break
    fi

    sleep "$INTERVAL"
done
