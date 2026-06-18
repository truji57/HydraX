from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SymbolMapCreate(BaseModel):
    base_symbol: str
    broker_server: str
    broker_symbol: str


class SymbolMapUpdate(BaseModel):
    base_symbol: Optional[str] = None
    broker_server: Optional[str] = None
    broker_symbol: Optional[str] = None


class SymbolMapResponse(BaseModel):
    id: str
    base_symbol: str
    broker_server: str
    broker_symbol: str

    model_config = {"from_attributes": True}


class ServerListResponse(BaseModel):
    servers: list[str]
