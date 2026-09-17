from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TradeLogResponse(BaseModel):
    id: str
    timestamp: datetime
    master_name: str
    slave_name: str
    master_ticket: Optional[int]
    slave_ticket: Optional[int]
    action: str
    symbol: str
    volume: float
    price: float
    sl: Optional[float]
    tp: Optional[float]
    result: str


class PositionResponse(BaseModel):
    id: str
    master_ticket: int
    master_account_id: str
    slave_account_id: str
    slave_ticket: Optional[int]
    symbol: str
    volume: float
    price_open: float
    direction: str
    status: str
    created_at: datetime
    closed_at: Optional[datetime]
