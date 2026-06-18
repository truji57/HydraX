from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
from pathlib import Path

from app.database import get_db
from app.schemas.copier import HealthResponse
from app.schemas.server import ServerListResponse
from app.config import settings
from app.utils.mt5_helpers import mt5_available
from app.services.server_service import get_server_names

router = APIRouter(prefix="/api/system", tags=["system"])


class DirEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[DirEntry]
    drives: list[str]


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    try:
        db.connection()
        db_ok = True
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        db_connected=db_ok,
        mt5_available=mt5_available(),
    )


@router.get("/servers", response_model=ServerListResponse)
def list_servers(db: Session = Depends(get_db)):
    return ServerListResponse(servers=get_server_names(db))


@router.get("/browse", response_model=BrowseResponse)
def browse_filesystem(path: str = Query(default="")):
    try:
        if not path:
            drives = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
            return BrowseResponse(path="", parent=None, entries=[], drives=drives)

        path = path.strip()
        if len(path) == 2 and path[1] == ":":
            path = path + "\\"

        p = Path(path)
        if not p.exists():
            return BrowseResponse(path=str(p), parent=str(p.parent) if p.parent != p else None, entries=[], drives=[])

        if p.is_file():
            p = p.parent

        parent = str(p.parent) if p.parent != p else None

        entries = []
        try:
            for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith("$") or item.name.startswith("."):
                    continue
                if item.is_dir() or item.suffix.lower() == ".exe":
                    entries.append(DirEntry(
                        name=item.name,
                        path=str(item),
                        is_dir=item.is_dir(),
                    ))
        except PermissionError:
            pass

        return BrowseResponse(path=str(p), parent=parent, entries=entries, drives=[])
    except Exception:
        return BrowseResponse(path=path, parent=None, entries=[], drives=[])
