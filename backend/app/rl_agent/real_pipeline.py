"""Authoritative real-data incident-level offline-RL pipeline utilities."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

FEATURES = ["Category", "MitreTechniques", "ActionGrouped", "ActionGranular", "EntityType", "EvidenceRole", "ThreatFamily", "OSFamily", "SuspicionLevel", "hour", "day", "month", "is_weekend"]
INCIDENT_ID = "IncidentId"
TARGET = "IncidentGrade"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = PROJECT_ROOT / "data" / "processed"
RL_DATA = PROJECT_ROOT / "data" / "rl_incident"
MODELS = PROJECT_ROOT / "models"
EXPERIMENTS_DIR = MODELS / "experiments"
TRAIN_PATH = PROCESSED / "train_processed.csv"
TEST_PATH = PROCESSED / "test_processed.csv"
MODEL_PATH = MODELS / "real_dqn_agent.pt"
TRAIN_METRICS_PATH = MODELS / "training_metrics.json"
TEST_METRICS_PATH = MODELS / "real_test_metrics.json"
COMPARISON_PATH = MODELS / "model_comparison.json"
RL_DATA.mkdir(parents=True, exist_ok=True); MODELS.mkdir(parents=True, exist_ok=True); EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)


def locate_source_dataset() -> Path:
    candidates = [PROCESSED / n for n in ("Microsoft_SOC_Dataset.csv", "microsoft_soc_dataset.csv", "soc_dataset.csv", "full_processed.csv", "processed.csv", "all_processed.csv")]
    for path in candidates:
        if path.exists(): return path
    valid = []
    for path in PROCESSED.glob("*.csv"):
        try:
            cols = pd.read_csv(path, nrows=0).columns
            if INCIDENT_ID in cols and TARGET in cols: valid.append(path)
        except Exception: pass
    if not valid: raise FileNotFoundError("Could not find a processed CSV containing IncidentId and IncidentGrade.")
    return max(valid, key=lambda p: p.stat().st_size)


def _assert_disjoint(*frames: pd.DataFrame) -> None:
    sets = [set(frame[INCIDENT_ID].astype(str)) for frame in frames]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            overlap = sets[i] & sets[j]
            if overlap: raise RuntimeError(f"FATAL: incident overlap between split {i} and {j}: {len(overlap)}")


def build_incident_split() -> tuple[str, str, str]:
    from .triage_env import incident_split
    source = locate_source_dataset(); df = pd.read_csv(source, low_memory=False)
    if INCIDENT_ID not in df.columns or TARGET not in df.columns: raise RuntimeError("IncidentId and IncidentGrade are required.")
    train_val, test_df = incident_split(df, train_ratio=float(os.getenv("REAL_RL_TRAIN_VAL_RATIO", "0.80")), seed=int(os.getenv("REAL_RL_SEED", "42")))
    train_df, val_df = incident_split(train_val, train_ratio=float(os.getenv("REAL_RL_TRAIN_RATIO_WITHIN_TRAIN_VAL", "0.75")), seed=int(os.getenv("REAL_RL_VALIDATION_SEED", "4242")))
    _assert_disjoint(train_df, val_df, test_df)
    paths = (RL_DATA / "train_incident.csv", RL_DATA / "validation_incident.csv", RL_DATA / "test_incident.csv")
    for frame, path in zip((train_df, val_df, test_df), paths): frame.to_csv(path, index=False)
    (RL_DATA / "train_incidents.txt").write_text("\n".join(sorted(train_df[INCIDENT_ID].astype(str).unique())), encoding="utf-8")
    (RL_DATA / "validation_incidents.txt").write_text("\n".join(sorted(val_df[INCIDENT_ID].astype(str).unique())), encoding="utf-8")
    (RL_DATA / "test_incidents.txt").write_text("\n".join(sorted(test_df[INCIDENT_ID].astype(str).unique())), encoding="utf-8")
    report = {"source_rows": len(df), "train_rows": len(train_df), "validation_rows": len(val_df), "test_rows": len(test_df), "train_incidents": int(train_df[INCIDENT_ID].astype(str).nunique()), "validation_incidents": int(val_df[INCIDENT_ID].astype(str).nunique()), "test_incidents": int(test_df[INCIDENT_ID].astype(str).nunique()), "incident_overlap": 0, "features": FEATURES, "incident_id": INCIDENT_ID, "target": TARGET}
    (RL_DATA / "split_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return tuple(str(p) for p in paths)


def _experiment_configs() -> list[dict]:
    raw = os.getenv("REAL_RL_EXPERIMENTS")
    if raw:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed: return parsed
    return [
        {"name": "double_dqn", "algorithm": "double_dqn", "learning_rate": 1e-3, "gamma": 0.95, "batch_size": 512},
        {"name": "cql", "algorithm": "cql", "learning_rate": 1e-3, "gamma": 0.95, "batch_size": 512},
        {"name": "iql", "algorithm": "iql", "learning_rate": 1e-3, "gamma": 0.95, "batch_size": 512},
        {"name": "bcq", "algorithm": "bcq", "learning_rate": 1e-3, "gamma": 0.95, "batch_size": 512},
    ]


def _write_comparison(records: list[dict], best: dict | None, status: str = "running") -> None:
    COMPARISON_PATH.write_text(json.dumps({"status": status, "selection_rule": "0.70 * validation_policy_optimality + 0.30 * validation_reward_efficiency", "test_used_for_selection": False, "candidates": records, "best": best}, indent=2, default=str), encoding="utf-8")


def _score(candidate: dict) -> float:
    validation = candidate.get("best_validation") or {}
    return float(0.70 * float(validation.get("policy_optimality", 0.0)) + 0.30 * float(validation.get("reward_efficiency", 0.0)))
