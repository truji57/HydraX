from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON

from app.database import Base
from app.models.account import gen_uuid


class EventLog(Base):
    __tablename__ = "event_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    type = Column(String(50), nullable=False)
    data = Column(JSON, nullable=True)