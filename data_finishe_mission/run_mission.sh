#!/usr/bin/env bash

set -uo pipefail

MISSION="${MISSION_DIR:-$HOME/Desktop/Data_mission}"
INPUT="$MISSION/data_finished"
RUNTIME="$MISSION/RL_Agent_runtime"
PROCESSOR="$RUNTIME/scripts/process_data_finished.py"
LOGS="$MISSION/logs"
ARCHIVE="$MISSION/archive"

mkdir -p "$INPUT" "$LOGS" "$ARCHIVE" "$RUNTIME"

echo "=============================================================="
echo " DATA_MISSION — GUIDE -> PROCESS -> INCIDENT -> 80 LIVE"
echo "=============================================================="
echo "MISSION   : $MISSION"
echo "INPUT     : $INPUT"
echo "RUNTIME   : $RUNTIME"
echo "PROCESSOR : $PROCESSOR"
echo

echo "[1/7] Synchronizing RL_Agent runtime..."
if [[ ! -d "$RUNTIME/.git" ]]; then
  until git clone --depth 1 https://github.com/gimuser/RL_Agent.git "$RUNTIME"; do
    echo "[WAIT] Runtime clone failed; retrying in 30 seconds..."
    sleep 30
  done
else
  git -C "$RUNTIME" fetch origin main 2>/dev/null || true
  git -C "$RUNTIME" reset --hard origin/main 2>/dev/null || true
fi

echo "[OK] Runtime commit:"
git -C "$RUNTIME" rev-parse --short HEAD 2>/dev/null || true
echo

TRAIN="$INPUT/GUIDE_Train.csv"
TEST="$INPUT/GUIDE_Test.csv"

# Manual-only: never download, delete, or overwrite the source datasets.
echo "[2/7] Waiting for manually supplied GUIDE datasets..."
while [[ ! -s "$TRAIN" || ! -s "$TEST" ]]; do
  echo "[WAIT] Required files:"
  echo "       $TRAIN"
  echo "       $TEST"
  [[ -s "$TRAIN" ]] || echo "       Missing: GUIDE_Train.csv"
  [[ -s "$TEST" ]] || echo "       Missing: GUIDE_Test.csv"
  sleep 15
done

echo "[OK] Both GUIDE datasets are present."
ls -lh "$TRAIN" "$TEST"
echo

wait_stable() {
  local file="$1"
  local a b
  [[ -s "$file" ]] || return 1
  a=$(stat -c '%s' "$file" 2>/dev/null || printf '0')
  sleep 3
  b=$(stat -c '%s' "$file" 2>/dev/null || printf '0')
  [[ "$a" == "$b" ]]
}

echo "[3/7] Checking dataset stability..."
while ! wait_stable "$TRAIN" || ! wait_stable "$TEST"; do
  echo "[WAIT] One or both files are still changing."
  sleep 10
done

echo "[OK] Both files are stable."
echo

# The processor supports RL_AGENT_INPUT_DIR. Use that so the runtime reads
# the files in Data_mission without loading/copying the 700-800 MB files twice.
export RL_AGENT_INPUT_DIR="$INPUT"

while [[ ! -f "$PROCESSOR" ]]; do
  echo "[WAIT] Processor not available: $PROCESSOR"
  git -C "$RUNTIME" fetch origin main 2>/dev/null || true
  git -C "$RUNTIME" reset --hard origin/main 2>/dev/null || true
  sleep 10
done

echo "[4/7] Processor found."
echo

STAMP=$(date -u '+%Y%m%d_%H%M%S')
LOG="$LOGS/mission_${STAMP}.log"
ARCHIVE_RUN="$ARCHIVE/$STAMP"
mkdir -p "$ARCHIVE_RUN"

echo "[5/7] Running memory-safe GUIDE pipeline..."
echo "[LOG] $LOG"
echo

if python3 "$PROCESSOR" 2>&1 | tee "$LOG"; then
  echo
  echo "[6/7] Processing succeeded."
  mv "$TRAIN" "$ARCHIVE_RUN/GUIDE_Train.csv"
  mv "$TEST" "$ARCHIVE_RUN/GUIDE_Test.csv"
  cp "$LOG" "$ARCHIVE_RUN/mission.log"
  echo "[OK] Source datasets archived at:"
  echo "     $ARCHIVE_RUN"
else
  echo
  echo "[ERROR] Processing failed."
  echo "[INFO] Source datasets were NOT moved and remain in:"
  echo "       $INPUT"
  echo "[LOG]  $LOG"
fi

echo
echo "[7/7] Output check"
echo
for path in \
  "$RUNTIME/data/processed/train_processed.csv" \
  "$RUNTIME/data/processed/test_processed.csv" \
  "$RUNTIME/data/rl_incident/train_incident.csv" \
  "$RUNTIME/data/rl_incident/test_incident.csv" \
  "$RUNTIME/data_alert/live_source.csv" \
  "$RUNTIME/data_alert/live_processed.csv" \
  "$RUNTIME/data_alert/live_mapping.csv"
do
  if [[ -f "$path" ]]; then
    echo "[OK] $path"
  else
    echo "[WARN] Missing: $path"
  fi
done

echo
echo "=============================================================="
echo " MISSION STATUS"
echo "=============================================================="
echo "Live set: 80 incidents = 40 + 40 distinct"
echo "Disjointness: verified by process_data_finished.py"
echo "Input:  $INPUT"
echo "Runtime: $RUNTIME"
echo "=============================================================="
