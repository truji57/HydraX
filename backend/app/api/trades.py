from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.trade_log import TradeLog
from app.models.account import Account

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
def list_trades(
    slave_id: str | None = None,
    master_id: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(TradeLog)
    if slave_id:
        query = query.filter(TradeLog.slave_account_id == slave_id)
    if master_id:
        query = query.filter(TradeLog.master_account_id == master_id)
    rows = query.order_by(desc(TradeLog.timestamp)).offset(offset).limit(limit).all()
    account_ids = set()
    for r in rows:
        if r.master_account_id:
            account_ids.add(r.master_account_id)
        if r.slave_account_id:
            account_ids.add(r.slave_account_id)
    accounts = {a.id: a.name for a in db.query(Account).filter(Account.id.in_(account_ids)).all()}
    return [
        {
            "id": r.id, "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "master_name": accounts.get(r.master_account_id, "-") if r.master_account_id else "-",
            "slave_name": accounts.get(r.slave_account_id, "-") if r.slave_account_id else "-",
            "master_ticket": r.master_ticket, "slave_ticket": r.slave_ticket,
            "action": r.action.value if r.action else None,
            "symbol": r.symbol, "volume": r.volume, "price": r.price,
            "sl": r.sl, "tp": r.tp, "result": r.result.value if r.result else None,
            "error_code": r.error_code, "error_message": r.error_message,
        }
        for r in rows
    ]


def get_positions(db, slave_id=None, status="OPEN"):
    from app.models.ticket_map import TicketMap
    query = db.query(TicketMap)
    if slave_id:
        query = query.filter(TicketMap.slave_account_id == slave_id)
    if status:
        query = query.filter(TicketMap.status == status)
    return query.order_by(desc(TicketMap.created_at)).all()


@router.get("/positions", response_model=list)
def list_positions(slave_id: str | None = None, status: str = "OPEN", db: Session = Depends(get_db)):
    return get_positions(db, slave_id, status)
