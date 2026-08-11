"""Background orchestration for the dataset-backed DQN trainer.

Only metrics produced by :class:`Trainer` are retained.  MongoDB persistence is
best-effort monitoring: a missing database does not manufacture history or
prevent a local training run from producing its model artifact.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from app.config.settings import settings
from app.database.database import checkpoints_collection, training_collection, training_metrics_collection
from app.rl_agent.trainer import Trainer
from app.services.model_service import save_trained_model


STATE: dict[str, Any] = {
    "status": "IDLE",
    "current_epoch": 0,
    "history": [],
    "last_error": None,
    "model_version": None,
}
TRAINING_CTRL: dict[str, Any] = {
    "thread": None,
    "stop_event": None,
    "lock": threading.Lock(),
}
_PERSISTENCE_AVAILABLE: bool | None = None


def _persist(operation) -> bool:
    """Persist one monitoring record, disabling repeated failures per process."""
    global _PERSISTENCE_AVAILABLE
    if _PERSISTENCE_AVAILABLE is False:
        return False
    try:
        operation()
    except Exception:
        _PERSISTENCE_AVAILABLE = False
        return False
    _PERSISTENCE_AVAILABLE = True
    return True


def _upsert_training_status(status: str, current_epoch: int) -> None:
    STATE["status"] = status
    STATE["current_epoch"] = current_epoch
    _persist(
        lambda: training_collection.insert_one(
            {
                "type": "status",
                "status": status,
                "current_epoch": current_epoch,
                "updated_at": datetime.now(UTC),
            }
        )
    )


def _record_episode(record: dict[str, Any]) -> None:
    """Record one completed training pass and any optimiser loss."""
    # normalize record keys for backward compatibility
    STATE["history"].append(record)
    pass_number = int(record.get("pass", record.get("episode", 0)))
    _upsert_training_status("RUNNING", pass_number)
    if record.get("loss") is None:
        return
    metric = {
        "pass": pass_number,
        "loss": float(record["loss"]),
        "average_reward": record.get("average_reward"),
        "steps": int(record.get("steps", 0)),
        "epsilon": float(record.get("epsilon", 0.0)),
        "timestamp": datetime.now(UTC),
    }
    _persist(lambda: training_collection.insert_one({"type": "history", **metric}))
    _persist(lambda: training_metrics_collection.insert_one(metric))


def _run_training_async(algorithm: str, training_passes: int | None, stop_event: threading.Event) -> None:
    try:
        trainer = Trainer(algorithm=algorithm)
        result = trainer.train(
            training_passes=training_passes,
            max_steps=settings.training_max_steps,
            seed=settings.training_seed,
            stop_event=stop_event,
            on_episode=_record_episode,
        )
        if result.get("training_passes", 0) == 0:
            _upsert_training_status("STOPPED" if result["stopped"] else "FAILED", 0)
            return

        evaluation = trainer.evaluate(max_steps=settings.evaluation_max_steps)
        metadata = save_trained_model(
            trainer.agent.model,
            training_metadata=result,
            evaluation=evaluation,
        )
        STATE["model_version"] = metadata["model_version"]
        # Expose useful training counters for monitoring and the frontend.
        for key in ("dataset_rows", "environment_steps", "gradient_updates", "elapsed_seconds"):
            if key in result:
                STATE[key] = result[key]
        _persist(
            lambda: checkpoints_collection.insert_one(
                {
                    "name": settings.model_path.name,
                    "path": str(settings.model_path),
                    "model_version": metadata["model_version"],
                    "created_at": datetime.now(UTC),
                }
            )
        )
        _upsert_training_status(
            "STOPPED" if result["stopped"] else "COMPLETED",
            int(result.get("training_passes", 0)),
        )
    except Exception as exc:
        STATE["last_error"] = str(exc)
        _upsert_training_status("FAILED", STATE["current_epoch"])
    finally:
        with TRAINING_CTRL["lock"]:
            TRAINING_CTRL["thread"] = None
            TRAINING_CTRL["stop_event"] = None


def get_training_status() -> dict[str, Any]:
    base = {
        "status": STATE["status"],
        "current_epoch": STATE["current_epoch"],
        "last_error": STATE["last_error"],
        "model_version": STATE["model_version"],
        "persistence": "AVAILABLE" if _PERSISTENCE_AVAILABLE else "UNAVAILABLE",
    }
    # Include optional counters when available
    for optional in ("dataset_rows", "environment_steps", "gradient_updates", "elapsed_seconds"):
        if optional in STATE:
            base[optional] = STATE[optional]
    return base


def start_training(algorithm: str = "dqn", episodes: int | None = None) -> dict[str, str]:
    """Start real train-split interaction in a background thread."""
    with TRAINING_CTRL["lock"]:
        thread = TRAINING_CTRL["thread"]
        if thread is not None and thread.is_alive():
            return {"message": "Training already in progress"}

        selected_episodes = settings.training_episodes if episodes is None else episodes
        # If configured training_episodes is <= 0, let the trainer compute
        # the number of episodes needed to cover the full dataset.
        if isinstance(selected_episodes, int) and selected_episodes < 1:
            selected_episodes_arg = None
        else:
            selected_episodes_arg = selected_episodes
        STATE.update({"current_epoch": 0, "history": [], "last_error": None, "model_version": None})
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_run_training_async,
            args=(algorithm, selected_episodes_arg, stop_event),
            daemon=True,
            name="dataset-backed-dqn-training",
        )
        TRAINING_CTRL["thread"] = thread
        TRAINING_CTRL["stop_event"] = stop_event
        _upsert_training_status("RUNNING", 0)
        thread.start()
    return {"message": "Training started"}


def stop_training() -> dict[str, str]:
    """Request a cooperative stop; no fabricated final metric is written."""
    with TRAINING_CTRL["lock"]:
        stop_event = TRAINING_CTRL["stop_event"]
        thread = TRAINING_CTRL["thread"]
        if stop_event is None or thread is None or not thread.is_alive():
            return {"message": "No training run is active"}
        stop_event.set()
        _upsert_training_status("STOPPING", STATE["current_epoch"])
    return {"message": "Training stop requested"}


def get_checkpoints() -> list[str]:
    """Return only compatible model-service artifacts, never legacy pickle files."""
    if settings.model_path.is_file() and settings.model_metadata_path.is_file():
        return [settings.model_path.name]
    return []


def get_history() -> list[dict[str, Any]]:
    """Expose episodes with optimiser losses; episodes before replay warmup omit loss."""
    return [
        {"epoch": item["episode"], "loss": item["loss"]}
        for item in STATE["history"]
        if item["loss"] is not None
    ]


def get_metrics(limit: int = 100) -> list[dict[str, Any]]:
    records = [item for item in STATE["history"] if item["loss"] is not None]
    return [
        {
            "epoch": item["episode"],
            "loss": item["loss"],
            "average_reward": item["average_reward"],
            "steps": item["steps"],
            "epsilon": item["epsilon"],
        }
        for item in records[-max(0, limit) :]
    ]
