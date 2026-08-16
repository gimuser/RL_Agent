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

# Keep the runtime processor synchronized with the public repository.
echo "[1/8] Synchronizing RL_Agent runtime..."
if [[ ! -d "$RUNTIME/.git" ]]; then
  if git clone --depth 1 https://github.com/gimuser/RL_Agent.git "$RUNTIME"; then
    echo "[OK] Runtime cloned."
  else
    echo "[ERROR] Runtime clone failed. Retrying in 30 seconds."
    sleep 30
    while [[ ! -d "$RUNTIME/.git" ]]; do
      if git clone --depth 1 https://github.com/gimuser/RL_Agent.git "$RUNTIME"; then
        break
      fi
      sleep 30
    done
  fi
else
  git -C "$RUNTIME" fetch origin main 2>/dev/null || true
  git -C "$RUNTIME" reset --hard origin/main 2>/dev/null || true
fi

echo "[OK] Runtime commit:"
git -C "$RUNTIME" rev-parse --short HEAD 2>/dev/null || true
echo

TRAIN="$INPUT/GUIDE_Train.csv"
TEST="$INPUT/GUIDE_Test.csv"

# MANUAL-FIRST: never delete or overwrite manually supplied files.
echo "[2/8] Checking manually supplied GUIDE datasets..."

while [[ ! -s "$TRAIN" || ! -s "$TEST" ]]; do
  echo "[WAIT] Both files are required in: $INPUT"
  echo "       $TRAIN"
  echo "       $TEST"
  echo "       Missing files are NOT downloaded and existing files are NOT deleted."
  sleep 15
done

echo "[OK] GUIDE_Train.csv found: $TRAIN"
echo "[OK] GUIDE_Test.csv  found: $TEST"
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

echo "[3/8] Checking dataset stability..."
while true; do
  if wait_stable "$TRAIN" && wait_stable "$TEST"; then
    echo "[OK] Both files are stable."
    break
  fi
  echo "[WAIT] Files are still being copied/changed."
  sleep 10
done
echo

# The processor reads from its own ROOT/data_finished path. Mirror the two
# manually supplied files into that runtime input directory without changing
# the original Data_mission copies.
echo "[4/8] Preparing runtime input..."
RUNTIME_INPUT="$RUNTIME/data_finished"
mkdir -p "$RUNTIME_INPUT"
cp --reflink=auto "$TRAIN" "$RUNTIME_INPUT/GUIDE_Train.csv"
cp --reflink=auto "$TEST" "$RUNTIME_INPUT/GUIDE_Test.csv"

echo "[OK] Runtime input prepared: $RUNTIME_INPUT"
echo

while [[ ! -f "$PROCESSOR" ]]; do
  echo "[WAIT] Processor not available: $PROCESSOR"
  git -C "$RUNTIME" fetch origin main 2>/dev/null || true
  git -C "$RUNTIME" reset --hard origin/main 2>/dev/null || true
  sleep 10
done

echo "[OK] Processor found."
echo

STAMP=$(date -u '+%Y%m%d_%H%M%S')
LOG="$LOGS/mission_${STAMP}.log"
ARCHIVE_RUN="$ARCHIVE/$STAMP"
mkdir -p "$ARCHIVE_RUN"

echo "[5/8] Running memory-safe processing..."
echo "[LOG] $LOG"
echo

if python3 "$PROCESSOR" 2>&1 | tee "$LOG"; then

  echo
  echo "[6/8] Processing succeeded."

  # Archive the manually supplied source files only after successful processing.
  mv "$TRAIN" "$ARCHIVE_RUN/GUIDE_Train.csv"
  mv "$TEST" "$ARCHIVE_RUN/GUIDE_Test.csv"
  cp "$LOG" "$ARCHIVE_RUN/mission.log"

  echo "[OK] Input datasets archived:"
  echo "     $ARCHIVE_RUN"

else

  echo
  echo "[ERROR] Processing failed."
  echo "[INFO] Original input datasets were NOT moved by this step."
  echo "[INFO] Log: $LOG"
  echo "[INFO] Runtime copies remain under: $RUNTIME_INPUT"
fi

echo
echo "[7/8] Checking outputs..."
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
echo "[8/8] Mission status"
echo "=============================================================="
echo "80 live alerts are required: LIVE-0001 ... LIVE-0080"
echo "Train/test/live disjointness is verified by the processor."
echo "Runtime source: $RUNTIME"
echo "Mission input : $INPUT"
echo "=============================================================="
