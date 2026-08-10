import asyncio
import time
from typing import Dict
from fastapi import FastAPI, Request
from app.config.settings import settings


def init_api_status_store(app: FastAPI) -> None:
    # Initialize a dict in app.state to hold status for each component
    app.state.api_statuses = {}
    now = time.time()
    for comp in settings.api_components:
        app.state.api_statuses[comp["name"]] = {
            "name": comp["name"],
            "prefix": comp["prefix"],
            "status": "unknown",
            "last_seen": None,
            "last_checked": now,
            "request_count": 0,
        }


async def api_activity_middleware(request: Request, call_next):
    # Update last_seen for the matching component (by prefix)
    path = request.url.path
    for comp in settings.api_components:
        if path.startswith(comp["prefix"]):
            statuses: Dict = request.app.state.api_statuses
            entry = statuses.get(comp["name"])
            if entry is not None:
                entry["last_seen"] = time.time()
                entry["status"] = "up"
                entry["request_count"] = entry.get("request_count", 0) + 1
            break

    response = await call_next(request)
    return response


async def api_status_monitor_task(app: FastAPI):
    # Background task that marks components 'down' if not seen recently
    interval = max(1, settings.api_status_poll_interval)
    timeout = max(1, settings.api_status_timeout_seconds)
    while True:
        now = time.time()
        statuses: Dict = getattr(app.state, "api_statuses", {})
        for name, entry in statuses.items():
            last = entry.get("last_seen")
            if last is None:
                # Still unknown — mark down only if app has been running for
                # longer than timeout so short-lived startups don't show red.
                if (now - entry.get("last_checked", now)) > timeout:
                    entry["status"] = "down"
            else:
                if (now - last) > timeout:
                    entry["status"] = "down"
                else:
                    entry["status"] = "up"
            entry["last_checked"] = now
        await asyncio.sleep(interval)


def start_status_monitor(app: FastAPI):
    if not settings.enable_api_activity_tracking:
        return
    init_api_status_store(app)
    # Attach middleware
    app.middleware("http")(api_activity_middleware)
    # Start background task
    loop = asyncio.get_event_loop()
    task = loop.create_task(api_status_monitor_task(app))
    app.state.api_status_monitor_task = task


async def stop_status_monitor(app: FastAPI):
    task = getattr(app.state, "api_status_monitor_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
