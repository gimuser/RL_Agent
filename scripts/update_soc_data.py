#!/usr/bin/env python3
"""Runtime-only Microsoft GUIDE dataset updater for the RL agent.

This script deliberately does NOT commit or require the downloaded Kaggle
CSV files to exist in GitHub. It downloads GUIDE_Train.csv / GUIDE_Test.csv
at runtime, keeps only the incident-level columns used by the existing RL
pipeline, removes duplicate incidents safely, creates an 80-incident live
holdout, runs the existing cleaner/validator/encoder/feature-engineering/
normalizer components, and replaces data/rl_incident train/test files.

The live holdout is selected BEFORE fitting the encoder/scaler, so live data
are not used to fit preprocessing artifacts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_SOC_UPDATE = PROJECT_ROOT / "data_soc_update"
RAW_DIR = DATA_SOC_UPDATE / "raw"
WORK_DIR = DATA_SOC_UPDATE / "work"
BACKUP_DIR = DATA_SOC_UPDATE / "backup"
MANIFEST_PATH = DATA_SOC_UPDATE / "update_manifest.json"

RL_INCIDENT_DIR = PROJECT_ROOT / "data" / "rl_incident"
DATA_ALERT_DIR = PROJECT_ROOT / "data_alert"

TRAIN_RAW_NAME = "GUIDE_Train.csv"
TEST_RAW_NAME = "GUIDE_Test.csv"

TRAIN_WORK = WORK_DIR / "data_train.csv"
TEST_WORK = WORK_DIR / "data_test.csv"
TRAIN_PROCESSED_WORK = WORK_DIR / "train_processed.csv"
TEST_PROCESSED_WORK = WORK_DIR / "test_processed.csv"

FINAL_TRAIN = RL_INCIDENT_DIR / "train_incident.csv"
FINAL_TEST = RL_INCIDENT_DIR / "test_incident.csv"
TRAIN_IDS = RL_INCIDENT_DIR / "train_incidents.txt"
TEST_IDS = RL_INCIDENT_DIR / "test_incidents.txt"
SPLIT_REPORT = RL_INCIDENT_DIR / "split_report.json"

LIVE_SOURCE = DATA_ALERT_DIR / "live_source.csv"
LIVE_PROCESSED = DATA_ALERT_DIR / "live_processed.csv"
LIVE_MAPPING = DATA_ALERT_DIR / "live_mapping.csv"

KAGGLE_DATASETS = [
    "microsoft/microsoft-security-incident-prediction",
    "avijitjana101/microsoft-soc-dataset",
]

KEEP_COLUMNS = [
    "IncidentId",
    "Timestamp",
    "Category",
    "MitreTechniques",
    "IncidentGrade",
    "ActionGrouped",
    "ActionGranular",
    "EntityType",
    "EvidenceRole",
    "ThreatFamily",
    "OSFamily",
    "SuspicionLevel",
    "LastVerdict",
]

FINAL_COLUMNS = KEEP_COLUMNS + ["hour", "day", "month", "is_weekend"]
N_LIVE = 80
RANDOM_SEED = 20260816


def log(message: str = "") -> None:
    print(message, flush=True)


def fail(message: str, exc: Exception | None = None) -> None:
    if exc is not None:
        log(f"[ERROR] {message}: {exc}")
    else:
        log(f"[ERROR] {message}")
    raise SystemExit(1)


def ensure_package(import_name: str, pip_name: str) -> None:
    try:
        __import__(import_name)
        return
    except ImportError:
        log(f"[INSTALL] Installing missing package: {pip_name}")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name]
            )
        except subprocess.CalledProcessError as exc:
            fail(f"Could not install {pip_name}", exc)


def find_kaggle_file(root: Path, filename: str) -> Path | None:
    matches = list(root.rglob(filename))
    if not matches:
        return None
    matches.sort(key=lambda p: (len(p.parts), str(p)))
    return matches[0]


def download_dataset() -> tuple[Path, Path, str]:
    ensure_package("kagglehub", "kagglehub")
    import kagglehub

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    last_error: Exception | None = None
    for dataset_slug in KAGGLE_DATASETS:
        log(f"[DOWNLOAD] Trying Kaggle dataset: {dataset_slug}")
        try:
            try:
                downloaded = Path(
                    kagglehub.dataset_download(
                        dataset_slug,
                        path=str(RAW_DIR),
                    )
                )
            except TypeError:
                downloaded = Path(kagglehub.dataset_download(dataset_slug))

            train_path = find_kaggle_file(downloaded, TRAIN_RAW_NAME)
            test_path = find_kaggle_file(downloaded, TEST_RAW_NAME)

            if train_path and test_path:
                log(f"[DOWNLOAD] Train: {train_path}")
                log(f"[DOWNLOAD] Test : {test_path}")
                return train_path, test_path, dataset_slug

            last_error = FileNotFoundError(
                f"{TRAIN_RAW_NAME}/{TEST_RAW_NAME} not found under {downloaded}"
            )
            log(f"[WARN] {last_error}")
        except Exception as exc:  # pragma: no cover - runtime dependent
            last_error = exc
            log(f"[WARN] Download failed for {dataset_slug}: {exc}")

    fail(
        "Could not download a GUIDE train/test pair from Kaggle. "
        "Configure Kaggle authentication and rerun.",
        last_error,
    )
    raise AssertionError("unreachable")


def validate_columns(df: pd.DataFrame, name: str) -> None:
    missing = [c for c in KEEP_COLUMNS if c not in df.columns]
    if missing:
        fail(f"{name} is missing required columns: {missing}")


def deduplicate_incidents(df: pd.DataFrame, name: str) -> tuple[pd.DataFrame, int]:
    before = len(df)
    duplicated_ids = df["IncidentId"].duplicated(keep=False)
    if not duplicated_ids.any():
        return df, 0

    # Do not silently collapse contradictory labels for the same incident.
    conflicts = (
        df.loc[duplicated_ids]
        .groupby("IncidentId")["IncidentGrade"]
        .nunique(dropna=False)
    )
    bad = conflicts[conflicts > 1]
    if not bad.empty:
        fail(
            f"{name} contains IncidentId values with conflicting IncidentGrade labels: "
            f"{bad.index[:10].tolist()}"
        )

    df = df.drop_duplicates(subset=["IncidentId"], keep="first").copy()
    removed = before - len(df)
    log(f"[DEDUP] {name}: removed {removed:,} duplicate incident rows")
    return df, removed


def write_ids(path: Path, df: pd.DataFrame) -> None:
    path.write_text(
        "\n".join(df["IncidentId"].astype(str).tolist()) + "\n",
        encoding="utf-8",
    )


def apply_existing_pipeline(train: pd.DataFrame, test: pd.DataFrame):
    pipeline_dir = PROJECT_ROOT / "backend" / "app" / "data_pipeline"
    sys.path.insert(0, str(pipeline_dir))

    from cleaner import clean_data
    from encoder import encode_data
    from feature_engineering import create_features
    from normalizer import normalize_data
    from validator import validate_data

    log("[PIPELINE] Cleaning with existing clean_data()")
    train = clean_data(train)
    test = clean_data(test)

    log("[PIPELINE] Validating with existing validate_data()")
    if not validate_data(train, "TRAIN"):
        fail("Existing train validation failed")
    if not validate_data(test, "TEST"):
        fail("Existing test validation failed")

    log("[PIPELINE] Encoding with existing train-fitted encode_data()")
    train, test = encode_data(train, test)

    log("[PIPELINE] Engineering hour/day/month/weekend with existing create_features()")
    train, test = create_features(train, test)

    log("[PIPELINE] Normalizing with existing train-fitted normalize_data()")
    train, test = normalize_data(train, test)

    return train, test


def process_live_with_existing_artifacts(live_raw: pd.DataFrame) -> pd.DataFrame:
    pipeline_dir = PROJECT_ROOT / "backend" / "app" / "data_pipeline"
    sys.path.insert(0, str(pipeline_dir))

    from feature_engineering import create_features
    from encoder import load_mappings
    from normalizer import load_scaler

    live = live_raw.copy()
    mappings = load_mappings()

    for column, mapping in mappings.items():
        if column not in live.columns:
            continue
        values = live[column].astype(str)
        live[column] = values.map(mapping).fillna(-1).astype(int)

    # Reuse the existing feature engineering implementation.
    live, _ = create_features(live, live.copy())

    scaler_artifact = load_scaler()
    scaler = scaler_artifact["scaler"]
    columns = scaler_artifact["columns"]
    live[columns] = scaler.transform(live[columns])

    return live


def main() -> None:
    started = datetime.now(timezone.utc)
    log("=" * 78)
    log("RL AGENT — MICROSOFT GUIDE DATA UPDATE")
    log("=" * 78)
    log(f"Project root : {PROJECT_ROOT}")
    log(f"Target train : {FINAL_TRAIN}")
    log(f"Target test  : {FINAL_TEST}")
    log(f"Live alerts  : {N_LIVE}")
    log()

    for directory in [RAW_DIR, WORK_DIR, BACKUP_DIR, RL_INCIDENT_DIR, DATA_ALERT_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    train_path, test_path, dataset_slug = download_dataset()

    log("\n[LOAD] Reading downloaded GUIDE files")
    train_raw = pd.read_csv(train_path, low_memory=False)
    test_raw = pd.read_csv(test_path, low_memory=False)
    log(f"[LOAD] Raw train rows: {len(train_raw):,}, columns: {len(train_raw.columns)}")
    log(f"[LOAD] Raw test  rows: {len(test_raw):,}, columns: {len(test_raw.columns)}")

    validate_columns(train_raw, "GUIDE_Train.csv")
    validate_columns(test_raw, "GUIDE_Test.csv")

    log("\n[SELECT] Keeping only the incident-level columns used by the RL state/target")
    train = train_raw[KEEP_COLUMNS].copy()
    test = test_raw[KEEP_COLUMNS].copy()

    # Clean exact duplicate rows, then duplicate incident IDs.
    train = train.drop_duplicates().copy()
    test = test.drop_duplicates().copy()
    train, train_dupes = deduplicate_incidents(train, "TRAIN")
    test, test_dupes = deduplicate_incidents(test, "TEST")

    log(f"[SELECT] Train after column selection/dedup: {len(train):,}")
    log(f"[SELECT] Test  after column selection/dedup: {len(test):,}")

    cross_overlap = set(train["IncidentId"]) & set(test["IncidentId"])
    if cross_overlap:
        fail(
            f"Train/test IncidentId overlap detected: {len(cross_overlap):,}. "
            "Refusing to continue because it would leak incidents across splits."
        )
    log("[CHECK] Train/test IncidentId overlap: 0")

    # Create the independent live holdout BEFORE fitting encoders/scaler.
    if len(train) <= N_LIVE:
        fail(f"Train has only {len(train)} incidents; cannot hold out {N_LIVE} live alerts.")

    live_ids = (
        train[["IncidentId", "Timestamp"]]
        .sample(n=N_LIVE, random_state=RANDOM_SEED)
        .copy()
    )
    live_ids = live_ids.sort_values(["Timestamp", "IncidentId"]).reset_index(drop=True)
    live_incident_ids = set(live_ids["IncidentId"].tolist())

    live_raw = train[train["IncidentId"].isin(live_incident_ids)].copy()
    train_core = train[~train["IncidentId"].isin(live_incident_ids)].copy()

    log(f"[LIVE] Held out {len(live_raw):,} unique incidents for live alerts")
    log(f"[LIVE] Remaining RL train incidents: {len(train_core):,}")

    if len(live_raw) != N_LIVE or len(live_raw["IncidentId"].unique()) != N_LIVE:
        fail("Live holdout is not exactly 80 unique incidents.")

    # Keep runtime-only raw working copies outside Git.
    train_core.to_csv(TRAIN_WORK, index=False)
    test.to_csv(TEST_WORK, index=False)

    log("\n[PIPELINE] Running the existing data_pipeline modules")
    train_processed, test_processed = apply_existing_pipeline(train_core, test)

    # Strict output contract: exactly the same 17-column schema as your current RL incident files.
    missing_final = [c for c in FINAL_COLUMNS if c not in train_processed.columns or c not in test_processed.columns]
    if missing_final:
        fail(f"Processed datasets are missing final columns: {missing_final}")

    train_processed = train_processed[FINAL_COLUMNS].copy()
    test_processed = test_processed[FINAL_COLUMNS].copy()

    # Process the live holdout with the artifacts fit only on train_core.
    live_processed = process_live_with_existing_artifacts(live_raw)
    live_processed = live_processed[FINAL_COLUMNS].copy()

    # Save work artifacts and final train/test files.
    train_processed.to_csv(TRAIN_PROCESSED_WORK, index=False)
    test_processed.to_csv(TEST_PROCESSED_WORK, index=False)

    timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_backup = BACKUP_DIR / timestamp_tag
    run_backup.mkdir(parents=True, exist_ok=True)

    log("\n[BACKUP] Backing up current rl_incident files")
    for path in [FINAL_TRAIN, FINAL_TEST, TRAIN_IDS, TEST_IDS, SPLIT_REPORT]:
        if path.exists():
            shutil.copy2(path, run_backup / path.name)
            log(f"[BACKUP] {path.name}")

    before_train = pd.read_csv(FINAL_TRAIN, low_memory=False) if FINAL_TRAIN.exists() else None
    before_test = pd.read_csv(FINAL_TEST, low_memory=False) if FINAL_TEST.exists() else None

    train_processed.to_csv(FINAL_TRAIN, index=False)
    test_processed.to_csv(FINAL_TEST, index=False)
    write_ids(TRAIN_IDS, train_processed)
    write_ids(TEST_IDS, test_processed)

    # Live outputs match the existing data_alert convention: source + normalized processed + mapping.
    live_source = live_raw.copy()
    live_source.insert(0, "alert_id", [f"LIVE-{i:04d}" for i in range(1, N_LIVE + 1)])
    live_processed.insert(0, "alert_id", live_source["alert_id"].tolist())

    live_source.to_csv(LIVE_SOURCE, index=False)
    live_processed.to_csv(LIVE_PROCESSED, index=False)
    pd.DataFrame({
        "alert_id": live_source["alert_id"],
        "IncidentId": live_source["IncidentId"],
        "Timestamp": live_source["Timestamp"],
    }).to_csv(LIVE_MAPPING, index=False)

    train_ids = set(train_processed["IncidentId"].tolist())
    test_ids = set(test_processed["IncidentId"].tolist())
    live_ids_final = set(live_processed["IncidentId"].tolist())

    if train_ids & test_ids:
        fail("Final train/test overlap detected after processing.")
    if train_ids & live_ids_final:
        fail("Final train/live overlap detected. Live alerts are not independent.")
    if test_ids & live_ids_final:
        fail("Final test/live overlap detected. Live alerts are not independent.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_slug": dataset_slug,
        "raw_files": {
            "train": str(train_path),
            "test": str(test_path),
        },
        "kept_columns": KEEP_COLUMNS,
        "final_columns": FINAL_COLUMNS,
        "train_rows": int(len(train_processed)),
        "test_rows": int(len(test_processed)),
        "train_incidents": int(train_processed["IncidentId"].nunique()),
        "test_incidents": int(test_processed["IncidentId"].nunique()),
        "live_rows": int(len(live_processed)),
        "live_incidents": int(live_processed["IncidentId"].nunique()),
        "train_test_overlap": int(len(train_ids & test_ids)),
        "train_live_overlap": int(len(train_ids & live_ids_final)),
        "test_live_overlap": int(len(test_ids & live_ids_final)),
        "train_duplicate_rows_removed": int(train_dupes),
        "test_duplicate_rows_removed": int(test_dupes),
        "before": {
            "train_rows": int(len(before_train)) if before_train is not None else None,
            "test_rows": int(len(before_test)) if before_test is not None else None,
        },
        "after": {
            "train_rows": int(len(train_processed)),
            "test_rows": int(len(test_processed)),
        },
        "runtime_only": True,
        "git_safe": True,
    }

    SPLIT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    log("\n[FINAL] DATASET UPDATE COMPLETE")
    log(f"[FINAL] Train: {len(train_processed):,} rows / {train_processed[\"IncidentId\"].nunique():,} incidents")
    log(f"[FINAL] Test : {len(test_processed):,} rows / {test_processed[\"IncidentId\"].nunique():,} incidents")
    log(f"[FINAL] Live : {len(live_processed):,} rows / {live_processed[\"IncidentId\"].nunique():,} incidents")
    log(f"[FINAL] Schema: {len(FINAL_COLUMNS)} columns")
    log("[FINAL] Train/Test overlap: 0")
    log("[FINAL] Train/Live overlap: 0")
    log("[FINAL] Test/Live overlap: 0")
    log(f"[FINAL] Backup: {run_backup}")
    log(f"[FINAL] Manifest: {MANIFEST_PATH}")
    log(f"[FINAL] Elapsed: {datetime.now(timezone.utc) - started}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n[ERROR] Interrupted by user. No further files were modified.")
        raise SystemExit(130)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - runtime error reporting
        fail("Unexpected failure", exc)
