#!/usr/bin/env bash

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MISSION="$HOME/Desktop/Data_mission"
INPUT="$MISSION/data_finished"
PROCESSOR="$ROOT/scripts/process_data_finished.py"
LOGS="$MISSION/logs"
ARCHIVE="$MISSION/archive"
DOWNLOAD_ROOT="$INPUT/kaggle_download"

mkdir -p "$INPUT" "$LOGS" "$ARCHIVE" "$DOWNLOAD_ROOT"

echo "=============================================================="
echo " DATA_MISSION — KAGGLE -> PROCESS -> RL DATA"
echo "=============================================================="
echo "MISSION   : $MISSION"
echo "RL_AGENT  : $ROOT"
echo "INPUT     : $INPUT"
echo "PROCESSOR : $PROCESSOR"
echo

while [[ ! -f "$PROCESSOR" ]]; do
  echo "[WAIT] Processor not available yet: $PROCESSOR"
  sleep 10
  git -C "$ROOT" fetch origin main 2>/dev/null || true
  git -C "$ROOT" reset --hard origin/main 2>/dev/null || true
done

echo "[OK] Processor found."
echo

if python3 -c "import kagglehub" >/dev/null 2>&1; then
  echo "[OK] kagglehub is installed."
else
  echo "[INSTALL] Installing latest kagglehub..."
  if python3 -m pip install --user --upgrade kagglehub; then
    echo "[OK] kagglehub installed/updated."
  else
    echo "[ERROR] Could not install kagglehub. Retrying in 30 seconds."
    sleep 30
    while true; do sleep 30; done
  fi
fi

python3 - <<PY
import importlib.metadata
print("[KAGGLEHUB] version:", importlib.metadata.version("kagglehub"))
PY

export INPUT DOWNLOAD_ROOT

download_dataset() {
python3 - <<'PY'
import os
import shutil
from pathlib import Path
import kagglehub

out = Path(os.environ["DOWNLOAD_ROOT"])
out.mkdir(parents=True, exist_ok=True)

sources = [
    "microsoft/microsoft-security-incident-prediction",
    "avijitjana101/microsoft-soc-dataset",
]

train_name = "GUIDE_Train.csv"
test_name = "GUIDE_Test.csv"

for old in (out / train_name, out / test_name):
    try:
        old.unlink()
    except FileNotFoundError:
        pass

for slug in sources:
    print(f"[DOWNLOAD] Trying Kaggle dataset: {slug}", flush=True)
    try:
        # IMPORTANT: output_dir is the local destination directory.
        # path is NOT used here; with older kagglehub versions that caused
        # the local absolute path to be sent as a remote file_name.
        downloaded = Path(
            kagglehub.dataset_download(
                slug,
                output_dir=str(out),
                force_download=True,
            )
        )

        print(f"[DOWNLOAD] Resolver returned: {downloaded}", flush=True)

        train = next(downloaded.rglob(train_name), None)
        test = next(downloaded.rglob(test_name), None)

        # Some versions return the exact file path or a cache path.
        if train is None and downloaded.name == train_name:
            train = downloaded
        if test is None and downloaded.name == test_name:
            test = downloaded

        if train is not None and test is not None:
            target_train = out / train_name
            target_test = out / test_name

            if train.resolve() != target_train.resolve():
                shutil.copy2(train, target_train)
            if test.resolve() != target_test.resolve():
                shutil.copy2(test, target_test)

            print(f"[FOUND] {target_train}", flush=True)
            print(f"[FOUND] {target_test}", flush=True)
            print("[SUCCESS] GUIDE train/test downloaded.", flush=True)
            break

        print(
            f"[WARN] {slug}: GUIDE_Train.csv and GUIDE_Test.csv were not found in {downloaded}",
            flush=True,
        )

    except Exception as exc:
        print(f"[WARN] {slug}: {exc}", flush=True)
else:
    print("[ERROR] No Kaggle source produced both GUIDE files.", flush=True)
    raise RuntimeError("Kaggle GUIDE download failed")
PY
}

while true; do

  echo "[DOWNLOAD] Starting GUIDE download..."
  rm -rf "$DOWNLOAD_ROOT"
  mkdir -p "$DOWNLOAD_ROOT"

  if download_dataset; then
    TRAIN="$INPUT/GUIDE_Train.csv"
    TEST="$INPUT/GUIDE_Test.csv"

    if [[ -f "$DOWNLOAD_ROOT/GUIDE_Train.csv" && -f "$DOWNLOAD_ROOT/GUIDE_Test.csv" ]]; then
      cp "$DOWNLOAD_ROOT/GUIDE_Train.csv" "$TRAIN"
      cp "$DOWNLOAD_ROOT/GUIDE_Test.csv" "$TEST"
      rm -rf "$DOWNLOAD_ROOT"
      echo "[OK] GUIDE files copied to: $INPUT"
      ls -lh "$TRAIN" "$TEST"
      break
    fi
  fi

  echo "[WAIT] Download failed. Retrying in 30 seconds..."
  sleep 30

done

wait_stable() {
  local file="$1"
  local a b

  [[ -s "$file" ]] || return 1

  a=$(stat -c '%s' "$file" 2>/dev/null || printf '0')
  sleep 3
  b=$(stat -c '%s' "$file" 2>/dev/null || printf '0')

  [[ "$a" == "$b" ]]
}

TRAIN="$INPUT/GUIDE_Train.csv"
TEST="$INPUT/GUIDE_Test.csv"

if ! wait_stable "$TRAIN" || ! wait_stable "$TEST"; then
  echo "[ERROR] Downloaded dataset files are not stable."
  echo "[INFO] Train: $TRAIN"
  echo "[INFO] Test : $TEST"
  sleep 30
else
  echo "[OK] Dataset files are stable."
fi

while true; do
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
    break
  else
    echo
    echo "[ERROR] Processor failed."
    echo "[INFO] Input files remain in $INPUT."
    echo "[LOG]  $log_file"
    sleep 30
  fi
done

echo
echo "=============================================================="
echo " MISSION FINISHED"
echo "=============================================================="
