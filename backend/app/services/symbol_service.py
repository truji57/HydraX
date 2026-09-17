from typing import Optional

from sqlalchemy.orm import Session

from app.models.symbol_map import SymbolMap
from app.schemas.symbol import SymbolMapCreate, SymbolMapUpdate


def get_symbol_map(db: Session, base_symbol: Optional[str] = None, server: Optional[str] = None) -> list[SymbolMap]:
    query = db.query(SymbolMap)
    if base_symbol:
        query = query.filter(SymbolMap.base_symbol == base_symbol)
    if server:
        query = query.filter(SymbolMap.broker_server == server)
    return query.all()


def create_symbol_map_entry(db: Session, data: SymbolMapCreate) -> SymbolMap:
    entry = SymbolMap(
        base_symbol=data.base_symbol,
        broker_server=data.broker_server,
        broker_symbol=data.broker_symbol,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_symbol_map_entry(db: Session, entry_id: str, data: SymbolMapUpdate) -> Optional[SymbolMap]:
    entry = db.query(SymbolMap).filter(SymbolMap.id == entry_id).first()
    if not entry:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)

    db.commit()
    db.refresh(entry)
    return entry


def delete_symbol_map_entry(db: Session, entry_id: str) -> bool:
    entry = db.query(SymbolMap).filter(SymbolMap.id == entry_id).first()
    if not entry:
        return False
    db.delete(entry)
    db.commit()
    return True


def get_distinct_servers(db: Session) -> list[str]:
    results = db.query(SymbolMap.broker_server).distinct().all()
    return [r[0] for r in results]


def get_distinct_symbols(db: Session) -> list[str]:
    results = db.query(SymbolMap.base_symbol).distinct().all()
    return [r[0] for r in results]