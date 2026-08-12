import json
import os
import threading
from datetime import datetime
from pathlib import Path

from app.database.database import (
    training_collection,
    training_metrics_collection,
    checkpoints_collection,
)

from app.rl_agent.trainer import Trainer


ROOT = Path(__file__).resolve().parents[3]

TRAIN_METRICS = (
    ROOT / "models" / "training_metrics.json"
)

TEST_METRICS = (
    ROOT / "models" / "real_test_metrics.json"
)

STATE = {
    "status": "idle",
    "current_epoch": 0,
}

TRAINING_CTRL = {
    "thread": None,
    "stop_event": None,
    "lock": threading.Lock(),
}


def _status(status, epoch):

    STATE["status"] = status
    STATE["current_epoch"] = epoch

    try:
        training_collection.insert_one(
            {
                "type": "status",
                "status": status,
                "current_epoch": epoch,
                "updated_at": datetime.utcnow(),
            }
        )
    except Exception:
        pass


def get_training_status():

    try:
        doc = training_collection.find_one(
            {"type": "status"},
            sort=[("updated_at", -1)],
        )

        if doc:
            return {
                "status": doc.get(
                    "status",
                    "unknown",
                ),
                "current_epoch": int(
                    doc.get(
                        "current_epoch",
                        0,
                    )
                ),
            }

    except Exception:
        pass

    return {
        "status": STATE["status"],
        "current_epoch": STATE["current_epoch"],
    }


def _run_training_async(
    algorithm="double_dqn",
    epochs=1,
    stop_event=None,
):

    try:

        _status("running", 0)

        trainer = Trainer(
            algorithm=algorithm,
            state_dim=11,
            action_dim=3,
        )

        # Real training happens here.
        trainer.train(
            episodes=epochs
        )

        if stop_event is not None and stop_event.is_set():
            _status(
                "stopped",
                STATE["current_epoch"],
            )
            return

        # Read REAL metrics produced by the trainer.
        if TRAIN_METRICS.exists():

            data = json.loads(
                TRAIN_METRICS.read_text(
                    encoding="utf-8"
                )
            )

            history = data.get(
                "history",
                [],
            )

            for item in history:

                epoch = int(
                    item["epoch"]
                )

                STATE["current_epoch"] = epoch

                try:
                    training_metrics_collection.insert_one(
                        {
                            "type": "real_training_metric",
                            **item,
                            "timestamp": datetime.utcnow(),
                        }
                    )
                except Exception:
                    pass

        trainer.evaluate()

        _status(
            "completed",
            STATE["current_epoch"],
        )

    except Exception as exc:

        try:
            training_collection.insert_one(
                {
                    "type": "training_error",
                    "error": str(exc),
                    "timestamp": datetime.utcnow(),
                }
            )
        except Exception:
            pass

        _status(
            "failed",
            STATE["current_epoch"],
        )

        raise


def start_training(
    algorithm="double_dqn",
    episodes=1,
):

    status = get_training_status()

    if status["status"] == "running":
        return {
            "message": "Training already running"
        }

    epochs = int(
        os.getenv(
            "REAL_RL_EPOCHS",
            str(episodes),
        )
    )

    stop_event = threading.Event()

    with TRAINING_CTRL["lock"]:

        TRAINING_CTRL["stop_event"] = stop_event

        thread = threading.Thread(
            target=_run_training_async,
            args=(
                algorithm,
                epochs,
                stop_event,
            ),
            daemon=True,
        )

        TRAINING_CTRL["thread"] = thread

        thread.start()

    return {
        "message": "Training started",
        "dataset": "train_processed.csv",
        "epochs": epochs,
        "real_data": True,
    }


def stop_training():

    with TRAINING_CTRL["lock"]:

        event = TRAINING_CTRL.get(
            "stop_event"
        )

        if event:
            event.set()

    _status(
        "stopping",
        STATE["current_epoch"],
    )

    return {
        "message": "Training stop requested"
    }


def get_checkpoints():

    checkpoint_dir = (
        ROOT / "models" / "checkpoints"
    )

    if not checkpoint_dir.exists():
        return []

    return [
        {
            "name": p.name,
            "path": str(p),
        }
        for p in sorted(
            checkpoint_dir.iterdir()
        )
        if p.is_file()
    ]

# ---------------------------------------------------------------------------
# Backwards-compatible API helper
# ---------------------------------------------------------------------------
def get_history(*args, **kwargs):
    """
    Return training history for the API.

    The current RL implementation stores training metrics in
    models/training_metrics.json when available.
    """
    from pathlib import Path
    import json

    root = Path(__file__).resolve().parents[3]
    metrics_file = root / "models" / "training_metrics.json"

    if not metrics_file.exists():
        return []

    try:
        with metrics_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Support common metric container formats.
            for key in ("history", "episodes", "metrics", "training_history"):
                value = data.get(key)
                if isinstance(value, list):
                    return value

            return data

        return []

    except (OSError, json.JSONDecodeError):
        return []

# ============================================================================
# API COMPATIBILITY LAYER
# ============================================================================
# These helpers keep the FastAPI training endpoints compatible with the
# current real-data RL training implementation.

from pathlib import Path as _Path
import json as _json


def _project_root():
    return _Path(__file__).resolve().parents[3]


def _load_json_file(filename):
    path = _project_root() / "models" / filename

    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            return _json.load(f)
    except (OSError, _json.JSONDecodeError):
        return None


def get_metrics(*args, **kwargs):
    """
    Return persisted training metrics.

    Compatible with the FastAPI training API.
    """
    data = _load_json_file("training_metrics.json")

    if data is None:
        return {}

    if isinstance(data, dict):
        return data

    return {"history": data}


def get_history(*args, **kwargs):
    """
    Return episode/training history.
    """
    data = _load_json_file("training_metrics.json")

    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in (
            "history",
            "episodes",
            "metrics",
            "training_history",
        ):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def get_training_status(*args, **kwargs):
    """
    Return a lightweight training status object.
    """
    root = _project_root()

    model = root / "models" / "real_dqn_agent.pt"
    metrics = root / "models" / "training_metrics.json"

    return {
        "trained": model.exists(),
        "model_exists": model.exists(),
        "metrics_exists": metrics.exists(),
        "status": "completed" if model.exists() else "not_trained",
    }


def get_training_metrics(*args, **kwargs):
    """
    Alias used by older API code.
    """
    return get_metrics(*args, **kwargs)


def get_training_history(*args, **kwargs):
    """
    Alias used by older API code.
    """
    return get_history(*args, **kwargs)

