"""Legacy multi-model experiment compatibility layer.

The authoritative project training path is now the incident-level real-data
pipeline exposed through /api/training-control.  This module remains import-
compatible for the older experiment API, but it must not import the removed
legacy ``Trainer`` class during FastAPI startup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config.settings import settings


EXPERIMENTS_DIR = settings.model_dir / "experiments"
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENTS: dict[str, dict[str, Any]] = {}


def start_experiment_background(models: list[dict[str, Any]]) -> dict[str, Any]:
    """Compatibility response for the retired multi-model experiment API."""
    if not isinstance(models, list):
        return {
            "status": "failed",
            "error": "models must be a list",
        }

    return {
        "status": "unsupported",
        "message": (
            "The legacy multi-model experiment endpoint is retired. "
            "Use /api/training-control for the authoritative real-data "
            "incident-level RL pipeline."
        ),
        "created_at": datetime.now(UTC).isoformat(),
        "total_models": len(models),
    }


def stop_experiment(run_id: str) -> dict[str, Any]:
    return {
        "status": "unsupported",
        "run_id": run_id,
        "message": (
            "Legacy experiment runs are retired. "
            "Use /api/training-control/stop for full real-data training."
        ),
    }


def get_experiment_status(run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": "unsupported",
        "message": (
            "Legacy multi-model experiment telemetry is no longer used."
        ),
    }
