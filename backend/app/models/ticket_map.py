import enum
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Enum, DateTime, ForeignKey

from app.database import Base
from app.models.account import gen_uuid


class TicketStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class Direction(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class TicketMap(Base):
    __tablename__ = "ticket_map"

    id = Column(String, primary_key=True, default=gen_uuid)
    master_ticket = Column(Integer, nullable=False)
    master_account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    slave_account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    slave_ticket = Column(Integer, nullable=True)
    symbol = Column(String(50), nullable=False)
    volume = Column(Float, nullable=False)
    price_open = Column(Float, nullable=False)
    direction = Column(Enum(Direction), nullable=False)
    status = Column(Enum(TicketStatus), default=TicketStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
