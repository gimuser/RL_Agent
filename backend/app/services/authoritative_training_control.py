from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = PROJECT_ROOT / "models"
TRAIN_METRICS = MODELS_DIR / "training_metrics.json"
TEST_METRICS = MODELS_DIR / "real_test_metrics.json"
SPLIT_REPORT = PROJECT_ROOT / "data" / "rl_incident" / "split_report.json"
MODEL_PATH = MODELS_DIR / "real_dqn_agent.pt"
LOG_PATH = MODELS_DIR / "full_real_training.log"

_lock = Lock()
_process: subprocess.Popen[str] | None = None
_started_at: str | None = None
_last_return_code: int | None = None
_last_message: str = ""


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _history() -> list[dict[str, Any]]:
    data = _load_json(TRAIN_METRICS) or {}
    metrics = data.get("metrics")
    if not isinstance(metrics, list):
        return []

    output: list[dict[str, Any]] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        epoch = item.get("epoch")
        loss = item.get("loss")
        if not isinstance(epoch, (int, float)) or not isinstance(loss, (int, float)):
            continue
        output.append({
            "epoch": epoch,
            "loss": loss,
            "avg_reward": item.get("average_reward", item.get("avg_reward")),
            "updates": item.get("updates"),
            "rows": item.get("rows"),
            "incidents": item.get("incidents"),
            "action_distribution": item.get("action_counts") or item.get("action_distribution") or item.get("actions"),
            "time_seconds": item.get("time_seconds"),
        })
    return output


def _results() -> dict[str, Any]:
    training = _load_json(TRAIN_METRICS) or {}
    testing = _load_json(TEST_METRICS) or {}
    split = _load_json(SPLIT_REPORT) or {}
    config = training.get("config") if isinstance(training.get("config"), dict) else {}
    history = _history()
    last = history[-1] if history else {}
    features = split.get("features")

    model_exists = MODEL_PATH.exists()
    model_size = MODEL_PATH.stat().st_size if model_exists else None
    model_modified = (
        datetime.fromtimestamp(MODEL_PATH.stat().st_mtime, tz=timezone.utc).isoformat()
        if model_exists else None
    )

    return {
        "source": "authoritative_files",
        "dataset": {
            "name": "train_processed.csv",
            "train_rows": split.get("train_rows"),
            "test_rows": split.get("test_rows"),
            "train_incidents": split.get("train_incidents"),
            "test_incidents": split.get("test_incidents"),
            "incident_overlap": split.get("incident_overlap"),
            "features": features,
            "feature_count": len(features) if isinstance(features, list) else None,
            "synthetic_data": config.get("synthetic_data") if config else testing.get("synthetic_data"),
            "unseen_incidents": testing.get("unseen_incidents"),
        },
        "training": {
            "epochs": config.get("epochs"),
            "batch_size": config.get("batch_size"),
            "final_epoch": last.get("epoch"),
            "final_loss": last.get("loss"),
            "final_avg_reward": last.get("avg_reward"),
            "updates_per_epoch": last.get("updates"),
            "rows_per_epoch": last.get("rows"),
            "incidents_per_epoch": last.get("incidents"),
            "action_distribution": last.get("action_distribution"),
            "history": history,
        },
        "evaluation": {
            "samples": testing.get("test_rows"),
            "throughput_rows_per_second": testing.get("throughput_rows_per_second"),
            "action_distribution": testing.get("action_distribution"),
            "per_class": testing.get("per_class"),
            "average_reward": testing.get("average_reward"),
            "policy_optimality": testing.get("policy_optimality"),
            "reward_efficiency": testing.get("reward_efficiency"),
            "reward_regret": testing.get("reward_regret"),
        },
        "model": {
            "path": str(MODEL_PATH),
            "exists": model_exists,
            "size_bytes": model_size,
            "modified_at": model_modified,
        },
    }


def _sync_process_state() -> None:
    global _process, _last_return_code, _last_message
    if _process is None:
        return
    code = _process.poll()
    if code is None:
        return
    _last_return_code = code
    if code == 0:
        _last_message = "Authoritative real-data training process completed."
    else:
        _last_message = f"Training process exited with return code {code}."
    _process = None


def start() -> dict[str, Any]:
    global _process, _started_at, _last_return_code, _last_message
    with _lock:
        _sync_process_state()
        if _process is not None and _process.poll() is None:
            return {"status": "running", "message": "Full real-data training is already running."}

        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Clear stale metrics before a new run. The trainer will repopulate this
        # file after the first completed epoch.
        if TRAIN_METRICS.exists():
            TRAIN_METRICS.write_text("{\"config\": {}, \"metrics\": []}\n", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")

        log_handle = LOG_PATH.open("w", encoding="utf-8")
        _process = subprocess.Popen(
            [sys.executable, "-m", "app.rl_agent.real_pipeline"],
            cwd=str(PROJECT_ROOT / "backend"),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _started_at = datetime.now(timezone.utc).isoformat()
        _last_return_code = None
        _last_message = "Full real-data RL training started."

        return {"status": "started", "message": _last_message}


def stop() -> dict[str, Any]:
    global _process, _last_message, _last_return_code
    with _lock:
        _sync_process_state()
        if _process is None or _process.poll() is not None:
            return {"status": "idle", "message": "No managed full training process is running."}

        pid = _process.pid
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            _process.terminate()

        try:
            _process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                _process.kill()
            _process.wait(timeout=5)

        _last_return_code = _process.returncode
        _process = None
        _last_message = "Full real-data training was stopped by the user."
        return {"status": "stopped", "message": _last_message}


def status() -> dict[str, Any]:
    with _lock:
        _sync_process_state()
        running = _process is not None and _process.poll() is None
        results = _results()

        if running:
            message = "Training real processed data with the authoritative incident-level RL pipeline."
            state = "running"
        elif _last_return_code == 0:
            message = _last_message or "Training completed."
            state = "completed"
        elif _last_return_code is not None:
            message = _last_message
            state = "stopped" if "stopped" in _last_message.lower() else "failed"
        elif results["training"]["history"]:
            message = "Persisted authoritative training results available."
            state = "completed"
        else:
            message = "No authoritative full-training run is currently active."
            state = "idle"

        return {
            "status": state,
            "message": message,
            "started_at": _started_at,
            "pid": _process.pid if running and _process is not None else None,
            "results": results,
        }
