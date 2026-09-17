from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.event_log import EventLog

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(limit: int = Query(200, le=2000), db: Session = Depends(get_db)):
    rows = db.query(EventLog).order_by(desc(EventLog.timestamp)).limit(limit).all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "type": r.type,
            "data": r.data or {},
        }
        for r in rows
    ]