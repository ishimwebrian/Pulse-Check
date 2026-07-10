import pytest
import time
from fastapi.testclient import TestClient
from app import app, store

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_store():
    """
    Fixture to clear the monitor store and cancel all active timers before and after each test.
    This guarantees independent test runs and prevents background thread leaks.
    """
    def _clear():
        with store._lock:
            for m in list(store._monitors.values()):
                if m.get("timer"):
                    m["timer"].cancel()
            store._monitors.clear()
            
    _clear()
    yield
    _clear()

def test_register_monitor_success():
    payload = {
        "id": "device-123",
        "timeout": 60,
        "alert_email": "admin@critmon.com"
    }
    response = client.post("/monitors", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Monitor registered successfully"
    assert data["monitor"]["id"] == "device-123"
    assert data["monitor"]["timeout"] == 60
    assert data["monitor"]["alert_email"] == "admin@critmon.com"
    assert data["monitor"]["status"] == "active"

def test_register_monitor_already_exists():
    payload = {
        "id": "device-123",
        "timeout": 60,
        "alert_email": "admin@critmon.com"
    }
    # Register first time
    response1 = client.post("/monitors", json=payload)
    assert response1.status_code == 201

    # Register second time
    response2 = client.post("/monitors", json=payload)
    assert response2.status_code == 400
    assert "already registered" in response2.json()["detail"]

def test_heartbeat_success():
    payload = {
        "id": "device-123",
        "timeout": 60,
        "alert_email": "admin@critmon.com"
    }
    client.post("/monitors", json=payload)

    response = client.post("/monitors/device-123/heartbeat")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Heartbeat received, timer reset"
    assert data["status"] == "active"

def test_heartbeat_not_found():
    response = client.post("/monitors/non-existent-device/heartbeat")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_pause_success():
    payload = {
        "id": "device-123",
        "timeout": 60,
        "alert_email": "admin@critmon.com"
    }
    client.post("/monitors", json=payload)

    # Pause it
    response = client.post("/monitors/device-123/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"

    # Verify status in list
    list_response = client.get("/monitors")
    assert list_response.status_code == 200
    monitors = list_response.json()
    assert len(monitors) == 1
    assert monitors[0]["status"] == "paused"
    assert monitors[0]["remaining_seconds"] == 60.0

def test_heartbeat_resumes_paused_monitor():
    payload = {
        "id": "device-123",
        "timeout": 60,
        "alert_email": "admin@critmon.com"
    }
    client.post("/monitors", json=payload)

    # Pause
    client.post("/monitors/device-123/pause")

    # Send heartbeat (should resume and unpause)
    response = client.post("/monitors/device-123/heartbeat")
    assert response.status_code == 200
    assert response.json()["status"] == "active"

    # Verify status in list
    list_response = client.get("/monitors")
    monitors = list_response.json()
    assert monitors[0]["status"] == "active"

def test_delete_monitor_success():
    payload = {
        "id": "device-123",
        "timeout": 60,
        "alert_email": "admin@critmon.com"
    }
    client.post("/monitors", json=payload)

    # Delete
    response = client.delete("/monitors/device-123")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]

    # Verify gone
    list_response = client.get("/monitors")
    assert len(list_response.json()) == 0

def test_delete_monitor_not_found():
    response = client.delete("/monitors/non-existent")
    assert response.status_code == 404

def test_timeout_expiration_flow(capsys):
    # Register with a 1-second timeout
    payload = {
        "id": "short-lived-device",
        "timeout": 1,
        "alert_email": "admin@critmon.com"
    }
    client.post("/monitors", json=payload)

    # Verify active first
    list_response1 = client.get("/monitors")
    assert list_response1.json()[0]["status"] == "active"
    assert list_response1.json()[0]["remaining_seconds"] > 0.0

    # Wait for the timer to expire (1.2 seconds)
    time.sleep(1.2)

    # Check status changed to 'down'
    list_response2 = client.get("/monitors")
    assert list_response2.json()[0]["status"] == "down"
    assert list_response2.json()[0]["remaining_seconds"] == 0.0

    # Verify a heartbeat on expired monitor fails
    hb_response = client.post("/monitors/short-lived-device/heartbeat")
    assert hb_response.status_code == 400
    assert "expired" in hb_response.json()["detail"]

    # Verify pause on expired monitor fails
    pause_response = client.post("/monitors/short-lived-device/pause")
    assert pause_response.status_code == 400
    assert "expired" in pause_response.json()["detail"]

    # Capture stdout and verify the required alert print output format
    captured = capsys.readouterr()
    assert "ALERT" in captured.out
    assert "short-lived-device" in captured.out
    assert "time" in captured.out
