from typing import Optional

from sqlalchemy.orm import Session

from app.models.server import Server
from app.models.account import Platform


def get_servers(db: Session, platform: Optional[str] = None) -> list[Server]:
    q = db.query(Server).order_by(Server.name)
    if platform:
        q = q.filter(Server.platform == platform)
    return q.all()


def get_server_names(db: Session, platform: Optional[str] = None) -> list[dict]:
    servers = get_servers(db, platform)
    return [{"name": s.name, "platform": s.platform.value} for s in servers]


def create_server(db: Session, name: str, platform: str = "MT5") -> Server:
    server = Server(name=name, platform=Platform(platform))
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


def update_server(db: Session, server_id: str, name: Optional[str] = None,
                  platform: Optional[str] = None) -> Optional[Server]:
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        return None
    if name:
        server.name = name
    if platform:
        server.platform = Platform(platform)
    db.commit()
    db.refresh(server)
    return server


def delete_server(db: Session, server_id: str) -> bool:
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        return False
    db.delete(server)
    db.commit()
    return True