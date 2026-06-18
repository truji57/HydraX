from datetime import datetime

from app.database import SessionLocal
from app.models.ticket_map import TicketMap, TicketStatus, Direction
from app.utils.logger import get_logger

logger = get_logger("hydrax.tickets")


def reserve_pending(
    master_ticket: int,
    master_account_id: str,
    slave_account_id: str,
    symbol: str,
    volume: float,
    price_open: float,
    direction: str,
) -> TicketMap:
    db = SessionLocal()
    try:
        existing = (
            db.query(TicketMap)
            .filter(
                TicketMap.master_ticket == master_ticket,
                TicketMap.slave_account_id == slave_account_id,
            )
            .first()
        )
        if existing and existing.status in (TicketStatus.OPEN, TicketStatus.PENDING):
            logger.warning(f"Duplicate prevented: master_ticket={master_ticket} slave={slave_account_id}")
            return existing

        entry = TicketMap(
            master_ticket=master_ticket,
            master_account_id=master_account_id,
            slave_account_id=slave_account_id,
            slave_ticket=None,
            symbol=symbol,
            volume=volume,
            price_open=price_open,
            direction=Direction.BUY if direction.upper() == "BUY" else Direction.SELL,
            status=TicketStatus.PENDING,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    finally:
        db.close()


def confirm_open(master_ticket: int, slave_account_id: str, slave_ticket: int):
    db = SessionLocal()
    try:
        entry = (
            db.query(TicketMap)
            .filter(
                TicketMap.master_ticket == master_ticket,
                TicketMap.slave_account_id == slave_account_id,
                TicketMap.status == TicketStatus.PENDING,
            )
            .first()
        )
        if entry:
            entry.slave_ticket = slave_ticket
            entry.status = TicketStatus.OPEN
            entry.created_at = datetime.utcnow()
            db.commit()
            logger.info(f"Ticket confirmed: master={master_ticket} slave={slave_ticket}")
    finally:
        db.close()


def mark_pending_error(master_ticket: int, slave_account_id: str):
    db = SessionLocal()
    try:
        entry = (
            db.query(TicketMap)
            .filter(
                TicketMap.master_ticket == master_ticket,
                TicketMap.slave_account_id == slave_account_id,
                TicketMap.status == TicketStatus.PENDING,
            )
            .first()
        )
        if entry:
            entry.status = TicketStatus.ERROR
            db.commit()
    finally:
        db.close()


def mark_closed(master_ticket: int, slave_account_id: str):
    db = SessionLocal()
    try:
        entry = (
            db.query(TicketMap)
            .filter(
                TicketMap.master_ticket == master_ticket,
                TicketMap.slave_account_id == slave_account_id,
                TicketMap.status == TicketStatus.OPEN,
            )
            .first()
        )
        if entry:
            entry.status = TicketStatus.CLOSED
            entry.closed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def get_slave_ticket(master_ticket: int, slave_account_id: str) -> int | None:
    """Returns the slave ticket, 0 if PENDING, or None if no mapping exists."""
    db = SessionLocal()
    try:
        entry = (
            db.query(TicketMap)
            .filter(
                TicketMap.master_ticket == master_ticket,
                TicketMap.slave_account_id == slave_account_id,
                TicketMap.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]),
            )
            .first()
        )
        if entry:
            return entry.slave_ticket if entry.slave_ticket else 0
        return None
    finally:
        db.close()
        db.close()
