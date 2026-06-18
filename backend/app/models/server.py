from sqlalchemy import Column, String

from app.database import Base
from app.models.account import gen_uuid


class Server(Base):
    __tablename__ = "servers"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), unique=True, nullable=False)
