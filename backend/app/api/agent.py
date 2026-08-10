"""Agent-related API routes.

Provides a small router to query agent status and request an action for an
incoming event. Uses `app.services.agent_service` for behavior.
"""

from fastapi import APIRouter
from app.services.agent_service import get_agent_status, act_on_event

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.get("/status")
def api_agent_status():
	return get_agent_status()


@router.post("/act")
def api_act(payload: dict):
	return act_on_event(payload)


__all__ = ["router"]

