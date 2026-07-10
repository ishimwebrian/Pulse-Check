from pydantic import BaseModel, Field
from typing import Optional, List

class MonitorCreate(BaseModel):
    id: str = Field(..., min_length=1, description="Unique identifier for the device")
    timeout: int = Field(..., gt=0, description="Countdown timeout in seconds (must be positive)")
    alert_email: str = Field(..., min_length=3, description="Email address to notify if the device goes down")

class MonitorResponse(BaseModel):
    id: str
    timeout: int
    alert_email: str
    status: str
    last_heartbeat: Optional[str] = None
    heartbeat_count: int
    remaining_seconds: Optional[float] = None
