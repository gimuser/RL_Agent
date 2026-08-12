from fastapi import APIRouter
from app.services.training_service import (
    get_training_status,
    start_training as start_training_service,
    stop_training as stop_training_service,
    get_checkpoints,
    get_history,
    get_metrics,
)

router = APIRouter(prefix="/api/training", tags=["Training"])

@router.get("/status")
def training_status():
    return get_training_status()

@router.post("/start")
def start_training():
    return start_training_service()

@router.post("/stop")
def stop_training():
    return stop_training_service()

@router.get("/checkpoints")
def api_get_checkpoints():
    return {"checkpoints": get_checkpoints()}

@router.get("/history")
def api_get_history():
    return {"history": get_history()}

@router.get("/metrics")
def api_get_metrics(limit: int = 100):
    return {"metrics": get_metrics(limit)}


# ==========================================================================
# AUTHORITATIVE FULL REAL-DATA RL TRAINING
# ==========================================================================

from threading import Thread
import os

_full_training_state = {
    "status": "idle",
    "message": "",
}


def _run_authoritative_full_training():
    try:
        _full_training_state["status"] = "running"
        _full_training_state["message"] = (
            "Training real processed data with the authoritative "
            "incident-level RL pipeline."
        )

        from app.rl_agent.real_pipeline import main

        # The authoritative pipeline reads:
        # data/processed/train_processed.csv
        #
        # It creates:
        # data/rl_incident/train_incident.csv
        # data/rl_incident/test_incident.csv
        #
        # and writes the accepted model/evaluation artifacts.
        main()

        _full_training_state["status"] = "completed"
        _full_training_state["message"] = (
            "Full real-data RL training and unseen-incident "
            "evaluation completed."
        )

    except Exception as exc:
        _full_training_state["status"] = "failed"
        _full_training_state["message"] = str(exc)


@router.post("/full-real-training")
def full_real_training():
    """
    Start the authoritative complete real-data RL pipeline.

    This is intentionally separate from the legacy multi-model
    experiment endpoint.
    """

    if _full_training_state["status"] == "running":
        return {
            "status": "running",
            "message": "Full real-data training is already running.",
        }

    thread = Thread(
        target=_run_authoritative_full_training,
        daemon=True,
    )

    thread.start()

    return {
        "status": "started",
        "message": (
            "Full real-data RL training started."
        ),
    }



# ------------------------------------------------------------------
# AUTHORITATIVE PERSISTED REAL-TRAINING RESULTS
# ------------------------------------------------------------------

from pathlib import Path as _Path
import json as _json
from datetime import datetime as _datetime, timezone as _timezone


def _authoritative_paths():
    _backend = _Path(__file__).resolve().parents[2]
    _root = _backend.parent

    return {
        "training": _root / "models" / "training_metrics.json",
        "test": _root / "models" / "real_test_metrics.json",
        "split": _root / "data" / "rl_incident" / "split_report.json",
        "model": _root / "models" / "real_dqn_agent.pt",
    }


def _load_authoritative_json(path):
    try:
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as handle:
            return _json.load(handle)

    except Exception:
        return None


def _number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def _history(training):
    if not isinstance(training, dict):
        return []

    candidates = (
        training.get("history"),
        training.get("epochs"),
        training.get("metrics"),
    )

    for candidate in candidates:
        if not isinstance(candidate, list):
            continue

        output = []

        for item in candidate:
            if not isinstance(item, dict):
                continue

            epoch = item.get("epoch")
            loss = item.get("loss")

            if _number(epoch) is None or _number(loss) is None:
                continue

            output.append(
                {
                    "epoch": epoch,
                    "loss": loss,
                    "avg_reward": (
                    item.get("average_reward")
                    if item.get("average_reward") is not None
                    else item.get("avg_reward")
                ),
                    "updates": item.get("updates"),
                    "rows": item.get("rows"),
                    "incidents": item.get("incidents"),
                    "action_distribution": (
                        item.get("actions")
                        or item.get("action_distribution")
                    ),
                }
            )

        if output:
            return output

    return []


def _authoritative_results():
    paths = _authoritative_paths()

    training_raw = _load_authoritative_json(paths["training"])
    test_raw = _load_authoritative_json(paths["test"])
    split_raw = _load_authoritative_json(paths["split"])

    training = (
        training_raw
        if isinstance(training_raw, dict)
        else {}
    )

    test = (
        test_raw
        if isinstance(test_raw, dict)
        else {}
    )

    split = (
        split_raw
        if isinstance(split_raw, dict)
        else {}
    )

    # training_metrics.json is:
    # {
    #   "config": {...},
    #   "metrics": [...]
    # }
    config = (
        training.get("config")
        if isinstance(training.get("config"), dict)
        else {}
    )

    metrics = (
        training.get("metrics")
        if isinstance(training.get("metrics"), list)
        else []
    )

    history = []

    for item in metrics:
        if not isinstance(item, dict):
            continue

        epoch = item.get("epoch")
        loss = item.get("loss")

        if not isinstance(epoch, (int, float)):
            continue

        if not isinstance(loss, (int, float)):
            continue

        history.append(
            {
                "epoch": epoch,
                "loss": loss,
                "avg_reward": (
                    item.get("average_reward")
                    if item.get("average_reward") is not None
                    else item.get("avg_reward")
                ),
                "updates": item.get("updates"),
                "rows": item.get("rows"),
                "incidents": item.get("incidents"),
                "action_distribution": (
                    item.get("action_counts")
                    or item.get("action_distribution")
                    or item.get("actions")
                ),
            }
        )

    last = history[-1] if history else {}

    model_exists = paths["model"].exists()

    model_size = (
        paths["model"].stat().st_size
        if model_exists
        else None
    )

    model_modified = (
        _datetime.fromtimestamp(
            paths["model"].stat().st_mtime,
            tz=_timezone.utc,
        ).isoformat()
        if model_exists
        else None
    )

    epochs = None

    for key in (
        "epochs",
        "num_epochs",
        "total_epochs",
    ):
        value = config.get(key)
        if isinstance(value, (int, float)):
            epochs = value
            break

    if epochs is None and history:
        epochs = history[-1]["epoch"]

    batch_size = None

    for key in (
        "batch_size",
        "batch",
    ):
        value = config.get(key)
        if isinstance(value, (int, float)):
            batch_size = value
            break

    features = split.get("features")

    return {
        "source": "authoritative_files",

        "status": (
            "completed"
            if model_exists and history
            else "unavailable"
        ),

        "dataset": {
            "name": "train_processed.csv",
            "train_rows": split.get("train_rows"),
            "test_rows": split.get("test_rows"),
            "train_incidents": split.get("train_incidents"),
            "test_incidents": split.get("test_incidents"),
            "incident_overlap": split.get("incident_overlap"),
            "features": features,
            "feature_count": (
                len(features)
                if isinstance(features, list)
                else None
            ),
            "synthetic_data": test.get(
                "synthetic_data"
            ),
            "unseen_incidents": test.get(
                "unseen_incidents"
            ),
        },

        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "final_epoch": last.get("epoch"),
            "final_loss": last.get("loss"),
            "final_avg_reward": last.get(
                "avg_reward"
            ),
            "updates_per_epoch": last.get(
                "updates"
            ),
            "rows_per_epoch": last.get(
                "rows"
            ),
            "incidents_per_epoch": last.get(
                "incidents"
            ),
            "action_distribution": last.get(
                "action_distribution"
            ),
            "history": history,
        },

        "evaluation": {
            "samples": test.get("test_rows"),
            "throughput_rows_per_second": test.get(
                "throughput_rows_per_second"
            ),
            "action_distribution": test.get(
                "action_distribution"
            ),
            "per_class": test.get(
                "per_class"
            ),
            "average_reward": test.get(
                "average_reward"
            ),
            "policy_optimality": test.get(
                "policy_optimality"
            ),
            "reward_efficiency": test.get(
                "reward_efficiency"
            ),
            "reward_regret": test.get(
                "reward_regret"
            ),
        },

        "model": {
            "path": str(paths["model"]),
            "exists": model_exists,
            "size_bytes": model_size,
            "modified_at": model_modified,
        },
    }


@router.get("/full-real-training/status")
def full_real_training_status():
    current = _full_training_state

    if isinstance(current, dict) and current.get("status") == "running":
        return current

    results = _authoritative_results()

    if results["status"] == "completed":
        return {
            "status": "completed",
            "message": "Authoritative real-data incident-level training completed.",
            "results": results,
        }

    return {
        "status": "idle",
        "message": "",
        "results": None,
    }
