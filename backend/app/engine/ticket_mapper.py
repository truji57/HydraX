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


def confirm_open(master_ticket: int, slave_account_id: str, slave_ticket: str):
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


def get_slave_ticket(master_ticket: int, slave_account_id: str) -> str | None:
    """Returns the slave position_id string, empty string if PENDING, or None if no mapping exists."""
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
            return entry.slave_ticket if entry.slave_ticket else ""
        return None
    finally:
        db.close()


def reconcile_stale_positions() -> int:
    from app.models.account import Account
    from app.engine.nt8_connector import NT8Connector

    fixed = 0
    db = SessionLocal()
    try:
        slaves = db.query(Account).filter(Account.role == "SLAVE", Account.active == True).all()

        for slave in slaves:
            try:
                conn = NT8Connector(slave.bridge_host, slave.bridge_port)
                positions = conn.get_positions(slave.login)
                real_ids = {p.get("id", "") for p in positions}

                open_entries = db.query(TicketMap).filter(
                    TicketMap.slave_account_id == slave.id,
                    TicketMap.status == TicketStatus.OPEN,
                ).all()

                for entry in open_entries:
                    if entry.slave_ticket and entry.slave_ticket.startswith("hp_"):
                        if entry.slave_ticket not in real_ids:
                            entry.status = TicketStatus.CLOSED
                            entry.closed_at = datetime.utcnow()
                            fixed += 1
                            logger.info(f"Reconciled: slave={slave.name} ticket={entry.slave_ticket} -> CLOSED")

                conn.disconnect()
            except Exception:
                pass

        db.commit()
    finally:
        db.close()

    return fixed
