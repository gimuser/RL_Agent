"""Sequential multi-model experiment orchestration over the real processed data."""

from __future__ import annotations

import gc
import json
import logging
import resource
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

from app.config.settings import settings
from app.data_pipeline.contract import FEATURE_COLUMNS, audit_processed_split, feature_schema
from app.rl_agent.trainer import Trainer

logger = logging.getLogger(__name__)

EXPERIMENTS_DIR = settings.model_dir / "experiments"
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
EXPERIMENTS: dict[str, dict] = {}


def _model_path(name: str) -> Path:
    return settings.model_dir / f"{name}.pt"


def _metadata_path(name: str) -> Path:
    return settings.model_dir / f"{name}.metadata.json"


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError()


def _save_model_artifact(model: torch.nn.Module, name: str, training: dict, evaluation: dict) -> dict:
    model_path = _model_path(name)
    metadata_path = _metadata_path(name)
    metadata = {
        "model_name": name,
        "algorithm": "dqn",
        "architecture": training.get("architecture", "standard"),
        "dqn_type": training.get("dqn_type", "standard"),
        "state_dim": int(training.get("state_dim", len(FEATURE_COLUMNS))),
        "action_dim": int(training.get("action_dim", 3)),
        "feature_columns": list(FEATURE_COLUMNS),
        "training_dataset": str(settings.processed_data_dir / "train_processed.csv"),
        "training_rows": int(training.get("dataset_rows", 0)),
        "training_passes": int(training.get("training_passes", 0)),
        "environment_steps": int(training.get("environment_steps", 0)),
        "gradient_updates": int(training.get("gradient_updates", 0)),
        "test_dataset": str(settings.processed_data_dir / "test_processed.csv"),
        "test_rows": int(evaluation.get("test_rows", 0)),
        "evaluation": evaluation,
        "training_duration_seconds": float(training.get("elapsed_seconds", 0.0)),
        "timestamp": datetime.now(UTC).isoformat(),
        "feature_schema": feature_schema(),
    }
    tmp_model = model_path.with_suffix(model_path.suffix + ".tmp")
    tmp_meta = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
    try:
        torch.save(model.state_dict(), tmp_model)
        tmp_meta.write_text(json.dumps(metadata, indent=2, default=_json_default), encoding="utf-8")
        tmp_model.replace(model_path)
        tmp_meta.replace(metadata_path)
    finally:
        for path in (tmp_model, tmp_meta):
            if path.exists():
                path.unlink(missing_ok=True)
    return {"model_path": str(model_path), "metadata_path": str(metadata_path), "metadata": metadata}


def _release_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _current_ram_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def start_experiment_background(models: list[dict[str, Any]]) -> dict[str, Any]:
    run_id = uuid.uuid4().hex
    stop_event = threading.Event()
    state: dict[str, Any] = {
        "run_id": run_id,
        "status": "queued",
        "models": [],
        "created_at": datetime.now(UTC).isoformat(),
        "training_dataset": str(settings.processed_data_dir / "train_processed.csv"),
        "test_dataset": str(settings.processed_data_dir / "test_processed.csv"),
        "stop_event": stop_event,
    }
    EXPERIMENTS[run_id] = state

    def _worker() -> None:
        state["status"] = "running"
        train_audit = audit_processed_split("train")
        test_audit = audit_processed_split("test")
        state["training_rows"] = train_audit.rows
        state["test_rows"] = test_audit.rows
        state["total_models"] = len(models)
        results: list[dict[str, Any]] = []
        for idx, cfg in enumerate(models, start=1):
            if stop_event.is_set():
                state["status"] = "stopped"
                break
            model_entry = {
                "name": cfg.get("name"),
                "status": "training",
                "index": idx,
                "total": len(models),
                "training_progress": {},
            }
            state["current_model"] = cfg.get("name")
            state["model_index"] = idx
            state["total_models"] = len(models)
            state["models"].append(model_entry)
            try:
                training_passes = int(cfg.get("training_passes", getattr(settings, "training_passes", 1)))
                trainer = Trainer(agent_config={
                    "learning_rate": cfg.get("learning_rate", 1e-3),
                    "gamma": cfg.get("gamma", 0.99),
                    "batch_size": cfg.get("batch_size", 64),
                    "memory_size": cfg.get("memory_size", 50000),
                    "target_update": cfg.get("target_update", 1000),
                    "architecture": cfg.get("architecture", "standard"),
                    "dqn_type": cfg.get("dqn_type", "standard"),
                })
                def on_progress(prog: dict) -> None:
                    model_entry["training_progress"].update({
                        "environment_steps": prog.get("environment_steps"),
                        "dataset_rows": prog.get("dataset_rows"),
                        "gradient_updates": prog.get("gradient_updates"),
                        "last_loss": prog.get("last_loss"),
                        "last_reward": prog.get("last_reward"),
                        "replay_size": prog.get("replay_size"),
                        "replay_capacity": prog.get("replay_capacity"),
                        "epsilon": prog.get("epsilon"),
                    })
                    state["training"] = {
                        "dataset": "train_processed.csv",
                        "rows": train_audit.rows,
                        "environment_steps": prog.get("environment_steps"),
                        "episodes": idx,
                        "gradient_updates": prog.get("gradient_updates"),
                        "epsilon": prog.get("epsilon"),
                        "mean_reward": prog.get("last_reward"),
                        "mean_loss": prog.get("last_loss"),
                    }
                    state["ram_usage_mb"] = _current_ram_mb()
                    if _current_ram_mb() > settings.training_ram_limit_mb:
                        stop_event.set()
                        state["status"] = "stopped"
                        state["stop_reason"] = "Training stopped because RAM safety threshold was reached."

                training = trainer.train(
                    training_passes=training_passes,
                    max_steps=settings.training_max_steps,
                    seed=settings.training_seed,
                    stop_event=stop_event,
                    on_progress=on_progress,
                )
                if stop_event.is_set():
                    raise RuntimeError("Training stopped before completion")
                evaluation = trainer.evaluate(max_steps=settings.evaluation_max_steps)
                if trainer.agent is None:
                    raise RuntimeError("Training did not initialize an agent")
                artifact = _save_model_artifact(trainer.agent.model, str(cfg.get("name") or "dqn_model"), {**training, **cfg}, evaluation)
                model_entry.update({
                    "status": "completed",
                    "training": training,
                    "evaluation": evaluation,
                    "artifact": artifact,
                })
                state["evaluation"] = evaluation
                state["checkpoint"] = artifact["model_path"]
                results.append(model_entry)
                _release_memory()
            except Exception as exc:
                model_entry.update({"status": "failed", "error": str(exc)})
                state["error"] = str(exc)
                state["status"] = "failed"
                _release_memory()
                break
        if state.get("status") != "failed" and state.get("status") != "stopped":
            state["status"] = "completed"
        if results:
            best = None
            for entry in results:
                eval_metrics = entry.get("evaluation") or {}
                score = eval_metrics.get("average_historical_reward", -1e9)
                if best is None or score > best.get("evaluation", {}).get("average_historical_reward", -1e9):
                    best = entry
            state["best"] = best
        state["results"] = results

    thread = threading.Thread(target=_worker, daemon=True, name=f"experiment-{run_id}")
    thread.start()
    state["status"] = "started"
    return {"run_id": run_id, "status": "started"}


def stop_experiment(run_id: str) -> dict[str, Any]:
    entry = EXPERIMENTS.get(run_id)
    if not entry:
        return {"status": "not_found"}
    stop_event = entry.get("stop_event")
    if stop_event is not None:
        stop_event.set()
        entry["status"] = "stopping"
    return {"status": "stopping", "run_id": run_id}


def get_experiment_status(run_id: str) -> dict:
    return EXPERIMENTS.get(run_id, {"status": "not_found"})

