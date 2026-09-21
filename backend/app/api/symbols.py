from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.symbol_map import SymbolMap
from app.schemas.symbol import (
    SymbolMapCreate, SymbolMapUpdate, SymbolMapResponse, ServerListResponse,
)
from app.utils.events import record_event
from app.services.symbol_service import (
    get_symbol_map,
    create_symbol_map_entry,
    update_symbol_map_entry,
    delete_symbol_map_entry,
    get_distinct_servers,
    get_distinct_symbols,
)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/map", response_model=list[SymbolMapResponse])
def list_map(base_symbol: str | None = None, server: str | None = None, db: Session = Depends(get_db)):
    return get_symbol_map(db, base_symbol=base_symbol, server=server)


@router.post("/map", response_model=SymbolMapResponse, status_code=201)
def create_map_entry(entry: SymbolMapCreate, db: Session = Depends(get_db)):
    created = create_symbol_map_entry(db, entry)
    record_event(db, "symbol_created", {
        "base_symbol": created.base_symbol, "broker_server": created.broker_server,
        "broker_symbol": created.broker_symbol,
    })
    return created


@router.put("/map/{entry_id}", response_model=SymbolMapResponse)
def update_map_entry(entry_id: str, entry: SymbolMapUpdate, db: Session = Depends(get_db)):
    updated = update_symbol_map_entry(db, entry_id, entry)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    record_event(db, "symbol_updated", {
        "base_symbol": updated.base_symbol, "broker_server": updated.broker_server,
        "broker_symbol": updated.broker_symbol,
    })
    return updated


@router.delete("/map/{entry_id}", status_code=204)
def delete_map_entry(entry_id: str, db: Session = Depends(get_db)):
    from app.models.symbol_map import SymbolMap
    entry = db.query(SymbolMap).filter(SymbolMap.id == entry_id).first()
    if not delete_symbol_map_entry(db, entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
    record_event(db, "symbol_deleted", {
        "base_symbol": entry.base_symbol if entry else entry_id,
        "broker_server": entry.broker_server if entry else "",
    })


@router.get("/servers", response_model=ServerListResponse)
def list_distinct_servers(db: Session = Depends(get_db)):
    return ServerListResponse(servers=get_distinct_servers(db))


@router.get("/symbols", response_model=ServerListResponse)
def list_distinct_symbols(db: Session = Depends(get_db)):
    return ServerListResponse(servers=get_distinct_symbols(db))


@router.get("/export")
def export_symbols(db: Session = Depends(get_db)):
    rows = get_symbol_map(db)
    symbols = [{"base_symbol": m.base_symbol, "broker_server": m.broker_server,
                "broker_symbol": m.broker_symbol} for m in rows]
    return {"app": "hydrax", "kind": "symbols", "version": 1, "symbols": symbols}


@router.post("/import")
def import_symbols(data: dict, db: Session = Depends(get_db)):
    index = {}
    for m in db.query(SymbolMap).all():
        index[(m.base_symbol, m.broker_server)] = m

    count = 0
    for item in data.get("symbols", []):
        base = (item.get("base_symbol") or "").strip()
        server = (item.get("broker_server") or "").strip()
        bsym = (item.get("broker_symbol") or "").strip()
        if not base or not server or not bsym:
            continue
        entry = index.get((base, server))
        if entry:
            entry.broker_symbol = bsym
        else:
            db.add(SymbolMap(base_symbol=base, broker_server=server, broker_symbol=bsym))
            index[(base, server)] = None
        count += 1
    db.commit()
    record_event(db, "symbol_imported", {"symbols": count})
    return {"ok": True, "imported": count}