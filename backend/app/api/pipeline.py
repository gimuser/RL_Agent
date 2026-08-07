from fastapi import APIRouter
from app.schemas.pipeline_schema import PipelineStats, PipelineImportResponse
router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])

@router.post("/import-train", response_model=PipelineImportResponse)
def import_train_dataset():
    return {"message": "Train dataset imported successfully", "imported_count": 1000}

@router.post("/import-test", response_model=PipelineImportResponse)
def import_test_dataset():
    return {"message": "Test dataset imported successfully", "imported_count": 200}

@router.get("/status")
def get_pipeline_status():
    return {"status": "completed", "last_run": "2026-04-01T10:00:00Z"}

@router.get("/statistics", response_model=PipelineStats)
def get_pipeline_statistics():
    return {"total_rows": 1200, "total_columns": 15, "missing_values": 0}