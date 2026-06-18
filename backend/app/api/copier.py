from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.copier import CopierStatus
from app.database import get_db
from app.models.ticket_map import TicketMap, TicketStatus
from app.engine.orchestrator import get_orchestrator, get_copier_state

router = APIRouter(prefix="/api/copier", tags=["copier"])


@router.get("/status")
def status(db: Session = Depends(get_db)):
    state = get_copier_state()
    orch = get_orchestrator()
    total_positions = db.query(TicketMap).filter(TicketMap.status == TicketStatus.OPEN).count()
    return {
        "running": state["running"] or orch.running,
        "uptime_seconds": state["uptime_seconds"],
        "active_masters": state["active_masters"],
        "active_slaves": state["active_slaves"],
        "total_positions": total_positions,
        "workers": state.get("workers", {}),
    }


@router.post("/start")
def start():
    orch = get_orchestrator()
    result = orch.start()
    return result


@router.post("/stop")
def stop():
    orch = get_orchestrator()
    if not orch.running:
        return {"ok": False, "message": "Copier not running"}
    orch.stop()
    return {"ok": True, "message": "Copier stopped"}


@router.post("/reset-positions")
def reset_positions(db: Session = Depends(get_db)):
    db.query(TicketMap).filter(TicketMap.status == TicketStatus.OPEN).update(
        {TicketMap.status: TicketStatus.CLOSED}
    )
    db.commit()
    remaining = db.query(TicketMap).filter(TicketMap.status == TicketStatus.OPEN).count()
    return {"ok": True, "message": f"Posiciones reseteadas. Quedan {remaining} abiertas."}


@router.post("/sync")
def sync_positions(db: Session = Depends(get_db)):
    import MetaTrader5 as mt5
    from app.models.account import Account
    from app.utils.crypto import decrypt_password

    fixed = 0
    slaves = db.query(Account).filter(Account.role == "SLAVE", Account.active == True).all()

    for slave in slaves:
        try:
            if not mt5.initialize(path=slave.terminal_path, timeout=5000):
                continue
            password = decrypt_password(slave.password)
            if not mt5.login(login=slave.login, password=password, server=slave.server):
                mt5.shutdown()
                continue

            real_tickets = {int(p.ticket) for p in (mt5.positions_get() or [])}

            open_entries = db.query(TicketMap).filter(
                TicketMap.slave_account_id == slave.id,
                TicketMap.status == TicketStatus.OPEN,
            ).all()

            for entry in open_entries:
                if entry.slave_ticket and entry.slave_ticket not in real_tickets:
                    entry.status = TicketStatus.CLOSED
                    fixed += 1

            mt5.shutdown()
        except Exception:
            try:
                mt5.shutdown()
            except Exception:
                pass

    db.commit()
    remaining = db.query(TicketMap).filter(TicketMap.status == TicketStatus.OPEN).count()
    return {"ok": True, "fixed": fixed, "remaining_open": remaining}
