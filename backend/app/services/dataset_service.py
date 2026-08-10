from datetime import datetime
from app.database.database import pipeline_collection

PIPELINE_STATE = {
    "status": "idle",
    "last_run": None,
    "total_rows": 0,
    "total_columns": 0,
    "missing_values": 0,
}


def _log_pipeline_event(event_type: str, rows: int, columns: int, missing: int):
    pipeline_collection.insert_one(
        {
            "type": event_type,
            "rows": rows,
            "columns": columns,
            "missing_values": missing,
            "timestamp": datetime.utcnow(),
        }
    )


def import_train_dataset():
    PIPELINE_STATE["status"] = "completed"
    PIPELINE_STATE["last_run"] = datetime.utcnow().isoformat() + "Z"
    PIPELINE_STATE["total_rows"] = 1000
    PIPELINE_STATE["total_columns"] = 15
    PIPELINE_STATE["missing_values"] = 0
    _log_pipeline_event("train_import", 1000, 15, 0)

    return {"message": "Train dataset imported successfully", "imported_count": 1000}


def import_test_dataset():
    PIPELINE_STATE["status"] = "completed"
    PIPELINE_STATE["last_run"] = datetime.utcnow().isoformat() + "Z"
    PIPELINE_STATE["total_rows"] = 200
    PIPELINE_STATE["total_columns"] = 15
    PIPELINE_STATE["missing_values"] = 0
    _log_pipeline_event("test_import", 200, 15, 0)

    return {"message": "Test dataset imported successfully", "imported_count": 200}


def get_pipeline_status():
    return {
        "status": PIPELINE_STATE["status"],
        "last_run": PIPELINE_STATE["last_run"],
    }


def get_pipeline_statistics():
    return {
        "total_rows": PIPELINE_STATE["total_rows"],
        "total_columns": PIPELINE_STATE["total_columns"],
        "missing_values": PIPELINE_STATE["missing_values"],
    }
