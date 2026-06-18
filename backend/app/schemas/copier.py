from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CopierStatus(BaseModel):
    running: bool
    uptime_seconds: Optional[float] = None
    active_masters: int = 0
    active_slaves: int = 0
    total_positions: int = 0
    last_error: Optional[str] = None


class CopierEvent(BaseModel):
    type: str
    timestamp: datetime
    message: str
    details: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    db_connected: bool
    mt5_available: bool
