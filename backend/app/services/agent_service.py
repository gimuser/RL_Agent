"""Model-backed agent API helpers.

The API may recommend an action from a compatible trained model, but it never
executes an external SOAR action.  Missing model artifacts are surfaced to the
caller instead of being replaced with a random decision.
"""

from typing import Any

from app.services.model_service import get_model_status, predict


AGENT_STATE: dict[str, Any] = {"last_action": None}


def get_agent_status() -> dict[str, Any]:
    model = get_model_status()
    return {
        "status": model["status"],
        "last_action": AGENT_STATE["last_action"],
        "model": model,
    }


def act_on_event(event: dict[str, Any]) -> dict[str, Any]:
    """Produce a model recommendation from a contract-valid alert payload."""
    recommendation = predict(event)
    AGENT_STATE["last_action"] = recommendation["action"]
    return recommendation


__all__ = ["get_agent_status", "act_on_event"]
