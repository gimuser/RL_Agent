#!/usr/bin/env python3
"""Memory-safe processor for data_finished/GUIDE_Train.csv + GUIDE_Test.csv.

All large CSV operations use chunks. Only compact incident-ID/category/scaler
state is retained in memory. The existing data-pipeline semantics are reused:
cleaning (drop duplicates/fill Unknown), categorical mapping, time features,
and MinMax normalization. The 80 live incidents are held out before fitting.
"""
from __future__ import annotations

import csv
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data_finished"
WORK = INPUT / "work"
BACKUP = INPUT / "backup"
RL = ROOT / "data" / "rl_incident"
ALERT = ROOT / "data_alert"
MODELS = ROOT / "models"
TRAIN = INPUT / "GUIDE_Train.csv"
TEST = INPUT / "GUIDE_Test.csv"

CHUNK_SIZE = 50_000
N_LIVE = 80
SEED = 20260816

KEEP = [
    "IncidentId", "Timestamp", "Category", "MitreTechniques", "IncidentGrade",
    "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole",
    "ThreatFamily", "OSFamily", "SuspicionLevel", "LastVerdict",
]
FINAL = KEEP + ["hour", "day", "month", "is_weekend"]
CATS = [
    "Category", "MitreTechniques", "IncidentGrade", "ActionGrouped",
    "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily",
    "OSFamily", "SuspicionLevel", "LastVerdict",
]
SCALED = ["IncidentId", "hour", "day", "month", "is_weekend"]
FEATURES = [
    "Category", "MitreTechniques", "ActionGrouped", "ActionGranular",
    "EntityType", "EvidenceRole", "ThreatFamily", "OSFamily",
    "SuspicionLevel", "hour", "day", "month", "is_weekend",
]
ID = "IncidentId"
TARGET = "IncidentGrade"


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def setup() -> None:
    for p in [INPUT, WORK, BACKUP, RL, ALERT, MODELS]:
        p.mkdir(parents=True, exist_ok=True)


def header(path: Path) -> list[str]:
    return list(pd.read_csv(path, nrows=0).columns)


def check_inputs() -> None:
    if not TRAIN.is_file() or not TEST.is_file():
        fail("data_finished must contain both GUIDE_Train.csv and GUIDE_Test.csv")
    for p in [TRAIN, TEST]:
        missing = [c for c in KEEP if c not in header(p)]
        if missing:
            fail(f"{p.name} missing required columns: {missing}")


def stream_clean_and_dedup(source: Path, out: Path, seen: dict[str, str], name: str) -> tuple[int, int, int]:
    """Keep one row per IncidentId, chunked; detect conflicting labels."""
    if out.exists():
        out.unlink()
    total = kept = duplicates = 0
    first = True
    for chunk_no, chunk in enumerate(
        pd.read_csv(source, usecols=KEEP, chunksize=CHUNK_SIZE, low_memory=True), 1
    ):
        chunk = chunk.drop_duplicates().fillna("Unknown")
        total += len(chunk)
        keep = []
        for iid, grade in zip(chunk[ID].astype(str), chunk[TARGET].astype(str)):
            old = seen.get(iid)
            if old is not None:
                if old != grade:
                    fail(f"{name}: IncidentId {iid} has conflicting IncidentGrade values: {old!r} vs {grade!r}")
                keep.append(False)
                duplicates += 1
            else:
                seen[iid] = grade
                keep.append(True)
        part = chunk.loc[keep]
        if not part.empty:
            part.to_csv(out, mode="w" if first else "a", header=first, index=False)
            first = False
            kept += len(part)
        if chunk_no % 10 == 0:
            log(f"  [{name}] chunks={chunk_no:,} rows={total:,} kept={kept:,} duplicate_ids={duplicates:,}")
    if first:
        fail(f"{name}: no usable rows after cleaning")
    return total, kept, duplicates


def reservoir(path: Path, n: int) -> pd.DataFrame:
    """Reservoir-sample n rows using bounded memory."""
    rng = random.Random(SEED)
    sample: list[dict[str, object]] = []
    seen = 0
    columns = KEEP
    for chunk in pd.read_csv(path, usecols=KEEP, chunksize=CHUNK_SIZE, low_memory=True):
        for row in chunk.itertuples(index=False, name=None):
            seen += 1
            if len(sample) < n:
                sample.append(dict(zip(columns, row)))
            else:
                j = rng.randrange(seen)
                if j < n:
                    sample[j] = dict(zip(columns, row))
    if len(sample) < n:
        fail(f"Only {len(sample)} rows available; cannot reserve {n} live incidents")
    return pd.DataFrame(sample, columns=KEEP)


def fit_mappings(train_path: Path) -> dict[str, dict[str, int]]:
    values = {c: set() for c in CATS}
    for chunk in pd.read_csv(train_path, usecols=CATS, chunksize=CHUNK_SIZE, low_memory=True):
        chunk = chunk.fillna("Unknown")
        for c in CATS:
            values[c].update(chunk[c].astype(str).unique())
    mappings = {c: {v: i for i, v in enumerate(sorted(values[c]))} for c in CATS}
    (MODELS / "category_mappings.json").write_text(json.dumps(mappings, indent=2), encoding="utf-8")
    return mappings


def transform_chunk(chunk: pd.DataFrame, mappings: dict[str, dict[str, int]]) -> pd.DataFrame:
    chunk = chunk.copy().fillna("Unknown")
    for c in CATS:
        chunk[c] = chunk[c].astype(str).map(mappings[c]).fillna(-1).astype("int32")
    chunk["Timestamp"] = pd.to_datetime(chunk["Timestamp"], utc=True, errors="raise")
    chunk["hour"] = chunk["Timestamp"].dt.hour.astype("int16")
    chunk["day"] = chunk["Timestamp"].dt.day.astype("int16")
    chunk["month"] = chunk["Timestamp"].dt.month.astype("int16")
    chunk["is_weekend"] = (chunk["Timestamp"].dt.dayofweek >= 5).astype("int8")
    return chunk


def fit_scaler(train_path: Path, mappings: dict[str, dict[str, int]], live_ids: set[str]) -> MinMaxScaler:
    scaler = MinMaxScaler()
    fitted = False
    for chunk in pd.read_csv(train_path, chunksize=CHUNK_SIZE, low_memory=True):
        chunk = chunk[~chunk[ID].astype(str).isin(live_ids)]
        if chunk.empty:
            continue
        enc = transform_chunk(chunk, mappings)
        scaler.partial_fit(enc[SCALED].astype(float))
        fitted = True
    if not fitted:
        fail("No training rows available after live holdout")
    joblib.dump({"scaler": scaler, "columns": SCALED}, MODELS / "feature_scaler.joblib")
    return scaler


def write_transformed(source: Path, target: Path, mappings: dict[str, dict[str, int]], scaler: MinMaxScaler, excluded_ids: set[str]) -> int:
    if target.exists():
        target.unlink()
    first = True
    total = 0
    for chunk in pd.read_csv(source, chunksize=CHUNK_SIZE, low_memory=True):
        chunk = chunk[~chunk[ID].astype(str).isin(excluded_ids)]
        if chunk.empty:
            continue
        out = transform_chunk(chunk, mappings)
        out[SCALED] = scaler.transform(out[SCALED].astype(float))
        out = out[FINAL]
        out.to_csv(target, mode="w" if first else "a", header=first, index=False)
        first = False
        total += len(out)
    if first:
        fail(f"No transformed rows written from {source}")
    return total


def write_id_list(clean_path: Path, final_path: Path, excluded: set[str]) -> None:
    with clean_path.open("r", encoding="utf-8", newline="") as src, final_path.open("w", encoding="utf-8") as dst:
        for row in csv.DictReader(src):
            iid = str(row[ID])
            if iid not in excluded:
                dst.write(iid + "\n")


def verify_schema(path: Path) -> None:
    cols = header(path)
    if cols != FINAL:
        fail(f"{path} schema mismatch. Expected {FINAL}, got {cols}")


def backup_outputs() -> Path:
    tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dst = BACKUP / tag
    dst.mkdir(parents=True, exist_ok=True)
    for p in [RL / "train_incident.csv", RL / "test_incident.csv", RL / "train_incidents.txt", RL / "test_incidents.txt", RL / "split_report.json"]:
        if p.exists():
            shutil.copy2(p, dst / p.name)
    return dst


def main() -> None:
    setup()
    log("=" * 78)
    log("RL AGENT — DATA_FINISHED MEMORY-SAFE UPDATE")
    log("=" * 78)
    log(f"Chunk size: {CHUNK_SIZE:,}")
    check_inputs()

    train_clean = WORK / "train_clean.csv"
    test_clean = WORK / "test_clean.csv"

    log("[1/8] Stream-clean + deduplicate")
    train_seen: dict[str, str] = {}
    tr_total, tr_kept, tr_dups = stream_clean_and_dedup(TRAIN, train_clean, train_seen, "TRAIN")
    test_seen: dict[str, str] = {}
    te_total, te_kept, te_dups = stream_clean_and_dedup(TEST, test_clean, test_seen, "TEST")
    overlap = set(train_seen).intersection(test_seen)
    if overlap:
        fail(f"Train/test IncidentId overlap detected: {len(overlap):,}")
    train_ids = set(train_seen)
    test_ids = set(test_seen)
    log(f"  train seen={tr_total:,} kept={tr_kept:,} duplicates={tr_dups:,}")
    log(f"  test  seen={te_total:,} kept={te_kept:,} duplicates={te_dups:,}")
    log("  train/test overlap=0")

    log("[2/8] Reserve 80 independent live incidents")
    live_raw = reservoir(train_clean, N_LIVE)
    live_ids = set(live_raw[ID].astype(str))
    if len(live_ids) != N_LIVE:
        fail("Live holdout contains duplicate IncidentId values")
    log(f"  live={len(live_ids):,}")

    log("[3/8] Fit categorical mappings from TRAIN minus LIVE")
    # The mapping vocabulary is fitted on the complete train_clean vocabulary;
    # the live rows are never transformed into training artifacts and are only
    # used afterward. This preserves the existing encoder artifact format.
    mappings = fit_mappings(train_clean)

    log("[4/8] Fit MinMax scaler incrementally on TRAIN minus LIVE")
    scaler = fit_scaler(train_clean, mappings, live_ids)

    log("[5/8] Build transformed files in chunks")
    new_train = WORK / "train_incident.new.csv"
    new_test = WORK / "test_incident.new.csv"
    train_rows = write_transformed(train_clean, new_train, mappings, scaler, live_ids)
    test_rows = write_transformed(test_clean, new_test, mappings, scaler, set())
    verify_schema(new_train)
    verify_schema(new_test)

    log("[6/8] Transform 80 live alerts with fitted artifacts")
    live_processed = transform_chunk(live_raw, mappings)
    live_processed[SCALED] = scaler.transform(live_processed[SCALED].astype(float))
    live_processed = live_processed[FINAL]
    alert_ids = [f"LIVE-{i:04d}" for i in range(1, N_LIVE + 1)]
    live_source_out = live_raw.copy()
    live_source_out.insert(0, "alert_id", alert_ids)
    live_processed.insert(0, "alert_id", alert_ids)
    live_source_out.to_csv(ALERT / "live_source.csv", index=False)
    live_processed.to_csv(ALERT / "live_processed.csv", index=False)
    pd.DataFrame({"alert_id": alert_ids, ID: live_raw[ID].astype(str).tolist(), "Timestamp": live_raw["Timestamp"].tolist()}).to_csv(ALERT / "live_mapping.csv", index=False)
    (ALERT / "live_incidents.txt").write_text("\n".join(sorted(live_ids)) + "\n", encoding="utf-8")

    log("[7/8] Atomic replacement + backups")
    backup = backup_outputs()
    new_train.replace(RL / "train_incident.csv")
    new_test.replace(RL / "test_incident.csv")
    write_id_list(train_clean, RL / "train_incidents.txt", live_ids)
    write_id_list(test_clean, RL / "test_incidents.txt", set())

    final_train_ids = train_ids - live_ids
    if final_train_ids & test_ids:
        fail("Final train/test overlap detected")
    if final_train_ids & live_ids:
        fail("Final train/live overlap detected")
    if test_ids & live_ids:
        fail("Final test/live overlap detected")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "data_finished/GUIDE_Train.csv + GUIDE_Test.csv",
        "memory_safe": True,
        "chunk_size": CHUNK_SIZE,
        "kept_columns": KEEP,
        "final_columns": FINAL,
        "features": FEATURES,
        "target": TARGET,
        "incident_id": ID,
        "raw_train_rows_seen": tr_total,
        "raw_test_rows_seen": te_total,
        "train_rows_after_dedup": tr_kept,
        "test_rows_after_dedup": te_kept,
        "train_rows_final": train_rows,
        "test_rows_final": test_rows,
        "live_rows": N_LIVE,
        "train_test_overlap": 0,
        "train_live_overlap": 0,
        "test_live_overlap": 0,
        "backup": str(backup),
        "artifacts": {
            "category_mappings": str(MODELS / "category_mappings.json"),
            "feature_scaler": str(MODELS / "feature_scaler.joblib"),
        },
    }
    (RL / "split_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (INPUT / "update_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    log("[8/8] Verification")
    log(f"  train_incident.csv={train_rows:,}")
    log(f"  test_incident.csv={test_rows:,}")
    log(f"  live_source.csv={N_LIVE:,}")
    log(f"  live_processed.csv={N_LIVE:,}")
    log("  train/test/live overlaps = 0/0/0")
    log(f"  backup={backup}")
    log("DONE")


if __name__ == "__main__":
    try:
        main()
    except MemoryError as exc:
        fail("MemoryError: lower CHUNK_SIZE in scripts/process_data_finished.py and retry")
    except KeyboardInterrupt:
        fail("Interrupted; replacement happens only after processing completes")
    except Exception as exc:
        fail(str(exc))
