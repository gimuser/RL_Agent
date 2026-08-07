from fastapi import APIRouter

router = APIRouter(prefix="/api/training", tags=["Training"])

@router.get("/status")
def training_status():
    return {"status": "running", "current_epoch": 5}

@router.post("/start")
def start_training():
    return {"message": "Training started"}

@router.post("/stop")
def stop_training():
    return {"message": "Training stopped"}

@router.get("/checkpoints")
def get_checkpoints():
    return {"checkpoints": ["model_v1.pth", "model_v2.pth"]}

@router.get("/history")
def get_history():
    return {"history": [{"epoch": 1, "loss": 0.45}]}