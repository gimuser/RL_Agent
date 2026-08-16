#!/usr/bin/env bash
set -e

###############################################################################
# DATA_MISSION FINAL DATA SCRIPT
#
# SOURCE (local machine only):
#   ~/Desktop/Data_mission/data_finished/GUIDE_Train.csv
#   ~/Desktop/Data_mission/data_finished/GUIDE_Test.csv
#
# REFERENCE PIPELINE (READ ONLY):
#   ~/Desktop/new_one/RL_Agent/backend/app/data_pipeline
#
# This script:
#   1) keeps exactly the 13 requested source columns;
#   2) removes exact duplicate 13-column rows with disk-backed SQLite;
#   3) resolves TRAIN/TEST IncidentId leakage, preserving TEST;
#   4) runs the actual old loader/cleaner/validator/encoder/
#      feature_engineering/normalizer from a temporary copy;
#   5) creates 17-column processed TRAIN/TEST;
#   6) extracts exactly 80 live alerts using the old live lineage idea:
#      one alert per unique IncidentId and Timestamp+occurrence mapping;
#   7) removes all selected live incidents from final TRAIN/TEST;
#   8) creates incident-level train/validation/test datasets like
#      data/rl_incident, keeping all rows of an incident together;
#   9) performs final zero-overlap checks.
#
# NEVER WRITES TO:
#   ~/Desktop/new_one/RL_Agent
#   data_finished/GUIDE_Train.csv
#   data_finished/GUIDE_Test.csv
###############################################################################

ROOT="$HOME/Desktop/Data_mission"
SOURCE="$ROOT/data_finished"
TRAIN_GUIDE="$SOURCE/GUIDE_Train.csv"
TEST_GUIDE="$SOURCE/GUIDE_Test.csv"

REF="$HOME/Desktop/new_one/RL_Agent"
REF_PIPELINE="$REF/backend/app/data_pipeline"

WORK="$ROOT/.final_data_script_work"
TEMP="$WORK/RL_Agent_temp"

OUT="$ROOT/generated_final"
REDUCED="$OUT/source_13cols"
PROCESSED="$OUT/processed"
LIVE="$OUT/data_alert"
INCIDENT="$OUT/data_incident"
REPORT="$OUT/reports"

PYTHON="${PYTHON_BIN:-python3}"
CHUNK=50000
LIVE_TOTAL=80
SEED=20260816

KEEP_COLUMNS=(
  IncidentId Timestamp Category MitreTechniques IncidentGrade
  ActionGrouped ActionGranular EntityType EvidenceRole ThreatFamily
  OSFamily SuspicionLevel LastVerdict
)

EXPECTED_PROCESSED=(
  IncidentId Timestamp Category MitreTechniques IncidentGrade
  ActionGrouped ActionGranular EntityType EvidenceRole ThreatFamily
  OSFamily SuspicionLevel LastVerdict hour day month is_weekend
)

echo
echo "======================================================================"
echo " FINAL DATA SCRIPT"
echo "======================================================================"
echo

echo "[1/12] Checking inputs..."
test -d "$ROOT"
test -f "$TRAIN_GUIDE"
test -f "$TEST_GUIDE"
test -d "$REF_PIPELINE"
echo "[OK] GUIDE_Train.csv"
echo "[OK] GUIDE_Test.csv"
echo "[OK] old backend/app/data_pipeline"
echo "[OK] new_one/RL_Agent will NOT be modified"

echo
echo "[2/12] Cleaning only our previous generated workspace..."
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$TEMP/backend/app/data_pipeline" "$TEMP/data/processed" "$TEMP/models" "$TEMP/data/raw" "$REDUCED" "$PROCESSED" "$LIVE" "$INCIDENT" "$REPORT"
echo "[OK] Workspace ready"

echo
echo "[3/12] Copying the ACTUAL old pipeline into temporary workspace..."
cp -a "$REF_PIPELINE"/. "$TEMP/backend/app/data_pipeline/"
for f in loader.py cleaner.py validator.py encoder.py feature_engineering.py normalizer.py preprocessor.py exporter.py; do
  test -f "$TEMP/backend/app/data_pipeline/$f"
  echo "  [OK] $f"
done

echo
echo "[4/12] Reducing both GUIDE files to the exact 13 source columns + exact dedup..."
"$PYTHON" - "$TRAIN_GUIDE" "$TEST_GUIDE" "$REDUCED" "$WORK" "$CHUNK" <<'PY'
import csv, hashlib, sqlite3, sys
from pathlib import Path

train_path, test_path, out_dir, work_dir, chunk_size = map(Path, sys.argv[1:5]) + (int(sys.argv[5]),)
PY
