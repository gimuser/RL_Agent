from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from app.database.database import (
    training_collection,
    training_metrics_collection,
    checkpoints_collection,
)

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT / "models"
TRAIN_METRICS = MODELS / "training_metrics.json"

# The authoritative real-data pipeline is controlled by
# /api/training-control. This module remains only for backwards-compatible
# legacy /api/training endpoints and must not import the removed Trainer class.
STATE = {"status": "idle", "current_epoch": 0}


def _load_json(filename: str):
    path = MODELS / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _history():
    data = _load_json("training_metrics.json")
    if isinstance(data, dict):
        value = data.get("metrics")
        if isinstance(value, list):
            return value
        for key in ("history", "episodes", "training_history"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    if isinstance(data, list):
        return data
    return []


def get_training_status():
    history = _history()
    model_exists = (MODELS / "real_dqn_agent.pt").exists()
    return {
        "status": STATE.get("status", "idle") if STATE.get("status") == "running" else ("completed" if model_exists else "idle"),
        "current_epoch": int(history[-1].get("epoch", 0)) if history and isinstance(history[-1], dict) else int(STATE.get("current_epoch", 0)),
    }


def start_training(*args, **kwargs):
    return {
        "message": "Legacy training endpoint disabled; use /api/training-control for authoritative real-data training.",
        "status": "not_started",
    }


def stop_training(*args, **kwargs):
    return {
        "message": "Use /api/training-control/stop for authoritative real-data training.",
        "status": "not_started",
    }


def get_checkpoints():
    checkpoint_dir = MODELS / "checkpoints"
    if not checkpoint_dir.exists():
        return []
    return [
        {"name": p.name, "path": str(p)}
        for p in sorted(checkpoint_dir.iterdir())
        if p.is_file()
    ]


def get_history(*args, **kwargs):
    return _history()


def get_metrics(*args, **kwargs):
    data = _load_json("training_metrics.json")
    return data if data is not None else {}


def get_training_metrics(*args, **kwargs):
    return get_metrics(*args, **kwargs)


def get_training_history(*args, **kwargs):
    return get_history(*args, **kwargs)
