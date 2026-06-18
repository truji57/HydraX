from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.server import ServerCreate, ServerResponse, ServerListResponse
from app.services.server_service import get_servers, get_server_names, create_server, delete_server, delete_server_by_name

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("", response_model=ServerListResponse)
def list_server_names(db: Session = Depends(get_db)):
    return ServerListResponse(servers=get_server_names(db))


@router.get("/list", response_model=list[ServerResponse])
def list_servers_full(db: Session = Depends(get_db)):
    return get_servers(db)


@router.post("", response_model=ServerResponse, status_code=201)
def add_server(data: ServerCreate, db: Session = Depends(get_db)):
    existing = [s for s in get_servers(db) if s.name.lower() == data.name.lower()]
    if existing:
        raise HTTPException(status_code=409, detail="Server already exists")
    return create_server(db, data.name)


@router.delete("/{server_id}", status_code=204)
def remove_server(server_id: str, db: Session = Depends(get_db)):
    if not delete_server(db, server_id):
        raise HTTPException(status_code=404, detail="Server not found")
