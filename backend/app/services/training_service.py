import os
from datetime import datetime
from pathlib import Path
from app.database.database import training_collection

STATE = {
    "status": "idle",
    "current_epoch": 0,
    "history": [],
}

CHECKPOINT_DIR = Path("models/checkpoints")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def _upsert_training_status(status: str, current_epoch: int):
    record = {
        "type": "status",
        "status": status,
        "current_epoch": current_epoch,
        "updated_at": datetime.utcnow(),
    }
    training_collection.insert_one(record)


def _log_training_history(epoch: int, loss: float):
    training_collection.insert_one(
        {
            "type": "history",
            "epoch": epoch,
            "loss": loss,
            "created_at": datetime.utcnow(),
        }
    )


def get_training_status():
    status_doc = training_collection.find_one(
        {"type": "status"}, sort=[("updated_at", -1)]
    )
    if not status_doc:
        return {"status": STATE["status"], "current_epoch": STATE["current_epoch"]}

    return {
        "status": status_doc["status"],
        "current_epoch": status_doc["current_epoch"],
    }


def start_training():
    current_status = get_training_status()
    if current_status["status"] == "running":
        return {"message": "Training already in progress"}

    STATE["status"] = "running"
    STATE["current_epoch"] += 1
    STATE["history"].append({"epoch": STATE["current_epoch"], "loss": 0.0})
    _upsert_training_status("running", STATE["current_epoch"])
    _log_training_history(STATE["current_epoch"], 0.0)

    return {"message": "Training started"}


def stop_training():
    STATE["status"] = "idle"
    _upsert_training_status("idle", STATE["current_epoch"])
    return {"message": "Training stopped"}


def get_checkpoints():
    if not CHECKPOINT_DIR.exists():
        return []

    return sorted(
        [item.name for item in CHECKPOINT_DIR.iterdir() if item.is_file()]
    )


def get_history():
    history_docs = training_collection.find({"type": "history"}).sort("epoch", 1)
    return [{"epoch": doc["epoch"], "loss": doc["loss"]} for doc in history_docs]
