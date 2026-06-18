from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.trade_log import TradeAction, TradeResult


class TradeLogResponse(BaseModel):
    id: str
    timestamp: datetime
    master_account_id: Optional[str]
    slave_account_id: Optional[str]
    action: TradeAction
    symbol: str
    volume: float
    price: float
    sl: Optional[float]
    tp: Optional[float]
    result: TradeResult
    error_code: Optional[int]
    error_message: Optional[str]
    details: Optional[dict]

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}
