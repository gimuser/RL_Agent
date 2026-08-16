#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MISSION="$ROOT/data_finishe_mission"
INPUT="$ROOT/data_finished"
PROCESSOR="$ROOT/scripts/process_data_finished.py"
LOGS="$MISSION/logs"
ARCHIVE="$MISSION/archive"

mkdir -p "$INPUT" "$LOGS" "$ARCHIVE"

echo "=============================================================="
echo " DATA_FINISHE_MISSION — KAGGLE -> PROCESS -> RL DATA"
echo "=============================================================="
echo "ROOT      : $ROOT"
echo "INPUT     : $INPUT"
echo "PROCESSOR : $PROCESSOR"
echo

if [[ ! -f "$PROCESSOR" ]]; then
  echo "[ERROR] Missing processor: $PROCESSOR"
  echo "[INFO] Run: git fetch origin main && git reset --hard origin/main"
  while [[ ! -f "$PROCESSOR" ]]; do sleep 10; done
fi

python3 - <<'PY'
import importlib.util
import subprocess
import sys

if importlib.util.find_spec("kagglehub") is None:
    print("[INSTALL] Installing kagglehub ...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "kagglehub"])
PY

export ROOT INPUT

python3 - <<'PY'
import os
import shutil
from pathlib import Path

import kagglehub

root = Path(os.environ["ROOT"])
out = Path(os.environ["INPUT"])
out.mkdir(parents=True, exist_ok=True)

sources = [
    "microsoft/microsoft-security-incident-prediction",
    "avijitjana101/microsoft-soc-dataset",
]

needed = {"GUIDE_Train.csv", "GUIDE_Test.csv"}
last_error = None

for slug in sources:
    print(f"[DOWNLOAD] Trying Kaggle dataset: {slug}", flush=True)
    try:
        downloaded = Path(kagglehub.dataset_download(slug))
        train = next(downloaded.rglob("GUIDE_Train.csv"), None)
        test = next(downloaded.rglob("GUIDE_Test.csv"), None)
        if train and test:
            target_train = out / "GUIDE_Train.csv"
            target_test = out / "GUIDE_Test.csv"
            shutil.copy2(train, target_train)
            shutil.copy2(test, target_test)
            print(f"[DOWNLOAD] GUIDE_Train.csv -> {target_train}", flush=True)
            print(f"[DOWNLOAD] GUIDE_Test.csv  -> {target_test}", flush=True)
            break
        last_error = FileNotFoundError(f"{slug}: GUIDE_Train.csv and GUIDE_Test.csv not found")
        print(f"[WARN] {last_error}", flush=True)
    except Exception as exc:
        last_error = exc
        print(f"[WARN] {slug}: {exc}", flush=True)
else:
    raise SystemExit(f"[ERROR] Could not obtain GUIDE train/test from Kaggle: {last_error}")
PY

wait_stable() {
  local file="$1"
  local a b
  [[ -s "$file" ]] || return 1
  a=$(stat -c '%s' "$file")
  sleep 2
  b=$(stat -c '%s' "$file")
  [[ "$a" == "$b" ]]
}

TRAIN="$INPUT/GUIDE_Train.csv"
TEST="$INPUT/GUIDE_Test.csv"

if ! wait_stable "$TRAIN" || ! wait_stable "$TEST"; then
  echo "[ERROR] Downloaded dataset files are not stable."
  echo "[INFO] Train: $TRAIN"
  echo "[INFO] Test : $TEST"
  while true; do sleep 30; done
fi

tag=$(date -u '+%Y%m%d_%H%M%S')
log_file="$LOGS/mission_${tag}.log"
archive_dir="$ARCHIVE/$tag"
mkdir -p "$archive_dir"


echo
echo "[PROCESS] Starting memory-safe processor..."
echo "[LOG] $log_file"

if python3 "$PROCESSOR" 2>&1 | tee "$log_file"; then
  echo
  echo "[SUCCESS] Processing completed."
  mv "$TRAIN" "$archive_dir/GUIDE_Train.csv"
  mv "$TEST" "$archive_dir/GUIDE_Test.csv"
  cp "$log_file" "$archive_dir/mission.log"
  echo "[ARCHIVE] $archive_dir"
  echo "[OUTPUT]  $ROOT/data/rl_incident/train_incident.csv"
  echo "[OUTPUT]  $ROOT/data/rl_incident/test_incident.csv"
  echo "[LIVE]    $ROOT/data_alert/live_source.csv"
  echo "[LIVE]    $ROOT/data_alert/live_processed.csv"
else
  echo
  echo "[ERROR] Processor failed."
  echo "[INFO] Input files remain in $INPUT for inspection/retry."
  echo "[LOG]  $log_file"
fi

echo
echo "=============================================================="
echo " MISSION FINISHED"
echo "=============================================================="
