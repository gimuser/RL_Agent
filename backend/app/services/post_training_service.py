from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.live_inference_service import run_live_inference
from app.services.model_versioning import ensure_model_version

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = PROJECT_ROOT / "models"
TRAIN_METRICS = MODELS_DIR / "training_metrics.json"


def promote_and_infer() -> dict[str, Any]:
    """Create/refresh the champion model identity, then immediately score the
    isolated live-alert holdout. Failures are returned as telemetry so training
    itself remains successful and debuggable.
    """
    training = {}
    try:
        if TRAIN_METRICS.exists():
            data = json.loads(TRAIN_METRICS.read_text(encoding="utf-8"))
            training = data.get("config", {}) if isinstance(data, dict) else {}
    except Exception:
        training = {}

    model_name = str(training.get("model_name") or training.get("algorithm") or "DoubleDQN")
    model_meta = ensure_model_version(
        model_name=model_name,
        extra={
            "best_epoch": training.get("best_epoch"),
            "actual_epochs": training.get("actual_epochs"),
            "learning_rate": training.get("learning_rate"),
            "candidate_count": training.get("candidate_count"),
        },
    )

    try:
        inference = run_live_inference()
        return {"status": "completed", "model": model_meta, "inference": inference}
    except Exception as exc:
        return {
            "status": "inference_failed",
            "model": model_meta,
            "inference": {"status": "ERROR", "error": str(exc)},
        }
