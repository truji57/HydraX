from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.symbol import SymbolMapCreate, SymbolMapUpdate, SymbolMapResponse, ServerListResponse
from app.services.symbol_service import (
    get_symbol_map,
    create_symbol_map_entry,
    update_symbol_map_entry,
    delete_symbol_map_entry,
    get_distinct_servers,
)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("/map", response_model=list[SymbolMapResponse])
def list_map(base_symbol: str | None = None, server: str | None = None, db: Session = Depends(get_db)):
    return get_symbol_map(db, base_symbol=base_symbol, server=server)


@router.post("/map", response_model=SymbolMapResponse, status_code=201)
def create_map_entry(entry: SymbolMapCreate, db: Session = Depends(get_db)):
    return create_symbol_map_entry(db, entry)


@router.put("/map/{entry_id}", response_model=SymbolMapResponse)
def update_map_entry(entry_id: str, entry: SymbolMapUpdate, db: Session = Depends(get_db)):
    updated = update_symbol_map_entry(db, entry_id, entry)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated


@router.delete("/map/{entry_id}", status_code=204)
def delete_map_entry(entry_id: str, db: Session = Depends(get_db)):
    if not delete_symbol_map_entry(db, entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
