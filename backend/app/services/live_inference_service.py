from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.database.database import db
from app.rl_agent.dqn import DoubleDQN
from app.rl_agent.triage_env import ACTIONS, FEATURES
from app.services.model_versioning import get_current_model_version, ensure_model_version
from app.services.live_alert_service import alerts_collection, activity_collection, analysts_collection, get_alert

MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "real_dqn_agent.pt"
INFERENCE_META_PATH = Path(__file__).resolve().parents[3] / "models" / "live_inference.json"

# These are intentionally configurable. Confidence is a Q-value softmax heuristic,
# not a calibrated probability. Human review is also triggered by low action margin.
DEFAULT_CONFIDENCE_THRESHOLD = 0.60
DEFAULT_MARGIN_THRESHOLD = 0.15


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values, axis=1, keepdims=True)
    exp = np.exp(np.clip(shifted, -50, 50))
    return exp / np.maximum(exp.sum(axis=1, keepdims=True), 1e-12)


def _least_loaded_analyst() -> dict[str, Any] | None:
    analysts = list(analysts_collection.find({"active": True}, {"_id": 0}))
    if not analysts:
        return None

    scored = []
    for analyst in analysts:
        analyst_id = analyst.get("analyst_id")
        capacity = int(analyst.get("capacity", 0) or 0)
        load = alerts_collection.count_documents({
            "assigned_analyst": analyst_id,
            "status": {"$in": ["HUMAN_REVIEW_PENDING", "ESCALATED", "OPEN"]},
        })
        available = max(capacity - load, 0)
        scored.append((load, -available, analyst))

    available = [item for item in scored if item[0] < int(item[2].get("capacity", 0) or 0)]
    pool = available or scored
    pool.sort(key=lambda item: (item[0], item[1], str(item[2].get("analyst_id", ""))))
    return pool[0][2] if pool else None


def _feature_matrix(document: dict[str, Any]) -> np.ndarray:
    processed = document.get("processed") or {}
    missing = [name for name in FEATURES if name not in processed]
    if missing:
        raise ValueError(f"Alert {document.get('alert_id')} missing processed features: {missing}")

    values = []
    for name in FEATURES:
        value = processed.get(name)
        if value is None:
            raise ValueError(f"Alert {document.get('alert_id')} has null processed feature: {name}")
        values.append(float(value))
    return np.asarray([values], dtype=np.float32)


def _load_model() -> tuple[DoubleDQN, dict[str, Any]]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Trained model not found: {MODEL_PATH}")

    metadata = get_current_model_version()
    if metadata is None:
        metadata = ensure_model_version(model_path=MODEL_PATH, model_name="DoubleDQN")
    metadata = metadata or {"model_version": "unknown", "model_name": "DoubleDQN"}

    model = DoubleDQN(
        input_dim=len(FEATURES),
        n_actions=len(ACTIONS),
        gamma=0.95,
    )
    model.load(str(MODEL_PATH))
    return model, metadata


def run_live_inference(
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
    only_uninferred: bool = True,
) -> dict[str, Any]:
    """Run the champion model against the isolated 40-alert Mongo queue.

    The original source and processed payloads are never rewritten. Only the
    Mongo operational state and audit trail are updated.
    """
    model, model_meta = _load_model()

    query: dict[str, Any] = {}
    if only_uninferred:
        query["agent.status"] = {"$in": ["WAITING_INFERENCE", None]}

    documents = list(alerts_collection.find(query, {"_id": 0}).sort("timestamp", 1))
    now = utc_now()
    counts = {name: 0 for name in ACTIONS.values()}
    routed = 0
    errors = []
    processed = 0
    start = time.perf_counter()

    for document in documents:
        alert_id = str(document.get("alert_id"))
        try:
            states = _feature_matrix(document)
            q_values = model.q_values(states)[0]
            probabilities = _softmax(q_values.reshape(1, -1))[0]
            order = np.argsort(probabilities)[::-1]
            top_action = int(order[0])
            second_action = int(order[1]) if len(order) > 1 else top_action
            confidence = float(probabilities[top_action])
            margin = float(probabilities[top_action] - probabilities[second_action])

            selected_action = top_action
            uncertainty_reason = None
            if top_action != 2:
                if confidence < confidence_threshold:
                    selected_action = 2
                    uncertainty_reason = "LOW_CONFIDENCE"
                elif margin < margin_threshold:
                    selected_action = 2
                    uncertainty_reason = "LOW_MARGIN"

            action_name = ACTIONS[selected_action]
            timestamp = utc_now()

            requires_human = action_name == "human_review"
            status = "HUMAN_REVIEW_PENDING" if requires_human else (
                "MODEL_ALLOWED" if action_name == "allow" else "MODEL_BLOCKED"
            )

            assigned_analyst = None
            if requires_human:
                analyst = _least_loaded_analyst()
                if analyst:
                    assigned_analyst = analyst.get("analyst_id")
                    routed += 1

            q_map = {ACTIONS[index]: float(value) for index, value in enumerate(q_values)}
            probability_map = {ACTIONS[index]: float(value) for index, value in enumerate(probabilities)}

            agent_state = {
                "status": "INFERRED",
                "action": action_name,
                "model_action": ACTIONS[top_action],
                "confidence": confidence,
                "q_values": q_map,
                "action_probabilities": probability_map,
                "confidence_threshold": float(confidence_threshold),
                "margin_threshold": float(margin_threshold),
                "action_margin": margin,
                "uncertainty_reason": uncertainty_reason,
                "model_version": model_meta.get("model_version"),
                "model_name": model_meta.get("model_name"),
                "requires_human_review": requires_human,
                "inference_timestamp": timestamp,
            }

            alerts_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "status": status,
                        "agent": agent_state,
                        "assigned_analyst": assigned_analyst,
                        "updated_at": timestamp,
                    }
                },
            )

            activity_collection.insert_one({
                "alert_id": alert_id,
                "actor": "agent",
                "action": "AGENT_INFERENCE",
                "details": {
                    "action": action_name,
                    "model_action": ACTIONS[top_action],
                    "confidence": confidence,
                    "action_margin": margin,
                    "uncertainty_reason": uncertainty_reason,
                    "model_version": model_meta.get("model_version"),
                },
                "timestamp": timestamp,
            })

            if requires_human:
                activity_collection.insert_one({
                    "alert_id": alert_id,
                    "actor": "system",
                    "action": "HUMAN_REVIEW_ROUTED",
                    "details": {
                        "analyst_id": assigned_analyst,
                        "reason": uncertainty_reason or "MODEL_REQUESTED_REVIEW",
                        "confidence": confidence,
                        "model_version": model_meta.get("model_version"),
                    },
                    "timestamp": timestamp,
                })

            counts[action_name] += 1
            processed += 1
        except Exception as exc:
            errors.append({"alert_id": alert_id, "error": str(exc)})
            activity_collection.insert_one({
                "alert_id": alert_id,
                "actor": "system",
                "action": "AGENT_INFERENCE_ERROR",
                "details": {"error": str(exc), "model_version": model_meta.get("model_version")},
                "timestamp": utc_now(),
            })

    elapsed = time.perf_counter() - start
    summary = {
        "status": "completed" if not errors else "completed_with_errors",
        "model_version": model_meta.get("model_version"),
        "model_name": model_meta.get("model_name"),
        "confidence_threshold": confidence_threshold,
        "margin_threshold": margin_threshold,
        "alerts_considered": len(documents),
        "alerts_processed": processed,
        "human_review_routed": routed,
        "action_distribution": counts,
        "errors": errors,
        "duration_seconds": elapsed,
        "throughput_alerts_per_second": (processed / elapsed) if elapsed else 0.0,
        "completed_at": now.isoformat(),
    }
    INFERENCE_META_PATH.write_text(
        __import__("json").dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return summary


def get_inference_status() -> dict[str, Any]:
    try:
        if not INFERENCE_META_PATH.exists():
            return {"status": "NOT_RUN", "summary": None}
        value = __import__("json").loads(INFERENCE_META_PATH.read_text(encoding="utf-8"))
        return {"status": value.get("status", "UNKNOWN"), "summary": value}
    except Exception as exc:
        return {"status": "ERROR", "summary": {"error": str(exc)}}
