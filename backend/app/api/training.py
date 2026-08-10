from fastapi import APIRouter
from app.services.training_service import (
    get_training_status,
    start_training as start_training_service,
    stop_training as stop_training_service,
    get_checkpoints,
    get_history,
    get_metrics,
)

router = APIRouter(prefix="/api/training", tags=["Training"])

@router.get("/status")
def training_status():
    return get_training_status()

@router.post("/start")
def start_training():
    return start_training_service()

@router.post("/stop")
def stop_training():
    return stop_training_service()

@router.get("/checkpoints")
def api_get_checkpoints():
    return {"checkpoints": get_checkpoints()}

@router.get("/history")
def api_get_history():
    return {"history": get_history()}

@router.get("/metrics")
def api_get_metrics(limit: int = 100):
    return {"metrics": get_metrics(limit)}
