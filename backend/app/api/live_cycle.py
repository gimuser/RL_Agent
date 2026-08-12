from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.live_cycle_service import current_cycle, start_new_live_cycle
from app.services.live_inference_service import get_inference_status

router = APIRouter(prefix="/api/live-cycle", tags=["Live Evaluation Cycle"])


class NewCyclePayload(BaseModel):
    reason: str = "manual_refresh"
    metadata: dict = {}


@router.get("")
def get_cycle():
    return {"cycle": current_cycle()}


@router.post("/new")
def new_cycle(payload: NewCyclePayload):
    return start_new_live_cycle(reason=payload.reason, metadata=payload.metadata)


@router.get("/inference")
def inference_status():
    return get_inference_status()
