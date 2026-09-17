from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ticket_map import TicketMap, TicketStatus
from app.engine.orchestrator import get_orchestrator, get_copier_state

router = APIRouter(prefix="/api/copier", tags=["copier"])


@router.get("/status")
def status(db: Session = Depends(get_db)):
    state = get_copier_state()
    orch = get_orchestrator()
    total = db.query(TicketMap).filter(TicketMap.status == TicketStatus.OPEN).count()
    return {
        "running": state["running"] or orch.running,
        "uptime_seconds": state["uptime_seconds"],
        "active_masters": state["active_masters"],
        "active_slaves": state["active_slaves"],
        "total_positions": total,
        "workers": state.get("workers", {}),
        "nt8_connected": state.get("nt8_connected", False),
        "nt8_last_heartbeat": state.get("nt8_last_heartbeat"),
        "mt5_connected": state.get("mt5_connected", False),
    }


@router.post("/start")
def start(db: Session = Depends(get_db)):
    from app.utils.events import record_event
    orch = get_orchestrator()
    result = orch.start()
    if result.get("ok"):
        record_event(db, "copier_start", {"message": result.get("message", "Copiador iniciado")})
    else:
        record_event(db, "copier_start_error", {"message": result.get("message", "Fallo al iniciar")})
    return result


@router.post("/stop")
def stop(db: Session = Depends(get_db)):
    from app.utils.events import record_event
    orch = get_orchestrator()
    if not orch.running:
        return {"ok": False, "message": "Not running"}
    orch.stop()
    record_event(db, "copier_stop", {"message": "Copiador detenido"})
    return {"ok": True, "message": "Copier stopped"}


@router.post("/emergency-close/{slave_id}")
def emergency_close(slave_id: str, db: Session = Depends(get_db)):
    from app.models.account import Account
    from app.engine.nt8_connector import NT8Connector
    from app.engine.orchestrator import get_orchestrator

    slave = db.query(Account).filter(Account.id == slave_id, Account.role == "SLAVE").first()
    if not slave:
        return {"ok": False, "error": "Slave no encontrado"}

    if slave.platform and slave.platform.value == "MT5":
        orch = get_orchestrator()
        q = orch._slave_queues.get(slave_id)
        if q is None:
            return {"ok": False, "error": "Worker MT5 no activo. Inicia el copiador."}
        try:
            q.put({"action": "EMERGENCY_CLOSE", "payload": {"account_id": slave_id}}, timeout=1)
        except Exception:
            return {"ok": False, "error": "No se pudo encolar el cierre MT5"}
        return {"ok": True, "closed": 0, "errors": 0, "queued": True}

    conn = NT8Connector(slave.bridge_host, slave.bridge_port)
    if not conn.connect():
        return {"ok": False, "error": "No se pudo conectar al bridge NT8"}

    positions = conn.get_positions(slave.login)
    closed = 0
    errors = 0

    for p in positions:
        pid = p.get("id", "")
        if pid:
            result = conn.close_position(str(pid), account=slave.login)
            if result and result.get("ok"):
                closed += 1
                db.query(TicketMap).filter(
                    TicketMap.slave_account_id == slave_id,
                    TicketMap.slave_ticket == pid,
                    TicketMap.status == TicketStatus.OPEN,
                ).update({TicketMap.status: TicketStatus.CLOSED})
            else:
                errors += 1

    db.commit()
    conn.disconnect()
    return {"ok": True, "closed": closed, "errors": errors, "total": len(positions)}


@router.post("/sync")
def sync_positions():
    from app.engine.ticket_mapper import reconcile_stale_positions
    fixed = reconcile_stale_positions()
    return {"ok": True, "fixed": fixed}


@router.get("/dashboard")
def dashboard_stats():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.models.account import Account, SlaveConfig
    from app.engine.nt8_connector import NT8Connector
    from app.engine.orchestrator import MT5_ACCOUNT_STATS, get_copier_state
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        accounts = db.query(Account).filter(Account.active == True).all()
        result = {}
        nt8_connected = get_copier_state().get("nt8_connected", False)

        def fetch_nt8(acc):
            try:
                conn = NT8Connector(acc.bridge_host, acc.bridge_port)
                info = conn.get_account(acc.login)
                found = bool(info and info.get("ok"))
                if not found and nt8_connected:
                    available = set(conn.get_accounts())
                    found = str(acc.login) in available
                conn.disconnect()
                if found:
                    realized = float(info.get("realized", 0) or 0)
                    unrealized = float(info.get("unrealized", 0) or 0)
                    balance = float(info.get("balance", 0) or 0)
                    positions = int(info.get("positions", 0) or 0)
                    conn_flag = info.get("connected")
                    if conn_flag is None:
                        active = not (balance == 0 and unrealized == 0 and realized == 0 and positions == 0)
                    else:
                        active = bool(conn_flag)
                    if active:
                        return acc.id, {"unrealized": unrealized, "positions": positions, "balance": balance, "day_pnl": realized + unrealized, "connected": True}
                return acc.id, {"unrealized": 0, "positions": 0, "balance": 0, "day_pnl": 0, "connected": False}
            except Exception:
                pass
            return acc.id, {"unrealized": 0, "positions": 0, "balance": 0, "day_pnl": 0, "connected": False}

        def fetch_mt5(acc):
            stats = MT5_ACCOUNT_STATS.get(acc.id)
            if not stats or not stats.get("connected"):
                return acc.id, {"unrealized": 0, "positions": 0, "balance": 0, "day_pnl": 0, "connected": False}
            return acc.id, {
                "unrealized": stats.get("unrealized", 0),
                "positions": stats.get("positions", 0),
                "balance": stats.get("balance", 0),
                "day_pnl": stats.get("day_pnl", 0),
                "connected": True,
            }

        def with_limits(acc, data):
            if acc.role != "SLAVE":
                return data
            sc = db.query(SlaveConfig).filter(SlaveConfig.account_id == acc.id).first()
            if not sc:
                return data
            day_start_balance = data.get("balance", 0) - data.get("day_pnl", 0)
            if sc.daily_loss_enabled:
                limit = sc.daily_loss_limit or 0
                if sc.daily_loss_mode and sc.daily_loss_mode.value == "PERCENT":
                    limit = day_start_balance * (limit / 100.0)
                data["loss_limit_usd"] = limit
            if sc.daily_profit_enabled:
                limit = sc.daily_profit_limit or 0
                if sc.daily_profit_mode and sc.daily_profit_mode.value == "PERCENT":
                    limit = day_start_balance * (limit / 100.0)
                data["profit_limit_usd"] = limit
            return data

        with ThreadPoolExecutor(max_workers=max(1, min(len(accounts), 10))) as executor:
            futures = {}
            for acc in accounts:
                if acc.platform and acc.platform.value == "MT5":
                    futures[executor.submit(fetch_mt5, acc)] = acc
                else:
                    futures[executor.submit(fetch_nt8, acc)] = acc
            for future in as_completed(futures, timeout=8):
                acc = futures[future]
                try:
                    acc_id, data = future.result(timeout=5)
                    result[acc_id] = with_limits(acc, data)
                except Exception:
                    pass
            for acc in accounts:
                if acc.id not in result:
                    result[acc.id] = {"unrealized": 0, "positions": 0, "balance": 0, "day_pnl": 0, "connected": False}

        return {"ok": True, "data": result}
    finally:
        db.close()


@router.post("/emergency-close-all")
def emergency_close_all(db: Session = Depends(get_db)):
    from app.models.account import Account
    from app.engine.nt8_connector import NT8Connector
    from app.engine.orchestrator import get_orchestrator

    slaves = db.query(Account).filter(Account.role == "SLAVE", Account.active == True).all()
    total_closed = 0
    total_errors = 0
    queued_mt5 = 0

    orch = get_orchestrator()

    for slave in slaves:
        if slave.platform and slave.platform.value == "MT5":
            q = orch._slave_queues.get(slave.id)
            if q is not None:
                try:
                    q.put({"action": "EMERGENCY_CLOSE", "payload": {"account_id": slave.id}}, timeout=1)
                    queued_mt5 += 1
                except Exception:
                    total_errors += 1
            else:
                total_errors += 1
            continue
        try:
            conn = NT8Connector(slave.bridge_host, slave.bridge_port)
            positions = conn.get_positions(slave.login)
            orders = conn.get_orders(slave.login)

            for o in orders:
                if o.get("type") in ("STOP", "LIMIT"):
                    conn.modify_position(o.get("symbol", ""), 0, 0, 0, account=slave.login)

            for p in positions:
                pid = p.get("id", "")
                if pid:
                    result = conn.close_position(str(pid), p.get("symbol", ""), account=slave.login)
                    if result and result.get("ok"):
                        total_closed += 1
                        db.query(TicketMap).filter(
                            TicketMap.slave_account_id == slave.id,
                            TicketMap.slave_ticket == pid,
                            TicketMap.status == TicketStatus.OPEN,
                        ).update({TicketMap.status: TicketStatus.CLOSED})
                    else:
                        total_errors += 1

            conn.disconnect()
        except Exception:
            total_errors += 1

    db.commit()
    return {"ok": True, "closed": total_closed, "errors": total_errors, "slaves": len(slaves), "queued_mt5": queued_mt5}