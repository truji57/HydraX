from sqlalchemy import Column, String, UniqueConstraint

from app.database import Base
from app.models.account import gen_uuid


class SymbolMap(Base):
    __tablename__ = "symbol_map"
    __table_args__ = (
        UniqueConstraint("base_symbol", "broker_server", name="uq_symbol_server"),
    )

    id = Column(String, primary_key=True, default=gen_uuid)
    base_symbol = Column(String(50), nullable=False)
    broker_server = Column(String(100), nullable=False)
    broker_symbol = Column(String(50), nullable=False)