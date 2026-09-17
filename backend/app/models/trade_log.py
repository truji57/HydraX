import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Enum, DateTime, ForeignKey, JSON

from app.database import Base
from app.models.account import gen_uuid


class TradeAction(str, enum.Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    MODIFY = "MODIFY"
    ERROR = "ERROR"


class TradeResult(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class TradeLog(Base):
    __tablename__ = "trade_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    master_account_id = Column(String, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    slave_account_id = Column(String, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    master_ticket = Column(Integer, nullable=True)
    slave_ticket = Column(Integer, nullable=True)
    action = Column(Enum(TradeAction), nullable=False)
    symbol = Column(String(50), nullable=False)
    volume = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    result = Column(Enum(TradeResult), nullable=False)
    error_code = Column(Integer, nullable=True)
    error_message = Column(String(500), nullable=True)
    details = Column(JSON, nullable=True)
