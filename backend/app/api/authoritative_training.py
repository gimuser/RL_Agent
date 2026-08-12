from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.authoritative_training_control import start, status, stop

router = APIRouter(prefix="/api/training-control", tags=["Authoritative Training Control"])


class TrainingStartRequest(BaseModel):
    model_names: list[str] = Field(default_factory=list)


@router.post("")
def start_full_training(request: TrainingStartRequest | None = None):
    return start(request.model_names if request else None)


@router.get("")
def get_full_training_status():
    return status()


@router.post("/stop")
def stop_full_training():
    return stop()
