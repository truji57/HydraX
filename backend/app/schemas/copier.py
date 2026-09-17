from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CopierStatus(BaseModel):
    running: bool
    uptime_seconds: Optional[float] = None
    active_masters: int = 0
    active_slaves: int = 0
    total_positions: int = 0
    workers: dict = {}


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    db_connected: bool
