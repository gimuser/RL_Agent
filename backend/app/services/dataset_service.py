"""Read-only access to the immutable processed dataset splits.

The historical API called this operation an "import", but the authoritative
CSV files are already part of the project.  These functions therefore validate
and audit the requested split; they never create replacement data or invent
statistics.
"""

from datetime import UTC, datetime

from app.data_pipeline.contract import DatasetAudit, audit_processed_split
from app.database.database import pipeline_collection

PIPELINE_STATE = {
    "status": "UNAVAILABLE",
    "last_run": None,
    "total_rows": None,
    "total_columns": None,
    "missing_values": None,
    "split": None,
}


def _log_pipeline_event(event_type: str, audit: DatasetAudit) -> None:
    """Persist an audit when MongoDB is available without masking file results."""
    try:
        pipeline_collection.insert_one(
            {
                "type": event_type,
                "rows": audit.rows,
                "columns": audit.columns,
                "missing_values": audit.missing_values,
                "timestamp": datetime.now(UTC),
            }
        )
    except Exception:
        # The data result is still valid when optional monitoring storage is
        # unavailable; callers can observe DB health through its own endpoint.
        return None


def _validate_split(split: str) -> DatasetAudit:
    audit = audit_processed_split(split)  # type: ignore[arg-type]
    PIPELINE_STATE.update(
        {
            "status": "READY",
            "last_run": datetime.now(UTC).isoformat(),
            "total_rows": audit.rows,
            "total_columns": audit.columns,
            "missing_values": audit.missing_values,
            "split": split,
        }
    )
    _log_pipeline_event(f"{split}_validated", audit)
    return audit


def import_train_dataset():
    audit = _validate_split("train")
    return {
        "message": "Train processed dataset validated",
        "imported_count": audit.rows,
    }


def import_test_dataset():
    audit = _validate_split("test")
    return {
        "message": "Test processed dataset validated",
        "imported_count": audit.rows,
    }


def get_pipeline_status():
    if PIPELINE_STATE["split"] is None:
        try:
            _validate_split("train")
        except Exception:
            return {"status": "UNAVAILABLE", "last_run": None}
    return {
        "status": PIPELINE_STATE["status"],
        "last_run": PIPELINE_STATE["last_run"],
    }


def get_pipeline_statistics():
    if PIPELINE_STATE["split"] is None:
        _validate_split("train")
    return {
        "total_rows": PIPELINE_STATE["total_rows"],
        "total_columns": PIPELINE_STATE["total_columns"],
        "missing_values": PIPELINE_STATE["missing_values"],
    }
