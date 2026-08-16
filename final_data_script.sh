#!/usr/bin/env bash
set -e

###############################################################################
# DATA_MISSION FINAL DATA SCRIPT
#
# Local sources:
#   ~/Desktop/Data_mission/data_finished/GUIDE_Train.csv
#   ~/Desktop/Data_mission/data_finished/GUIDE_Test.csv
#
# Read-only reference:
#   ~/Desktop/new_one/RL_Agent/backend/app/data_pipeline
#
# Outputs are created ONLY under ~/Desktop/Data_mission/generated_final.
# The reference project and original GUIDE files are never modified.
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

# ---------------------------------------------------------------------------
# 1. INPUT CHECKS
# ---------------------------------------------------------------------------

echo "[1/12] Checking inputs..."
test -d "$ROOT"
test -f "$TRAIN_GUIDE"
test -f "$TEST_GUIDE"
test -d "$REF_PIPELINE"
echo "[OK] GUIDE_Train.csv"
echo "[OK] GUIDE_Test.csv"
echo "[OK] old backend/app/data_pipeline"
echo "[OK] reference project is READ-ONLY"

# ---------------------------------------------------------------------------
# 2. OWN WORKSPACE ONLY
# ---------------------------------------------------------------------------

echo
echo "[2/12] Cleaning only our generated workspace..."
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$TEMP/backend/app/data_pipeline" "$TEMP/data/processed" "$TEMP/models" "$TEMP/data/raw" "$REDUCED" "$PROCESSED" "$LIVE" "$INCIDENT" "$REPORT"
echo "[OK] workspace ready"

# ---------------------------------------------------------------------------
# 3. COPY THE ACTUAL OLD PIPELINE
# ---------------------------------------------------------------------------

echo
echo "[3/12] Copying actual old pipeline into temporary workspace..."
cp -a "$REF_PIPELINE"/. "$TEMP/backend/app/data_pipeline/"
for f in loader.py cleaner.py validator.py encoder.py feature_engineering.py normalizer.py preprocessor.py exporter.py; do
  test -f "$TEMP/backend/app/data_pipeline/$f"
  echo "  [OK] $f"
done

# ---------------------------------------------------------------------------
# 4. SOURCE REDUCTION + EXACT DEDUP
# ---------------------------------------------------------------------------

echo
echo "[4/12] Reducing both GUIDE files to 13 columns and removing exact duplicates..."
"$PYTHON" - "$TRAIN_GUIDE" "$TEST_GUIDE" "$REDUCED" "$WORK" "$CHUNK" <<'PY'
import csv
import hashlib
import sqlite3
import sys
from pathlib import Path

train_path = Path(sys.argv[1])
test_path = Path(sys.argv[2])
out_dir = Path(sys.argv[3])
work_dir = Path(sys.argv[4])
chunk_size = int(sys.argv[5])

KEEP = [
    "IncidentId", "Timestamp", "Category", "MitreTechniques", "IncidentGrade",
    "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily",
    "OSFamily", "SuspicionLevel", "LastVerdict",
]


def digest_row(values):
    h = hashlib.sha256()
    for value in values:
        b = str(value).encode("utf-8", errors="surrogatepass")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.digest()


def reduce_file(source, destination):
    db_path = work_dir / f"{source.stem}_dedup.sqlite3"
    db_path.unlink(missing_ok=True)

    db = sqlite3.connect(db_path)
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA temp_store=FILE")
    db.execute("CREATE TABLE seen (k BLOB PRIMARY KEY)")

    total = kept = duplicates = 0

    with source.open("r", encoding="utf-8-sig", newline="") as fin:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            raise RuntimeError(f"No header: {source}")
        missing = [c for c in KEEP if c not in reader.fieldnames]
        if missing:
            raise RuntimeError(f"{source} missing columns: {missing}")

        with destination.open("w", encoding="utf-8", newline="") as fout:
            writer = csv.writer(fout)
            writer.writerow(KEEP)

            for row in reader:
                total += 1
                values = tuple((row.get(c) or "").strip() for c in KEEP)
                k = digest_row(values)
                cur = db.execute("INSERT OR IGNORE INTO seen(k) VALUES (?)", (k,))
                if cur.rowcount == 0:
                    duplicates += 1
                    continue
                writer.writerow(values)
                kept += 1
                if total % 500000 == 0:
                    db.commit()
                    print(f"    {source.name}: seen={total:,} kept={kept:,} exact_dups={duplicates:,}", flush=True)

    db.commit()
    db.close()
    db_path.unlink(missing_ok=True)

    print(f"[OK] {source.name}: input={total:,} kept={kept:,} exact_duplicates={duplicates:,}")
    return total, kept, duplicates

reduce_file(train_path, out_dir / "train_13cols.csv")
reduce_file(test_path, out_dir / "test_13cols.csv")
PY

# ---------------------------------------------------------------------------
# 5. INCIDENT LEAKAGE RESOLUTION BEFORE PIPELINE
# ---------------------------------------------------------------------------

echo
echo "[5/12] Resolving TRAIN/TEST IncidentId overlap (preserve TEST)..."
"$PYTHON" - "$REDUCED/train_13cols.csv" "$REDUCED/test_13cols.csv" <<'PY'
import csv
import sys
from pathlib import Path

train_path = Path(sys.argv[1])
test_path = Path(sys.argv[2])
KEEP = [
    "IncidentId", "Timestamp", "Category", "MitreTechniques", "IncidentGrade",
    "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily",
    "OSFamily", "SuspicionLevel", "LastVerdict",
]


def ids(path):
    out = set()
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out.add(str(row["IncidentId"]))
    return out

train_ids = ids(train_path)
test_ids = ids(test_path)
overlap = train_ids & test_ids
print("Before overlap resolution:", len(overlap))

if overlap:
    tmp = train_path.with_suffix(".tmp")
    removed = 0
    with train_path.open("r", encoding="utf-8", newline="") as fin, tmp.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=KEEP)
        writer.writeheader()
        for row in reader:
            if str(row["IncidentId"]) in overlap:
                removed += 1
                continue
            writer.writerow(row)
    tmp.replace(train_path)
    print("Removed TRAIN rows belonging to overlapping incidents:", removed)

train_ids = ids(train_path)
test_ids = ids(test_path)
final_overlap = train_ids & test_ids
print("After overlap resolution:", len(final_overlap))

if final_overlap:
    raise RuntimeError("TRAIN/TEST IncidentId overlap remains")
PY

# ---------------------------------------------------------------------------
# 6. PUT 13-COLUMN FILES WHERE THE ACTUAL OLD LOADER EXPECTS THEM
# ---------------------------------------------------------------------------

echo
echo "[6/12] Preparing temporary project for the actual old imports..."
cp "$REDUCED/train_13cols.csv" "$TEMP/data/processed/train_processed.csv"
cp "$REDUCED/test_13cols.csv" "$TEMP/data/processed/test_processed.csv"
echo "[OK] temporary data/processed ready"

# ---------------------------------------------------------------------------
# 7. RUN ACTUAL OLD PIPELINE MODULES
# ---------------------------------------------------------------------------

echo
echo "[7/12] Running actual old backend/app/data_pipeline..."
(
  cd "$TEMP"
  PYTHONPATH="$TEMP/backend/app/data_pipeline" "$PYTHON" - "$PROCESSED" <<'PY'
import sys
from pathlib import Path

out = Path(sys.argv[1])
sys.path.insert(0, str(Path.cwd() / "backend/app/data_pipeline"))

# EXACT old imports.
from loader import load_train_data, load_test_data
from cleaner import clean_data
from validator import validate_data
from encoder import encode_data
from feature_engineering import create_features
from normalizer import normalize_data

print("===== LOADING DATA =====")
train = load_train_data()
test = load_test_data()
print("TRAIN:", train.shape)
print("TEST :", test.shape)

print("\n===== CLEANING =====")
train = clean_data(train)
test = clean_data(test)
print("TRAIN:", train.shape)
print("TEST :", test.shape)

print("\n===== VALIDATION =====")
if not validate_data(train, "TRAIN"):
    raise RuntimeError("TRAIN validation failed")
if not validate_data(test, "TEST"):
    raise RuntimeError("TEST validation failed")

print("\n===== ENCODING =====")
train, test = encode_data(train, test)

print("\n===== FEATURE ENGINEERING =====")
train, test = create_features(train, test)

print("\n===== NORMALIZATION =====")
train, test = normalize_data(train, test)

print("\n===== OLD PIPELINE FINISHED =====")
print("TRAIN:", train.shape)
print("TEST :", test.shape)

out.mkdir(parents=True, exist_ok=True)
train.to_csv(out / "train_processed.csv", index=False)
test.to_csv(out / "test_processed.csv", index=False)
PY
)

# ---------------------------------------------------------------------------
# 8. VERIFY 17-COLUMN PROCESSED OUTPUTS
# ---------------------------------------------------------------------------

echo
echo "[8/12] Verifying processed TRAIN/TEST..."
"$PYTHON" - "$PROCESSED/train_processed.csv" "$PROCESSED/test_processed.csv" <<'PY'
import csv
import sys
from pathlib import Path

train_path = Path(sys.argv[1])
test_path = Path(sys.argv[2])
EXPECTED = [
    "IncidentId", "Timestamp", "Category", "MitreTechniques", "IncidentGrade",
    "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily",
    "OSFamily", "SuspicionLevel", "LastVerdict", "hour", "day", "month", "is_weekend",
]

def check(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = sum(1 for _ in reader)
    if header != EXPECTED:
        raise RuntimeError(f"Wrong schema in {path}: {header}")
    if rows == 0:
        raise RuntimeError(f"Empty processed file: {path}")
    print(f"{path.name}: {rows:,} rows, {len(header)} columns")

check(train_path)
check(test_path)
PY

# ---------------------------------------------------------------------------
# 9. EXACT OLD-STYLE LIVE EXTRACTION: 80 TOTAL, ONE PER INCIDENT
#    Mapping = normalized Timestamp + occurrence number, as in repository.
# ---------------------------------------------------------------------------

echo
echo "[9/12] Extracting exactly 80 live alerts..."
"$PYTHON" - "$REDUCED/train_13cols.csv" "$REDUCED/test_13cols.csv" "$PROCESSED/train_processed.csv" "$PROCESSED/test_processed.csv" "$LIVE" "$SEED" "$LIVE_TOTAL" <<'PY'
import csv, json, random, sys
from datetime import datetime, timezone
from pathlib import Path

train_source = Path(sys.argv[1])
test_source = Path(sys.argv[2])
train_processed = Path(sys.argv[3])
test_processed = Path(sys.argv[4])
live_dir = Path(sys.argv[5])
seed = int(sys.argv[6])
n_live = int(sys.argv[7])

SOURCE_COLUMNS = [
    "IncidentId", "Timestamp", "Category", "MitreTechniques", "IncidentGrade",
    "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily",
    "OSFamily", "SuspicionLevel", "LastVerdict",
]

random.seed(seed)

def read(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def tskey(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()

def build_lineage(source_rows, processed_rows, split):
    sgroups = {}
    pgroups = {}
    for i, row in enumerate(source_rows):
        sgroups.setdefault(tskey(row["Timestamp"]), []).append((i, row))
    for i, row in enumerate(processed_rows):
        pgroups.setdefault(tskey(row["Timestamp"]), []).append((i, row))
    out = []
    for key, srows in sgroups.items():
        prows = pgroups.get(key, [])
        for occurrence in range(min(len(srows), len(prows))):
            si, sr = srows[occurrence]
            pi, pr = prows[occurrence]
            out.append({
                "source_split": split,
                "source_row_number": si,
                "processed_row_number": pi,
                "IncidentId": str(sr["IncidentId"]),
                "Timestamp": sr["Timestamp"],
                "source_row": sr,
                "processed_row": pr,
            })
    return out

train_s = read(train_source)
test_s = read(test_source)
train_p = read(train_processed)
test_p = read(test_processed)

train_lineage = build_lineage(train_s, train_p, "train")
test_lineage = build_lineage(test_s, test_p, "test")
print("TRAIN mapped rows:", len(train_lineage))
print("TEST mapped rows :", len(test_lineage))

# One candidate per unique incident across both final populations.
candidates = []
seen = set()
for item in train_lineage + test_lineage:
    iid = item["IncidentId"]
    if iid in seen:
        continue
    seen.add(iid)
    candidates.append(item)

if len(candidates) < n_live:
    raise RuntimeError(f"Only {len(candidates)} unique mapped incidents; need {n_live}")

selected = random.sample(candidates, n_live)
selected.sort(key=lambda x: (tskey(x["Timestamp"]), x["IncidentId"]))

for n, item in enumerate(selected, 1):
    item["alert_id"] = f"LIVE-{n:04d}"

live_ids = {x["IncidentId"] for x in selected}
if len(live_ids) != n_live:
    raise RuntimeError("LIVE IncidentId values are not unique")

# live_source.csv
with (live_dir / "live_source.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["alert_id"] + SOURCE_COLUMNS)
    writer.writeheader()
    for item in selected:
        writer.writerow({"alert_id": item["alert_id"], **{c: item["source_row"][c] for c in SOURCE_COLUMNS}})

# live_processed.csv: exact counterparts, not re-created rows.
with (live_dir / "live_processed.csv").open("w", encoding="utf-8", newline="") as f:
    processed_fields = list(selected[0]["processed_row"].keys())
    writer = csv.DictWriter(f, fieldnames=["alert_id"] + processed_fields)
    writer.writeheader()
    for item in selected:
        writer.writerow({"alert_id": item["alert_id"], **item["processed_row"]})

# live_mapping.csv: same lineage fields as repository.
with (live_dir / "live_mapping.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["alert_id", "IncidentId", "Timestamp", "source_row_number", "processed_row_number"])
    writer.writeheader()
    for item in selected:
        writer.writerow({
            "alert_id": item["alert_id"],
            "IncidentId": item["IncidentId"],
            "Timestamp": item["Timestamp"],
            "source_row_number": item["source_row_number"],
            "processed_row_number": item["processed_row_number"],
        })

(live_dir / "live_incidents.txt").write_text(
    "\n".join(sorted(live_ids)) + "\n",
    encoding="utf-8"
)

manifest = {
    "requested_alerts": n_live,
    "selected_alerts": len(selected),
    "selected_incidents": len(live_ids),
    "random_seed": seed,
    "selection_rule": "one alert per unique IncidentId",
    "mapping_rule": "normalized Timestamp + occurrence number",
    "source_counts": {
        "train": sum(1 for x in selected if x["source_split"] == "train"),
        "test": sum(1 for x in selected if x["source_split"] == "test"),
    },
}
(live_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("LIVE TOTAL:", len(selected))
print("LIVE UNIQUE INCIDENTS:", len(live_ids))
print("FROM TRAIN:", manifest["source_counts"]["train"])
print("FROM TEST :", manifest["source_counts"]["test"])
PY

# ---------------------------------------------------------------------------
# 10. HOLD OUT LIVE INCIDENTS FROM PROCESSED TRAIN/TEST
# ---------------------------------------------------------------------------

echo
echo "[10/12] Removing all 80 live incidents from final processed TRAIN/TEST..."
"$PYTHON" - "$PROCESSED/train_processed.csv" "$PROCESSED/test_processed.csv" "$LIVE/live_incidents.txt" <<'PY'
import csv, sys
from pathlib import Path

train_path = Path(sys.argv[1])
test_path = Path(sys.argv[2])
live_ids_path = Path(sys.argv[3])
live_ids = {x.strip() for x in live_ids_path.read_text(encoding="utf-8").splitlines() if x.strip()}

def holdout(path):
    tmp = path.with_suffix(".tmp")
    kept = removed = 0
    with path.open("r", encoding="utf-8", newline="") as fin, tmp.open("w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            if str(row["IncidentId"]) in live_ids:
                removed += 1
                continue
            writer.writerow(row)
            kept += 1
    tmp.replace(path)
    return kept, removed

tr = holdout(train_path)
te = holdout(test_path)
print("TRAIN kept/removed:", tr)
print("TEST  kept/removed:", te)
PY

# ---------------------------------------------------------------------------
# 11. INCIDENT-LEVEL DATA LIKE data/rl_incident
#     Keep ALL rows of each incident together.
#     Split final TRAIN population 75/25 by IncidentId into TRAIN/VALIDATION.
#     Final TEST population remains TEST.
# ---------------------------------------------------------------------------

echo
echo "[11/12] Creating incident-level TRAIN / VALIDATION / TEST datasets..."
"$PYTHON" - "$PROCESSED/train_processed.csv" "$PROCESSED/test_processed.csv" "$INCIDENT" "$SEED" <<'PY'
import csv, random, sys
from collections import defaultdict
from pathlib import Path

train_path = Path(sys.argv[1])
test_path = Path(sys.argv[2])
out = Path(sys.argv[3])
seed = int(sys.argv[4])

random.seed(seed)

def read(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)

def group(rows):
    g = defaultdict(list)
    for row in rows:
        g[str(row["IncidentId"])].append(row)
    return g

train_fields, train_rows = read(train_path)
test_fields, test_rows = read(test_path)
train_groups = group(train_rows)
test_groups = group(test_rows)
train_ids = set(train_groups)
test_ids = set(test_groups)

if train_ids & test_ids:
    raise RuntimeError("TRAIN/TEST IncidentId overlap before incident split")

train_list = list(train_ids)
random.shuffle(train_list)
validation_count = int(len(train_list) * 0.25)
validation_ids = set(train_list[:validation_count])
final_train_ids = set(train_list[validation_count:])

assert not (final_train_ids & validation_ids)
assert not (final_train_ids & test_ids)
assert not (validation_ids & test_ids)


def write(path, fields, groups, ids):
    rows = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for iid in sorted(ids):
            for row in groups[iid]:
                writer.writerow(row)
                rows += 1
    return rows

train_rows_written = write(out / "train_incident.csv", train_fields, train_groups, final_train_ids)
validation_rows_written = write(out / "validation_incident.csv", train_fields, train_groups, validation_ids)
test_rows_written = write(out / "test_incident.csv", test_fields, test_groups, test_ids)

(out / "train_incidents.txt").write_text("\n".join(sorted(final_train_ids)) + "\n", encoding="utf-8")
(out / "validation_incidents.txt").write_text("\n".join(sorted(validation_ids)) + "\n", encoding="utf-8")
(out / "test_incidents.txt").write_text("\n".join(sorted(test_ids)) + "\n", encoding="utf-8")

import json
report = {
    "source_rows": len(train_rows) + len(test_rows),
    "train_rows": train_rows_written,
    "validation_rows": validation_rows_written,
    "test_rows": test_rows_written,
    "train_incidents": len(final_train_ids),
    "validation_incidents": len(validation_ids),
    "test_incidents": len(test_ids),
    "incident_overlap": 0,
    "features": [
        "Category", "MitreTechniques", "ActionGrouped", "ActionGranular",
        "EntityType", "EvidenceRole", "ThreatFamily", "OSFamily",
        "SuspicionLevel", "hour", "day", "month", "is_weekend"
    ],
    "incident_id": "IncidentId",
    "target": "IncidentGrade"
}
(out / "split_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

print("TRAIN rows/incidents:", train_rows_written, len(final_train_ids))
print("VALIDATION rows/incidents:", validation_rows_written, len(validation_ids))
print("TEST rows/incidents:", test_rows_written, len(test_ids))
print("TRAIN/VALIDATION/TEST incident overlap: 0")
PY

# ---------------------------------------------------------------------------
# 12. FINAL AUDIT
# ---------------------------------------------------------------------------

echo
echo "[12/12] FINAL AUDIT"
"$PYTHON" - "$ROOT" <<'PY'
import csv, json, sys
from pathlib import Path

root = Path(sys.argv[1])
out = root / "generated_final"
processed = out / "processed"
incident = out / "data_incident"
live = out / "data_alert"
source = out / "source_13cols"

EXPECTED = [
    "IncidentId", "Timestamp", "Category", "MitreTechniques", "IncidentGrade",
    "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily",
    "OSFamily", "SuspicionLevel", "LastVerdict", "hour", "day", "month", "is_weekend",
]

def read(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)

def ids(rows):
    return {str(r["IncidentId"]) for r in rows}

def exact_dups(path):
    seen = set(); d = 0
    with path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f); header = next(r)
        for row in r:
            t = tuple(row)
            if t in seen: d += 1
            else: seen.add(t)
    return d

for split in ["train", "test"]:
    fields, rows = read(processed / f"{split}_processed.csv")
    if fields != EXPECTED:
        raise RuntimeError(f"Bad processed schema: {split}")
    print(f"processed {split}: {len(rows):,} rows / {len(fields)} columns")
    print(f"processed {split} exact duplicates: {exact_dups(processed / f'{split}_processed.csv')}")

train_fields, train_rows = read(incident / "train_incident.csv")
val_fields, val_rows = read(incident / "validation_incident.csv")
test_fields, test_rows = read(incident / "test_incident.csv")
train_ids = ids(train_rows)
val_ids = ids(val_rows)
test_ids = ids(test_rows)

live_source_fields, live_source_rows = read(live / "live_source.csv")
live_processed_fields, live_processed_rows = read(live / "live_processed.csv")
live_mapping_fields, live_mapping_rows = read(live / "live_mapping.csv")
live_ids = ids(live_source_rows)

if len(live_source_rows) != 80: raise RuntimeError("LIVE source != 80")
if len(live_processed_rows) != 80: raise RuntimeError("LIVE processed != 80")
if len(live_mapping_rows) != 80: raise RuntimeError("LIVE mapping != 80")
if len(live_ids) != 80: raise RuntimeError("LIVE unique IncidentId != 80")
if train_ids & val_ids: raise RuntimeError("TRAIN/VALIDATION overlap")
if train_ids & test_ids: raise RuntimeError("TRAIN/TEST overlap")
if val_ids & test_ids: raise RuntimeError("VALIDATION/TEST overlap")
if live_ids & train_ids: raise RuntimeError("LIVE/TRAIN overlap")
if live_ids & val_ids: raise RuntimeError("LIVE/VALIDATION overlap")
if live_ids & test_ids: raise RuntimeError("LIVE/TEST overlap")

manifest = {
    "status": "SUCCESS",
    "processed_train_rows": len(train_rows),
    "processed_test_rows": len(test_rows),
    "incident_train_rows": len(train_rows),
    "incident_validation_rows": len(val_rows),
    "incident_test_rows": len(test_rows),
    "train_incidents": len(train_ids),
    "validation_incidents": len(val_ids),
    "test_incidents": len(test_ids),
    "live_total": len(live_source_rows),
    "live_unique_incidents": len(live_ids),
    "overlaps": {
        "train_validation": 0,
        "train_test": 0,
        "validation_test": 0,
        "live_train": 0,
        "live_validation": 0,
        "live_test": 0
    },
    "reference_pipeline": str(root.parent / "new_one/RL_Agent/backend/app/data_pipeline")
}

(out / "reports" / "final_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print()
print("======================================================================")
print(" ALL FINAL CHECKS PASSED")
print("======================================================================")
print("13 source columns          : OK")
print("17 processed columns       : OK")
print("TRAIN/VALIDATION overlap   : 0")
print("TRAIN/TEST overlap         : 0")
print("VALIDATION/TEST overlap    : 0")
print("LIVE TOTAL                 : 80")
print("LIVE unique incidents      : 80")
print("LIVE/TRAIN overlap         : 0")
print("LIVE/VALIDATION overlap    : 0")
print("LIVE/TEST overlap          : 0")
print("Original GUIDE files       : untouched")
print("new_one/RL_Agent           : untouched")
print("Report                     :", out / "reports/final_manifest.json")
PY

echo
echo "======================================================================"
echo " FINAL DATA SCRIPT FINISHED"
echo "======================================================================"
echo
echo "Generated root:"
echo "  $OUT"
echo
echo "Processed:"
echo "  $PROCESSED/train_processed.csv"
echo "  $PROCESSED/test_processed.csv"
echo
echo "Live (80 total):"
echo "  $LIVE/live_source.csv"
echo "  $LIVE/live_processed.csv"
echo "  $LIVE/live_mapping.csv"
echo "  $LIVE/live_incidents.txt"
echo "  $LIVE/manifest.json"
echo
echo "Incident datasets:"
echo "  $INCIDENT/train_incident.csv"
echo "  $INCIDENT/validation_incident.csv"
echo "  $INCIDENT/test_incident.csv"
echo "  $INCIDENT/split_report.json"
echo
echo "Reference project NOT modified:"
echo "  $REF"
echo
echo "======================================================================"

exit 0
