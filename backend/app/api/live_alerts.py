from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.live_alert_service import (
    activity_collection,
    agent_status,
    analysts_workload,
    assign_alert,
    get_alert,
    get_history,
    get_system_status,
    list_alerts,
    review_alert,
    seed_live_alerts,
)


router = APIRouter(prefix="/api", tags=["Live Alert Operations"])


class ReviewPayload(BaseModel):
    analyst_id: str = Field(default="SA", min_length=1)
    decision: str = Field(min_length=1)
    comment: str = ""
    action: str | None = None


class AssignPayload(BaseModel):
    analyst_id: str = Field(min_length=1)


@router.get("/system/live-status")
def live_system_status():
    return get_system_status()


@router.get("/live-alerts")
def live_alerts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str | None = None,
    severity: str | None = None,
):
    return list_alerts(skip=skip, limit=limit, search=search, severity=severity)


@router.get("/live-alerts/{alert_id}")
def live_alert(alert_id: str):
    document = get_alert(alert_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    document["history"] = get_history(alert_id)
    return document


@router.get("/live-alerts/{alert_id}/history")
def live_alert_history(alert_id: str):
    if get_alert(alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    items = get_history(alert_id)
    return {"items": items, "history": items, "total": len(items)}


@router.get("/live-activity")
def live_activity(limit: int = Query(default=200, ge=1, le=500)):
    items = list(
        activity_collection.find({}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return {"items": items, "activity": items, "total": len(items)}


@router.get("/human-review")
def human_review(limit: int = Query(default=100, ge=1, le=500)):
    result = list_alerts(limit=limit, skip=0)
    items = [item for item in result["items"] if item.get("agent", {}).get("requires_human_review")]
    return {"items": items, "alerts": items, "total": len(items)}


@router.post("/live-alerts/{alert_id}/review")
def human_review_alert(alert_id: str, payload: ReviewPayload):
    try:
        return review_alert(
            alert_id=alert_id,
            analyst_id=payload.analyst_id,
            decision=payload.decision,
            comment=payload.comment,
            action=payload.action,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Alert not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/live-alerts/{alert_id}/assign")
def assign_live_alert(alert_id: str, payload: AssignPayload):
    try:
        return assign_alert(alert_id, payload.analyst_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Alert not found") from exc


@router.get("/agent/live-status")
def live_agent_status():
    return agent_status()


@router.get("/agent/live-alerts")
def live_agent_alerts(limit: int = Query(default=100, ge=1, le=500)):
    return list_alerts(limit=limit, skip=0)


@router.get("/analysts/live-workload")
def live_analyst_workload():
    return analysts_workload()


@router.get("/analysts")
def live_analysts():
    return analysts_workload()


@router.get("/analysts/pending-alerts")
def analyst_pending_alerts(
    analyst_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
):
    """Alerts still requiring analyst control, optionally scoped to one analyst."""
    result = list_alerts(limit=limit, skip=0)
    items = [
        item
        for item in result["items"]
        if item.get("agent", {}).get("requires_human_review")
        and item.get("status") in {"HUMAN_REVIEW_PENDING", "ESCALATED", "OPEN"}
        and (analyst_id is None or item.get("assigned_analyst") == analyst_id)
    ]
    return {"items": items, "alerts": items, "total": len(items)}


@router.get("/analysts/recent-actions")
def analyst_recent_actions(
    limit: int = Query(default=100, ge=1, le=300),
    analyst_id: str | None = None,
):
    """Recent human analyst actions persisted in MongoDB activity history."""
    query = {"actor": {"$ne": "system"}}
    if analyst_id:
        query["actor"] = analyst_id

    activity_items = list(
        activity_collection.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

    items = [
        item
        for item in activity_items
        if str(item.get("action", "")).startswith(("HUMAN_", "ASSIGNED"))
    ]

    return {"items": items, "actions": items, "total": len(items)}


@router.post("/live-alerts/bootstrap")
def bootstrap_live_alerts():
    return seed_live_alerts(force=True)
