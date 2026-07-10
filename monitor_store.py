import threading
import time
import json
import datetime
from typing import Dict, Any, Optional, List
from timer_service import start_monitor_timer

class MonitorStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._monitors: Dict[str, Dict[str, Any]] = {}

    def register(self, monitor_id: str, timeout: int, alert_email: str) -> bool:
        """
        Registers a new device monitor and starts its timeout countdown.
        Returns True if successful, False if already registered.
        """
        with self._lock:
            if monitor_id in self._monitors:
                return False
            
            # Define the timeout expiration callback
            def on_expire():
                self.trigger_timeout(monitor_id)

            # Start the countdown timer
            timer = start_monitor_timer(timeout, on_expire)

            self._monitors[monitor_id] = {
                "id": monitor_id,
                "timeout": timeout,
                "alert_email": alert_email,
                "status": "active",
                "last_heartbeat": time.time(),
                "heartbeat_count": 0,
                "timer": timer
            }
            return True

    def heartbeat(self, monitor_id: str) -> Optional[str]:
        """
        Resets the countdown timer for the specified device and un-pauses if paused.
        Returns:
            "active" - on successful heartbeat / transition to active
            "down" - if the monitor has already expired
            None - if the monitor does not exist
        """
        with self._lock:
            monitor = self._monitors.get(monitor_id)
            if not monitor:
                return None
            
            if monitor["status"] == "down":
                return "down"

            # Cancel existing timer if set
            if monitor["timer"]:
                monitor["timer"].cancel()
                monitor["timer"] = None

            # Set up new timer
            def on_expire():
                self.trigger_timeout(monitor_id)

            new_timer = start_monitor_timer(monitor["timeout"], on_expire)
            monitor["timer"] = new_timer
            monitor["status"] = "active"
            monitor["last_heartbeat"] = time.time()
            monitor["heartbeat_count"] += 1
            return "active"

    def pause(self, monitor_id: str) -> Optional[str]:
        """
        Pauses monitoring for a device, canceling its active timer.
        Returns:
            "paused" - on success
            "down" - if the monitor has already expired
            None - if the monitor does not exist
        """
        with self._lock:
            monitor = self._monitors.get(monitor_id)
            if not monitor:
                return None

            if monitor["status"] == "down":
                return "down"

            # Cancel active timer
            if monitor["timer"]:
                monitor["timer"].cancel()
                monitor["timer"] = None

            monitor["status"] = "paused"
            return "paused"

    def trigger_timeout(self, monitor_id: str):
        """
        Callback fired when a timer expires. Logs the alert and marks status as down.
        """
        with self._lock:
            monitor = self._monitors.get(monitor_id)
            # Only trigger if it is currently active
            if monitor and monitor["status"] == "active":
                monitor["status"] = "down"
                monitor["timer"] = None
                
                # Console log the alert as a single-line JSON string
                alert_payload = {
                    "ALERT": f"Device {monitor_id} is down!",
                    "time": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
                print(json.dumps(alert_payload), flush=True)

    def get_all(self) -> List[Dict[str, Any]]:
        """
        Lists all registered monitors, converting timestamps to ISO format and 
        calculating remaining seconds before timeout.
        """
        with self._lock:
            result = []
            now = time.time()
            for m_id, m in self._monitors.items():
                remaining = 0.0
                if m["status"] == "active":
                    elapsed = now - m["last_heartbeat"]
                    remaining = max(0.0, m["timeout"] - elapsed)
                elif m["status"] == "paused":
                    remaining = float(m["timeout"])
                elif m["status"] == "down":
                    remaining = 0.0

                last_hb_iso = None
                if m["last_heartbeat"]:
                    # Convert float epoch to UTC ISO-8601 string
                    dt = datetime.datetime.fromtimestamp(m["last_heartbeat"], datetime.timezone.utc)
                    last_hb_iso = dt.isoformat()

                result.append({
                    "id": m["id"],
                    "timeout": m["timeout"],
                    "alert_email": m["alert_email"],
                    "status": m["status"],
                    "last_heartbeat": last_hb_iso,
                    "heartbeat_count": m["heartbeat_count"],
                    "remaining_seconds": round(remaining, 2)
                })
            return result

    def delete(self, monitor_id: str) -> bool:
        """
        Unregisters a monitor, canceling its timer. Returns True if found, False otherwise.
        """
        with self._lock:
            monitor = self._monitors.pop(monitor_id, None)
            if not monitor:
                return False
            
            if monitor["timer"]:
                monitor["timer"].cancel()
            return True
