from fastapi import APIRouter

from app.services.authoritative_training_control import start, status, stop

router = APIRouter(prefix="/api/training-control", tags=["Authoritative Training Control"])


@router.post("")
def start_full_training():
    return start()


@router.get("")
def get_full_training_status():
    return status()


@router.post("/stop")
def stop_full_training():
    return stop()
