from sqlalchemy import Column, String, Enum

from app.database import Base
from app.models.account import gen_uuid, Platform


class Server(Base):
    __tablename__ = "servers"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    platform = Column(Enum(Platform), default=Platform.MT5, nullable=False)