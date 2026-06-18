from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.trade_log import TradeLog
from app.models.ticket_map import TicketMap


def get_trade_logs(
    db: Session,
    slave_id: Optional[str] = None,
    master_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TradeLog]:
    query = db.query(TradeLog)
    if slave_id:
        query = query.filter(TradeLog.slave_account_id == slave_id)
    if master_id:
        query = query.filter(TradeLog.master_account_id == master_id)
    return query.order_by(desc(TradeLog.timestamp)).offset(offset).limit(limit).all()


def get_positions(
    db: Session,
    slave_id: Optional[str] = None,
    status: str = "OPEN",
) -> list[TicketMap]:
    query = db.query(TicketMap)
    if slave_id:
        query = query.filter(TicketMap.slave_account_id == slave_id)
    if status:
        query = query.filter(TicketMap.status == status)
    return query.order_by(desc(TicketMap.created_at)).all()
