from pydantic import BaseModel, Field


class ServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ServerResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class ServerListResponse(BaseModel):
    servers: list[str]
