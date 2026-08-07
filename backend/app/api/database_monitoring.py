from fastapi import APIRouter

router = APIRouter(prefix="/api/database", tags=["Database Monitoring"])

@router.get("/health")
def db_health():
    return {"status": "healthy", "database": "MongoDB"}

@router.get("/statistics")
def db_statistics():
    return {"collections_count": 4, "total_objects": 1500}

@router.get("/storage")
def db_storage():
    return {"data_size_mb": 45.2, "storage_size_mb": 60.0}

@router.get("/collections")
def db_collections():
    return {"collections": ["alerts", "decisions", "rewards", "evaluations"]}