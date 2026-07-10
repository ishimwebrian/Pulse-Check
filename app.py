from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from typing import List
from models import MonitorCreate, MonitorResponse
from monitor_store import MonitorStore
import os

app = FastAPI(
    title="Pulse-Check Watchdog Sentinel API",
    description="A thread-safe Dead Man's Switch API for critical infrastructure monitoring.",
    version="1.0.0"
)

# Instantiate the thread-safe memory store
store = MonitorStore()

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    """
    Serves the premium iOS watchdog control dashboard UI.
    """
    try:
        file_path = os.path.join(os.path.dirname(__file__) or ".", "dashboard.html")
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as e:
        return HTMLResponse(
            content=f"<html><body><h1>Dashboard Template Error</h1><p>{str(e)}</p></body></html>",
            status_code=500
        )

@app.post(
    "/monitors",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="Register a new device monitor",
    description="Registers a monitor with a timeout. A countdown timer will immediately start."
)
def register_monitor(monitor: MonitorCreate):
    success = store.register(monitor.id, monitor.timeout, monitor.alert_email)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monitor with ID '{monitor.id}' is already registered."
        )
    return {
        "message": "Monitor registered successfully",
        "monitor": {
            "id": monitor.id,
            "timeout": monitor.timeout,
            "alert_email": monitor.alert_email,
            "status": "active"
        }
    }

@app.post(
    "/monitors/{id}/heartbeat",
    status_code=status.HTTP_200_OK,
    response_model=dict,
    summary="Send a device heartbeat",
    description="Resets the countdown timer for the specified device and unpauses it if it was paused."
)
def send_heartbeat(id: str):
    hb_status = store.heartbeat(id)
    if hb_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitor with ID '{id}' not found."
        )
    if hb_status == "down":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monitor with ID '{id}' has already expired (status: down)."
        )
    return {
        "message": "Heartbeat received, timer reset",
        "status": "active"
    }

@app.post(
    "/monitors/{id}/pause",
    status_code=status.HTTP_200_OK,
    response_model=dict,
    summary="Pause monitoring",
    description="Pauses the countdown timer. No alerts will fire until a heartbeat resumes it."
)
def pause_monitor(id: str):
    pause_status = store.pause(id)
    if pause_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitor with ID '{id}' not found."
        )
    if pause_status == "down":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause an expired monitor (ID '{id}' is down)."
        )
    return {
        "message": "Monitor paused successfully",
        "status": "paused"
    }

@app.get(
    "/monitors",
    status_code=status.HTTP_200_OK,
    response_model=List[MonitorResponse],
    summary="List all monitors (Developer Choice)",
    description="Returns a list of all monitors, their current status, heartbeat stats, and remaining time before timeout."
)
def list_monitors():
    return store.get_all()

@app.delete(
    "/monitors/{id}",
    status_code=status.HTTP_200_OK,
    response_model=dict,
    summary="Delete a monitor (Developer Choice)",
    description="Completely unregisters a monitor and cancels any active timer associated with it."
)
def delete_monitor(id: str):
    success = store.delete(id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Monitor with ID '{id}' not found."
        )
    return {
        "message": f"Monitor with ID '{id}' deleted successfully"
    }
