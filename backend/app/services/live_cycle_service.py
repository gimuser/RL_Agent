from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.live_alert_service import (
    activity_collection,
    alerts_collection,
    analysts_collection,
    review_collection,
    seed_live_alerts,
)
from app.database.database import db

cycles_collection = db["live_alert_cycles"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _archive_current_cycle(cycle_id: str) -> dict[str, Any]:
    alerts = list(alerts_collection.find({}, {"_id": 0}))
    reviews = list(review_collection.find({}, {"_id": 0}))
    activity = list(activity_collection.find({}, {"_id": 0}))
    snapshot = {
        "cycle_id": cycle_id,
        "archived_at": utc_now(),
        "alerts": alerts,
        "reviews": reviews,
        "activity": activity,
        "alert_count": len(alerts),
        "review_count": len(reviews),
        "activity_count": len(activity),
    }
    if alerts or reviews or activity:
        cycles_collection.insert_one(snapshot)
    return snapshot


def start_new_live_cycle(reason: str = "manual_refresh", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Archive the active evaluation cycle and recreate the untouched 40-alert holdout.

    Source files in data_alert are never modified. The active Mongo collections are
    replaced with a fresh cycle so the same isolated alerts can be evaluated again.
    Previous analyst decisions remain available in live_alert_cycles.
    """
    cycle_id = f"CYCLE-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    archived = _archive_current_cycle(cycle_id)

    # seed_live_alerts(force=True) clears only the active live operational
    # collections and reconstructs them from the immutable data_alert files.
    seed_result = seed_live_alerts(force=True)

    now = utc_now()
    alerts_collection.update_many(
        {},
        {
            "$set": {
                "cycle_id": cycle_id,
                "decision_cycle_id": cycle_id,
                "cycle_reason": reason,
                "cycle_started_at": now,
            }
        },
    )
    activity_collection.update_many(
        {},
        {"$set": {"cycle_id": cycle_id, "decision_cycle_id": cycle_id}},
    )

    cycles_collection.update_one(
        {"cycle_id": cycle_id},
        {
            "$set": {
                "cycle_id": cycle_id,
                "status": "ACTIVE",
                "reason": reason,
                "metadata": metadata or {},
                "started_at": now,
                "live_alert_count": int(seed_result.get("alerts", 0)),
                "source": "data_alert/live_source.csv",
                "processed_source": "data_alert/live_processed.csv",
                "lineage_source": "data_alert/live_mapping.csv",
            },
            "$setOnInsert": {
                "previous_cycle_snapshot": {
                    "alert_count": archived.get("alert_count", 0),
                    "review_count": archived.get("review_count", 0),
                    "activity_count": archived.get("activity_count", 0),
                }
            },
        },
        upsert=True,
    )

    return {
        "cycle_id": cycle_id,
        "status": "ACTIVE",
        "reason": reason,
        "alerts": int(seed_result.get("alerts", 0)),
        "archived_alerts": int(archived.get("alert_count", 0)),
        "source_preserved": True,
        "started_at": now.isoformat(),
    }


def current_cycle() -> dict[str, Any] | None:
    alert = alerts_collection.find_one({}, {"_id": 0, "cycle_id": 1, "decision_cycle_id": 1, "cycle_reason": 1, "cycle_started_at": 1})
    if not alert:
        return None
    return alert
