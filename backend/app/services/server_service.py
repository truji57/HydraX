from typing import Optional

from sqlalchemy.orm import Session

from app.models.server import Server


def get_servers(db: Session) -> list[Server]:
    return db.query(Server).order_by(Server.name).all()


def get_server_names(db: Session) -> list[str]:
    return [s.name for s in db.query(Server).order_by(Server.name).all()]


def create_server(db: Session, name: str) -> Server:
    server = Server(name=name)
    db.add(server)
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


def delete_server_by_name(db: Session, name: str) -> bool:
    server = db.query(Server).filter(Server.name == name).first()
    if not server:
        return False
    db.delete(server)
    db.commit()
    return True
