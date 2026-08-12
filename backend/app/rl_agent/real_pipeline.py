"""Authoritative real-data incident-level offline RL pipeline.

Training policy:
  train incidents -> validation incidents -> early stopping/model selection
  -> candidate live-alert replay -> one-time unseen test evaluation.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from .dqn import DoubleDQN
from .evaluator import evaluate
from .trainer import train

# Keep these authoritative constants local so triage_env can import the
# compatibility helpers from this module without creating a circular import.
FEATURES = [
    "Category",
    "MitreTechniques",
    "ActionGrouped",
    "ActionGranular",
    "EntityType",
    "EvidenceRole",
    "ThreatFamily",
    "OSFamily",
    "SuspicionLevel",
    "hour",
    "day",
    "month",
    "is_weekend",
]
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

RL_DATA.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)


def locate_source_dataset() -> Path:
    candidates = [
        PROCESSED / "Microsoft_SOC_Dataset.csv",
        PROCESSED / "microsoft_soc_dataset.csv",
        PROCESSED / "soc_dataset.csv",
        PROCESSED / "full_processed.csv",
        PROCESSED / "processed.csv",
        PROCESSED / "all_processed.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    valid = []
    for path in PROCESSED.glob("*.csv"):
        try:
            cols = pd.read_csv(path, nrows=0).columns
            if INCIDENT_ID in cols and TARGET in cols:
                valid.append(path)
        except Exception:
            continue
    if not valid:
        raise FileNotFoundError("Could not find a processed CSV containing IncidentId and IncidentGrade.")
    return max(valid, key=lambda p: p.stat().st_size)


def _assert_disjoint(*frames: pd.DataFrame) -> None:
    sets = [set(frame[INCIDENT_ID].astype(str)) for frame in frames]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            overlap = sets[i] & sets[j]
            if overlap:
                raise RuntimeError(f"FATAL: incident overlap between split {i} and {j}: {len(overlap)}")


def build_incident_split() -> tuple[str, str, str]:
    from .triage_env import incident_split

    source = locate_source_dataset()
    df = pd.read_csv(source, low_memory=False)
    if INCIDENT_ID not in df.columns or TARGET not in df.columns:
        raise RuntimeError("IncidentId and IncidentGrade are required.")

    train_val, test_df = incident_split(
        df,
        train_ratio=float(os.getenv("REAL_RL_TRAIN_VAL_RATIO", "0.80")),
        seed=int(os.getenv("REAL_RL_SEED", "42")),
    )
    train_df, val_df = incident_split(
        train_val,
        train_ratio=float(os.getenv("REAL_RL_TRAIN_RATIO_WITHIN_TRAIN_VAL", "0.75")),
        seed=int(os.getenv("REAL_RL_VALIDATION_SEED", "4242")),
    )
    _assert_disjoint(train_df, val_df, test_df)

    train_path = RL_DATA / "train_incident.csv"
    val_path = RL_DATA / "validation_incident.csv"
    test_path = RL_DATA / "test_incident.csv"
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)

    (RL_DATA / "train_incidents.txt").write_text("\n".join(sorted(train_df[INCIDENT_ID].astype(str).unique())), encoding="utf-8")
    (RL_DATA / "validation_incidents.txt").write_text("\n".join(sorted(val_df[INCIDENT_ID].astype(str).unique())), encoding="utf-8")
    (RL_DATA / "test_incidents.txt").write_text("\n".join(sorted(test_df[INCIDENT_ID].astype(str).unique())), encoding="utf-8")

    report = {
        "source_rows": int(len(df)),
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "train_incidents": int(train_df[INCIDENT_ID].astype(str).nunique()),
        "validation_incidents": int(val_df[INCIDENT_ID].astype(str).nunique()),
        "test_incidents": int(test_df[INCIDENT_ID].astype(str).nunique()),
        "train_validation_overlap": 0,
        "train_test_overlap": 0,
        "validation_test_overlap": 0,
        "incident_overlap": 0,
        "features": FEATURES,
        "incident_id": INCIDENT_ID,
        "target": TARGET,
        "split": "incident-level 60/20/20 by default",
    }
    (RL_DATA / "split_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(train_path), str(val_path), str(test_path)


def _experiment_configs() -> list[dict]:
    raw = os.getenv("REAL_RL_EXPERIMENTS")
    if raw:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return parsed
    return [
        {"name": "dqn_lr_0005", "learning_rate": 5e-4, "gamma": 0.95, "batch_size": 512},
        {"name": "dqn_lr_001", "learning_rate": 1e-3, "gamma": 0.95, "batch_size": 512},
        {"name": "dqn_lr_002", "learning_rate": 2e-3, "gamma": 0.95, "batch_size": 512},
    ]


def _write_comparison(records: list[dict], best: dict | None, status: str = "running") -> None:
    COMPARISON_PATH.write_text(json.dumps({
        "status": status,
        "selection_rule": "0.70 * validation_policy_optimality + 0.30 * validation_reward_efficiency",
        "test_used_for_selection": False,
        "candidates": records,
        "best": best,
    }, indent=2), encoding="utf-8")


def _score(candidate: dict) -> float:
    validation = candidate.get("best_validation") or {}
    return float(0.70 * float(validation.get("policy_optimality", 0.0)) + 0.30 * float(validation.get("reward_efficiency", 0.0)))


def _default_int(name: str, value: int) -> int:
    return int(os.getenv(name, str(value)))


def _default_float(name: str, value: float) -> float:
    return float(os.getenv(name, str(value)))


def _run_candidate_live_cycle(candidate_path: Path, name: str, index: int) -> dict:
    from app.services.live_cycle_service import start_new_live_cycle
    from app.services.live_inference_service import run_live_inference

    reset = start_new_live_cycle(
        reason=f"candidate_{index}_evaluation",
        metadata={"candidate_name": name, "candidate_index": index},
    )
    inference = run_live_inference(
        model_path=str(candidate_path),
        model_name=name,
        only_uninferred=True,
    )
    return {
        "cycle_id": reset.get("cycle_id"),
        "alerts": reset.get("alerts"),
        "source_preserved": reset.get("source_preserved"),
        "inference": inference,
    }


def main() -> dict:
    train_csv, validation_csv, test_csv = build_incident_split()
    max_epochs = _default_int("REAL_RL_MAX_EPOCHS", 4000)
    min_epochs = _default_int("REAL_RL_MIN_EPOCHS", 50)
    patience = _default_int("REAL_RL_PATIENCE", 30)
    min_delta = _default_float("REAL_RL_MIN_DELTA", 1e-3)
    seed = _default_int("REAL_RL_SEED", 42)
    target_update = _default_int("REAL_RL_TARGET_UPDATE", 1)
    configs = _experiment_configs()
    comparison_records: list[dict] = []
    _write_comparison([], None, "running")

    for index, config in enumerate(configs, start=1):
        name = str(config.get("name") or f"candidate_{index}")
        learning_rate = float(config.get("learning_rate", 1e-3))
        gamma = float(config.get("gamma", 0.95))
        batch_size = int(config.get("batch_size", 512))
        candidate_path = EXPERIMENTS_DIR / f"{name}.pt"

        def on_progress(row: dict) -> None:
            TRAIN_METRICS_PATH.write_text(json.dumps({
                "config": {
                    "model_name": name,
                    "learning_rate": learning_rate,
                    "gamma": gamma,
                    "batch_size": batch_size,
                    "max_epochs": max_epochs,
                    "min_epochs": min_epochs,
                    "patience": patience,
                    "min_delta": min_delta,
                    "candidate_index": index,
                    "candidate_count": len(configs),
                    "features": FEATURES,
                    "synthetic_data": False,
                    "real_data": True,
                    "early_stopping": True,
                },
                "metrics": [row],
            }, indent=2), encoding="utf-8")

        model, result = train(
            train_csv=train_csv,
            validation_csv=validation_csv,
            epochs=max_epochs,
            min_epochs=min_epochs,
            patience=patience,
            min_delta=min_delta,
            batch_size=batch_size,
            learning_rate=learning_rate,
            gamma=gamma,
            target_update=target_update,
            seed=seed + index - 1,
            checkpoint_path=str(candidate_path),
            progress_callback=on_progress,
        )

        best_validation = result.get("best_validation") or {}
        candidate_record = {
            "name": name,
            "learning_rate": learning_rate,
            "gamma": gamma,
            "batch_size": batch_size,
            "actual_epochs": int(result.get("actual_epochs", 0)),
            "best_epoch": int(result.get("best_epoch", 0)),
            "best_validation": best_validation,
            "validation_score": _score({"best_validation": best_validation}),
            "model_path": str(candidate_path),
            "status": "completed",
        }

        try:
            candidate_live = _run_candidate_live_cycle(candidate_path, name, index)
            candidate_record["live_cycle_id"] = candidate_live.get("cycle_id")
            candidate_record["live_inference"] = candidate_live.get("inference")
            candidate_record["live_status"] = "completed"
        except Exception as exc:
            candidate_record["live_status"] = "failed"
            candidate_record["live_error"] = str(exc)

        comparison_records.append(candidate_record)
        comparison_records.sort(key=lambda item: item["validation_score"], reverse=True)
        _write_comparison(comparison_records, comparison_records[0], "running")
        (EXPERIMENTS_DIR / f"{name}.training.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        del model

    if not comparison_records:
        raise RuntimeError("No model candidates completed.")

    best = comparison_records[0]
    best_path = Path(best["model_path"])
    if not best_path.exists():
        raise RuntimeError(f"Best candidate checkpoint missing: {best_path}")

    shutil.copy2(best_path, MODEL_PATH)
    _write_comparison(comparison_records, best, "selected")
    final_metrics = evaluate(test_csv=test_csv, model_path=str(MODEL_PATH))

    selected_history_path = EXPERIMENTS_DIR / f"{best['name']}.training.json"
    selected_history = json.loads(selected_history_path.read_text(encoding="utf-8"))
    selected_config = selected_history.get("config", {})
    selected_config.update({
        "model_name": best["name"],
        "candidate_count": len(comparison_records),
        "selected": True,
        "selection_score": best["validation_score"],
        "selection_rule": "validation only; test untouched until final evaluation",
    })
    TRAIN_METRICS_PATH.write_text(json.dumps({
        "config": selected_config,
        "metrics": selected_history.get("metrics", []),
        "best_epoch": best["best_epoch"],
        "actual_epochs": best["actual_epochs"],
        "best_validation": best["best_validation"],
        "model_comparison": comparison_records,
    }, indent=2), encoding="utf-8")
    return final_metrics


# Compatibility helpers used by the existing application/tests.
def load_dataset(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False)
    missing = [c for c in list(FEATURES) + [TARGET] if c not in df.columns]
    if missing:
        raise RuntimeError(f"{path} missing required columns: {missing}")
    states = df[list(FEATURES)].astype(np.float32).to_numpy()
    labels = pd.to_numeric(df[TARGET], errors="raise").astype(np.int64).to_numpy()
    return df, states, labels


def reward_matrix(labels):
    from .triage_env import REWARD_TABLE
    rewards = np.zeros((len(labels), 3), dtype=np.float32)
    for i, label in enumerate(labels):
        row = REWARD_TABLE.get(int(label), REWARD_TABLE[3])
        for action in range(3):
            rewards[i, action] = float(row[action])
    return rewards


def reward_vector(labels):
    return reward_matrix(labels)


def fit_normalization(states):
    x = np.asarray(states, dtype=np.float32)
    if x.ndim != 2:
        raise ValueError(f"Expected 2D state matrix, got shape={x.shape}")
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    return {"mean": mean.astype(float).tolist(), "std": std.astype(float).tolist()}


def apply_normalization(states, normalization=None):
    x = np.asarray(states, dtype=np.float32)
    if normalization is None:
        return x
    mean = np.asarray(normalization["mean"], dtype=np.float32)
    std = np.asarray(normalization["std"], dtype=np.float32)
    std = np.where(std < 1e-8, 1.0, std)
    return ((x - mean) / std).astype(np.float32)


if __name__ == "__main__":
    main()
