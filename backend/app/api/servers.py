from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.server import ServerCreate, ServerUpdate, ServerResponse, ServerListResponse
from app.utils.events import record_event
from app.services import server_service

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("", response_model=ServerListResponse)
def list_server_names(platform: str = Query(None), db: Session = Depends(get_db)):
    return ServerListResponse(servers=server_service.get_server_names(db, platform))


@router.get("/list", response_model=list[ServerResponse])
def list_servers_full(db: Session = Depends(get_db)):
    return server_service.get_servers(db)


@router.post("", response_model=ServerResponse, status_code=201)
def add_server(data: ServerCreate, db: Session = Depends(get_db)):
    existing = [s for s in server_service.get_servers(db) if s.name.lower() == data.name.lower()]
    if existing:
        raise HTTPException(status_code=409, detail="Server already exists")
    server = server_service.create_server(db, data.name, data.platform.value)
    record_event(db, "server_created", {"name": server.name, "platform": server.platform.value})
    return server


@router.put("/{server_id}", response_model=ServerResponse)
def edit_server(server_id: str, data: ServerUpdate, db: Session = Depends(get_db)):
    server = server_service.update_server(
        db, server_id, name=data.name, platform=data.platform.value if data.platform else None
    )
    if not server:
        raise HTTPException(status_code=404, detail="Server no encontrado")
    record_event(db, "server_updated", {"name": server.name, "platform": server.platform.value})
    return server


@router.get("/export")
def export_servers(db: Session = Depends(get_db)):
    servers = [{"name": s.name, "platform": (s.platform.value if s.platform else "MT5")}
               for s in server_service.get_servers(db)]
    return {"app": "hydrax", "kind": "servers", "version": 1, "servers": servers}


@router.post("/import")
def import_servers(data: dict, db: Session = Depends(get_db)):
    existing = {s.name.lower(): s for s in server_service.get_servers(db)}
    count = 0
    for item in data.get("servers", []):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        platform = item.get("platform") or "MT5"
        if name.lower() in existing:
            existing[name.lower()].platform = platform
        else:
            server_service.create_server(db, name, platform)
        count += 1
    db.commit()
    record_event(db, "server_imported", {"servers": count})
    return {"ok": True, "imported": count}


@router.delete("/{server_id}", status_code=204)
def remove_server(server_id: str, db: Session = Depends(get_db)):
    server = next((s for s in server_service.get_servers(db) if s.id == server_id), None)
    if not server_service.delete_server(db, server_id):
        raise HTTPException(status_code=404, detail="Server not found")
    record_event(db, "server_deleted", {"name": server.name if server else server_id})