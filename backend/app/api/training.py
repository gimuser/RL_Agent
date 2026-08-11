from fastapi import APIRouter
from app.services.training_service import (
    get_training_status,
    start_training as start_training_service,
    stop_training as stop_training_service,
    get_checkpoints,
    get_history,
    get_metrics,
)
from app.services.experiment_service import get_experiment_status, start_experiment_background, stop_experiment

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


@router.post("/experiment")
def api_start_experiment(models: list[dict]):
    return start_experiment_background(models)


@router.post("/experiment/{run_id}/stop")
def api_stop_experiment(run_id: str):
    return stop_experiment(run_id)


@router.get("/experiment/{run_id}/status")
def api_experiment_status(run_id: str):
    return get_experiment_status(run_id)
