from typing import Optional
from pydantic import BaseModel, Field

from app.models.account import Platform


class ServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    platform: Platform = Platform.MT5


class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    platform: Optional[Platform] = None


class ServerResponse(BaseModel):
    id: str
    name: str
    platform: Platform

    model_config = {"from_attributes": True}


class ServerListResponse(BaseModel):
    servers: list[dict]