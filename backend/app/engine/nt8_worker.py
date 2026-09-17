"""Worker NinjaTrader 8 - monitor para masters y executor para slaves."""
import hashlib
import time
import traceback
import multiprocessing as mp
from datetime import datetime

from app.database import SessionLocal
from app.models.account import Account, SlaveConfig
from app.models.trade_log import TradeLog, TradeAction, TradeResult
from app.engine.nt8_connector import NT8Connector
from app.engine.ticket_mapper import (
    reserve_pending, confirm_open, mark_pending_error, mark_closed, get_slave_ticket,
)
from app.engine.risk_calculator import (
    calculate_contracts_fixed, calculate_contracts_risk_percent,
    calculate_contracts_risk_usd, calculate_contracts_ratio,
    calculate_contracts_balance_prop,
)
from app.engine.command_router import is_slave_linked_to_master
from app.utils.logger import get_logger

logger = get_logger("hydrax.nt8")


def _stable_ticket(id_str: str) -> int:
    return int(hashlib.md5(id_str.encode()).hexdigest()[:12], 16) % 1000000


def _log_trade(master_id: str | None, slave_id: str, action: TradeAction, symbol: str,
               volume: float, price: float, sl: float | None, tp: float | None,
               result: TradeResult, master_ticket: int | None = None,
               slave_ticket: int | None = None,
               error_code: int | None = None, error_msg: str | None = None):
    db = SessionLocal()
    try:
        entry = TradeLog(
            timestamp=datetime.utcnow(),
            master_account_id=master_id,
            slave_account_id=slave_id,
            master_ticket=master_ticket,
            slave_ticket=slave_ticket,
            action=action,
            symbol=symbol,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            result=result,
            error_code=error_code,
            error_message=error_msg,
        )
        db.add(entry)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()

def _emit_event(event_queue, event_type: str, data: dict):
    if event_queue is not None:
        try:
            event_queue.put({"type": event_type, "data": data})
        except Exception:
            pass


def nt8_master_monitor(account_id: str, name: str, bridge_host: str, bridge_port: int,
                       login: str, poll_interval: float,
                       slave_queues: dict, stop_flag: mp.Event, event_queue: mp.Queue):
    display = name or f"nt8-master-{login}"
    conn = NT8Connector(bridge_host, bridge_port)

    if not conn.connect():
        logger.error(f"{display}: connection failed")
        _emit_event(event_queue, "worker_error", {"worker": display, "role": "master", "error": f"No se pudo conectar al bridge {bridge_host}:{bridge_port}"})
        return

    logger.info(f"{display}: connected to NT8 bridge")

    poll = max(poll_interval, 0.1)

    prev_positions = {}
    positions = conn.get_positions(login)
    for p in positions:
        pid = p.get("id") or _stable_ticket(str(p))
        prev_positions[pid] = p
    logger.info(f"{display}: tracking {len(prev_positions)} existing positions")

    pending_open: dict[str, int] = {}
    pending_close: dict[str, dict] = {}

    prev_orders = {str(o.get("ticket", _stable_ticket(str(o)))): o for o in conn.get_orders(login)}
    logger.info(f"{display}: ignoring {len(prev_orders)} existing orders")

    recent_removed_sltp: dict[str, dict] = {}

    first_cycle = True

    master_balance = 0.0
    try:
        info = conn.get_account(login)
        if info and info.get("ok"):
            master_balance = float(info.get("balance", 0))
    except Exception:
        pass

    master_enabled = True

    while not stop_flag.is_set():
        try:
            cur_positions = {}
            positions = conn.get_positions(login)
            for p in positions:
                pid = p.get("id") or _stable_ticket(str(p))
                cur_positions[pid] = p

            cur_orders = {str(o.get("ticket", _stable_ticket(str(o)))): o for o in conn.get_orders(login)}


            for pid, p in list(cur_positions.items()):
                if pid not in prev_positions:
                    sl = p.get("sl", 0) or 0
                    tp = p.get("tp", 0) or 0
                    if not sl and not tp:
                        retries = pending_open.get(pid, 0) + 1
                        if retries < 4:
                            pending_open[pid] = retries
                            del cur_positions[pid]
                            continue
                        pending_open.pop(pid, None)
                    else:
                        pending_open.pop(pid, None)

                    direction = p.get("direction", "BUY")
                    symbol = p.get("symbol", "?")
                    contracts = p.get("contracts", 1)
                    logger.info(f"{display}: new position {pid} {symbol} {direction} sl={sl} tp={tp} raw_tick_val={p.get('tick_value')} raw_tick_size={p.get('tick_size')}")
                    if not master_enabled:
                        continue
                    tick_size = p.get("tick_size", 0.25)
                    tick_value = p.get("tick_value", 12.5)
                    cmd = {
                        "action": "OPEN",
                        "payload": {
                            "symbol": symbol,
                            "direction": direction,
                            "price": p.get("entry_price", 0),
                            "sl": p.get("sl", 0) or 0,
                            "tp": p.get("tp", 0) or 0,
                            "master_ticket": _stable_ticket(pid),
                            "master_account_id": account_id,
                            "master_name": display,
                            "bridge_host": bridge_host,
                            "bridge_port": bridge_port,
                            "contracts": contracts,
                            "nt8_position_id": pid,
                            "tick_size": tick_size,
                            "tick_value": tick_value,
                            "master_balance": master_balance,
                        },
                    }
                    for q in slave_queues.values():
                        if not stop_flag.is_set():
                            q.put(cmd)
                    try:
                        event_queue.put({
                            "type": "position_open",
                            "data": {"master": display, "symbol": symbol,
                                     "direction": direction, "contracts": contracts, "ticket": pid},
                        })
                    except Exception:
                        pass

            removed_sltp = {}
            if not first_cycle:
                for ot, o in prev_orders.items():
                    if ot not in cur_orders and o.get("type") in ("STOP", "LIMIT"):
                        sym = o.get("symbol", "")
                        dir_key = o.get("direction", "BUY")
                        removed_sltp[sym] = dir_key
                        logger.info(f"{display}: order removed {ot} type={o.get('type')} symbol={sym} dir={dir_key} -> added to removed_sltp")
            first_cycle = False

            for sym, dir_key in removed_sltp.items():
                if sym not in recent_removed_sltp:
                    recent_removed_sltp[sym] = {"dir": dir_key, "counter": 3}
                else:
                    recent_removed_sltp[sym] = {"dir": dir_key, "counter": 3}

            decay = [s for s, v in recent_removed_sltp.items() if v["counter"] <= 1]
            for s in decay:
                del recent_removed_sltp[s]
            for s in recent_removed_sltp:
                recent_removed_sltp[s]["counter"] -= 1

            modified_to_zero = set()
            for pid, cur in cur_positions.items():
                if pid in prev_positions:
                    prev = prev_positions[pid]
                    prev_sl = prev.get("sl", 0) or 0
                    prev_tp = prev.get("tp", 0) or 0
                    cur_sl = cur.get("sl", 0) or 0
                    cur_tp = cur.get("tp", 0) or 0
                    if (prev_sl > 0 and cur_sl == 0) or (prev_tp > 0 and cur_tp == 0):
                        modified_to_zero.add(pid)
                        logger.info(f"{display}: modified_to_zero {pid} prev_sl={prev_sl}->{cur_sl} prev_tp={prev_tp}->{cur_tp}")

            confirmed_close = []
            for pid, info in list(pending_close.items()):
                if pid not in cur_positions:
                    confirmed_close.append((pid, info))
                    logger.info(f"{display}: confirmed close for {pid}")
                else:
                    logger.info(f"{display}: flicker detected for {pid}, cancelling close")
                del pending_close[pid]

            for pid, info in confirmed_close:
                p = info["p"]
                close_reason = info.get("reason", "manual")
                symbol = p.get("symbol", "?")
                pos_dir = p.get("direction", "BUY")
                logger.info(f"{display}: closed position {pid} reason={close_reason} symbol={symbol} pos_dir={pos_dir}")
                if close_reason == "manual" and master_enabled:
                    logger.info(f"{display}: sending CLOSE to slaves for {pid} reason={close_reason}")
                    cmd = {
                        "action": "CLOSE",
                        "payload": {
                            "position_ticket": _stable_ticket(pid),
                            "symbol": symbol,
                            "direction": p.get("direction", "BUY"),
                            "contracts": p.get("contracts", 1),
                            "master_account_id": account_id,
                            "bridge_host": bridge_host,
                            "bridge_port": bridge_port,
                            "nt8_position_id": pid,
                        },
                    }
                    for q in slave_queues.values():
                        if not stop_flag.is_set():
                            q.put(cmd)
                try:
                    event_queue.put({
                        "type": "position_close",
                        "data": {"master": display, "symbol": symbol, "ticket": pid, "reason": close_reason},
                    })
                except Exception:
                    pass

            for pid, p in prev_positions.items():
                if pid not in cur_positions:
                    pending_open.pop(pid, None)
                    symbol = p.get("symbol", "?")
                    pos_dir = p.get("direction", "BUY")
                    exit_dir = "SELL" if pos_dir == "BUY" else "BUY"
                    filled_target = (symbol in recent_removed_sltp and recent_removed_sltp[symbol]["dir"] == exit_dir) or pid in modified_to_zero
                    close_reason = "target" if filled_target else "manual"
                    logger.info(f"{display}: detected close candidate {pid} reason={close_reason} symbol={symbol} pos_dir={pos_dir} recent_removed_dir={recent_removed_sltp.get(symbol, {}).get('dir')} pid_in_modified_to_zero={pid in modified_to_zero}")
                    pending_close[pid] = {"p": p, "reason": close_reason}

            for pid, cur in cur_positions.items():
                if pid in prev_positions:
                    prev = prev_positions[pid]
                    new_sl = cur.get("sl", 0) or 0
                    new_tp = cur.get("tp", 0) or 0
                    if (new_sl > 0 or new_tp > 0) and (
                        abs((prev.get("sl", 0) or 0) - new_sl) > 0.01 or
                        abs((prev.get("tp", 0) or 0) - new_tp) > 0.01):
                        logger.info(f"{display}: modify position {pid}")
                        try:
                            event_queue.put({
                                "type": "position_modify",
                            "data": {"master": display, "symbol": cur.get("symbol", "?"),
                                     "ticket": pid, "new_sl": new_sl, "new_tp": new_tp},
                            })
                        except Exception:
                            pass
                        if master_enabled:
                            cmd = {
                                "action": "MODIFY",
                                "payload": {
                                    "position_ticket": _stable_ticket(pid),
                                    "symbol": cur.get("symbol", "?"),
                                    "new_sl": new_sl,
                                    "new_tp": new_tp,
                                    "master_account_id": account_id,
                                    "bridge_host": bridge_host,
                                    "bridge_port": bridge_port,
                                    "nt8_position_id": pid,
                                },
                            }
                            for q in slave_queues.values():
                                if not stop_flag.is_set():
                                    q.put(cmd)

            prev_positions = cur_positions

            for ot, o in cur_orders.items():
                if ot not in prev_orders:
                    logger.info(f"{display}: new pending order {ot} {o.get('symbol')} {o.get('type')} {o.get('direction')}")
                    try:
                        event_queue.put({
                            "type": "order_pending",
                            "data": {
                                "master": display,
                                "symbol": o.get("symbol"),
                                "type": o.get("type"),
                                "direction": o.get("direction"),
                                "quantity": o.get("quantity"),
                                "ticket": ot,
                            },
                        })
                    except Exception:
                        pass
            for ot, o in prev_orders.items():
                if ot not in cur_orders:
                    logger.info(f"{display}: order removed {ot}")
                    try:
                        event_queue.put({
                            "type": "order_removed",
                            "data": {"master": display, "ticket": ot},
                        })
                    except Exception:
                        pass
            prev_orders = cur_orders

            try:
                info = conn.get_account(login)
                if info and info.get("ok"):
                    master_balance = float(info.get("balance", 0))
            except Exception:
                pass

            db = SessionLocal()
            try:
                m = db.query(Account).filter(Account.id == account_id).first()
                if m:
                    master_enabled = m.copy_enable if m.copy_enable is not None else True
            except Exception:
                pass
            finally:
                db.close()

            for _ in range(int(poll * 10)):
                if stop_flag.is_set():
                    break
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"{display}: error: {e}\n{traceback.format_exc()}")
            time.sleep(1)

    conn.disconnect()
    logger.info(f"{display}: monitor stopped")


def nt8_slave_executor(account_id: str, name: str, login: str, bridge_host: str, bridge_port: int,
                       risk_mode: str, risk_percent: float, risk_usd: float,
                       fixed_contracts: int, lot_multiplier: float, max_contracts: int,
                       max_positions: int, autocopy_enable: bool, copy_sl: bool,
                       copy_tp: bool, inverse_copy: bool, copy_modify: bool,
                       sync_close: bool,
                       daily_loss_enabled: bool, daily_loss_limit: float,
                       daily_profit_enabled: bool, daily_profit_limit: float,
                       delay_sec: float,
                       magic_number: int, queue: mp.Queue, stop_flag: mp.Event,
                       event_queue: mp.Queue):
    display = name or f"nt8-slave"

    conn = NT8Connector(bridge_host, bridge_port)
    if not conn.connect():
        logger.error(f"{display}: connection failed")
        _emit_event(event_queue, "worker_error", {"worker": display, "role": "slave", "error": f"No se pudo conectar al bridge {bridge_host}:{bridge_port}"})
        return

    logger.info(f"{display}: connected to NT8 bridge")

    _config = {
        "risk_mode": risk_mode, "risk_percent": risk_percent, "risk_usd": risk_usd,
        "fixed_contracts": fixed_contracts, "lot_multiplier": lot_multiplier,
        "max_contracts": max_contracts, "max_positions": max_positions,
        "autocopy_enable": autocopy_enable, "copy_sl": copy_sl,
        "copy_tp": copy_tp, "inverse_copy": inverse_copy,
        "copy_modify": copy_modify,
        "sync_close": sync_close,
        "daily_loss_enabled": daily_loss_enabled, "daily_loss_limit": daily_loss_limit,
        "daily_loss_mode": "USD",
        "daily_profit_enabled": daily_profit_enabled, "daily_profit_limit": daily_profit_limit,
        "daily_profit_mode": "USD",
        "delay_sec": delay_sec, "magic_number": magic_number,
    }

    def _get_account_balance(connector: NT8Connector, account_login: str) -> float:
        try:
            info = connector.get_account(account_login)
            if info and info.get("ok"):
                return float(info.get("balance", 0))
        except Exception:
            pass
        return 0.0

    def _calc_sl_ticks(entry_price: float, sl_price: float, tick_size: float) -> int:
        if not sl_price or tick_size <= 0:
            return 0
        return max(1, int(abs(entry_price - sl_price) / tick_size))

    def _check_daily_limits():
        if not _config["daily_loss_enabled"] and not _config["daily_profit_enabled"]:
            return None
        try:
            info = conn.get_account(login)
            if not info or not info.get("ok"):
                return None
            realized = float(info.get("realized", 0))
            unrealized = float(info.get("unrealized", 0))
            balance = float(info.get("balance", 0))
            day_pnl = realized + unrealized
            day_start_balance = balance - day_pnl

            loss_limit = _config["daily_loss_limit"]
            if _config.get("daily_loss_mode", "USD") == "PERCENT":
                loss_limit = day_start_balance * (loss_limit / 100.0)

            profit_limit = _config["daily_profit_limit"]
            if _config.get("daily_profit_mode", "USD") == "PERCENT":
                profit_limit = day_start_balance * (profit_limit / 100.0)

            logger.debug(f"{display}: limits check loss_enabled={_config['daily_loss_enabled']} loss={loss_limit} profit_enabled={_config['daily_profit_enabled']} profit={profit_limit} day_pnl={day_pnl:.2f}")
            if _config["daily_loss_enabled"] and day_pnl <= -abs(loss_limit):
                return ("loss", day_pnl)
            if _config["daily_profit_enabled"] and day_pnl >= abs(profit_limit):
                return ("profit", day_pnl)
        except Exception:
            pass
        return None

    def _pause_slave(reason: str):
        logger.warning(f"{display}: limit hit, closing positions first: {reason}")
        try:
            positions = conn.get_positions(login)
            for p in positions:
                pid = p.get("id")
                symbol = p.get("symbol", "")
                if pid:
                    conn.close_position(str(pid), symbol, account=login)
                    logger.warning(f"{display}: limit-closed {symbol}")
        except Exception as e:
            logger.error(f"{display}: error closing positions on limit: {e}")

        db_pause = SessionLocal()
        try:
            sc = db_pause.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
            if sc:
                sc.autocopy_enable = False
                sc.paused_by_limit = True
                db_pause.commit()
            _config["autocopy_enable"] = False
            logger.warning(f"{display}: paused (limit hit): {reason}")
            _emit_event(event_queue, "worker_error", {"worker": display, "error": f"PAUSADO por limite: {reason}"})
        except Exception:
            pass
        finally:
            db_pause.close()

    def _cleanup_orphan_orders():
        try:
            positions = conn.get_positions(login)
            orders = conn.get_orders(login)
            sltp_orders = [o for o in orders if o.get("type") in ("STOP", "LIMIT")]
            if not positions and sltp_orders:
                logger.warning(f"{display}: {len(sltp_orders)} orphan SL/TP orders found, cancelling")
                for o in sltp_orders:
                    symbol = o.get("symbol", "")
                    conn.modify_position(symbol, 0, 0, _config["magic_number"], account=login)
                logger.info(f"{display}: orphan orders cleaned")
        except Exception:
            pass

    def _reset_daily_if_new_day():
        db_r = SessionLocal()
        try:
            sc = db_r.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
            if not sc:
                return
            today = datetime.utcnow().date()
            last = sc.last_pnl_reset.date() if sc.last_pnl_reset else None
            if last != today:
                sc.daily_pnl = 0.0
                sc.last_pnl_reset = datetime.utcnow()
                if sc.paused_by_limit:
                    sc.autocopy_enable = True
                    sc.paused_by_limit = False
                    _config["autocopy_enable"] = True
                    logger.info(f"{display}: daily limit reset + reactivated for new day")
                    _emit_event(event_queue, "copy_ok", {"slave": display, "action": "RESET", "info": "Reactivado por nuevo dia"})
                db_r.commit()
        except Exception:
            pass
        finally:
            db_r.close()

    def reload_config():
        db = SessionLocal()
        try:
            cfg = db.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
            if cfg:
                _config["risk_mode"] = cfg.risk_mode.value if cfg.risk_mode else "FIXED"
                _config["risk_percent"] = cfg.risk_percent or 0.5
                _config["risk_usd"] = cfg.risk_usd or 50.0
                _config["fixed_contracts"] = cfg.fixed_contracts or 1
                _config["lot_multiplier"] = cfg.lot_multiplier or 1.0
                _config["max_contracts"] = cfg.max_contracts or 100
                _config["max_positions"] = cfg.max_positions or 100
                _config["autocopy_enable"] = cfg.autocopy_enable if cfg.autocopy_enable is not None else True
                _config["copy_sl"] = cfg.copy_sl if cfg.copy_sl is not None else True
                _config["copy_tp"] = cfg.copy_tp if cfg.copy_tp is not None else True
                _config["inverse_copy"] = cfg.inverse_copy or False
                _config["copy_modify"] = cfg.copy_modify if cfg.copy_modify is not None else True
                _config["sync_close"] = cfg.sync_close if cfg.sync_close is not None else False
                _config["daily_loss_enabled"] = cfg.daily_loss_enabled or False
                _config["daily_loss_limit"] = cfg.daily_loss_limit or 0.0
                _config["daily_loss_mode"] = cfg.daily_loss_mode.value if cfg.daily_loss_mode else "USD"
                _config["daily_profit_enabled"] = cfg.daily_profit_enabled or False
                _config["daily_profit_limit"] = cfg.daily_profit_limit or 0.0
                _config["daily_profit_mode"] = cfg.daily_profit_mode.value if cfg.daily_profit_mode else "USD"
                _config["delay_sec"] = cfg.delay_sec or 0.0
                _config["magic_number"] = cfg.magic_number or 0
        except Exception:
            pass
        finally:
            db.close()

    idle_cycles = 0

    while not stop_flag.is_set():
        cmd = None
        try:
            cmd = queue.get(timeout=0.5)
        except Exception:
            pass

        if cmd is None:
            idle_cycles += 1
            if idle_cycles >= 4:
                idle_cycles = 0
                reload_config()
                _reset_daily_if_new_day()
                if _config["autocopy_enable"]:
                    limit_hit = _check_daily_limits()
                    if limit_hit:
                        limit_type, pnl_value = limit_hit
                        _pause_slave(f"{limit_type} diario alcanzado: ${pnl_value:.2f}")
                _cleanup_orphan_orders()
            continue
        if stop_flag.is_set():
            break

        action = cmd.get("action")
        logger.info(f"{display}: received {action} from {cmd.get('payload', {}).get('master_name', '?')}")

        reload_config()

        if not _config["autocopy_enable"]:
            continue

        action = cmd.get("action")
        payload = cmd.get("payload", {})
        master_account_id = payload.get("master_account_id")

        if master_account_id and not is_slave_linked_to_master(account_id, master_account_id):
            logger.warning(f"{display}: skipped command from unlinked master {master_account_id}")
            continue

        if action == "OPEN":
            master_ticket = payload["master_ticket"]
            existing = get_slave_ticket(master_ticket, account_id)
            if existing is not None:
                continue

            symbol = payload.get("symbol", "")
            direction = payload.get("direction", "BUY")
            if _config["inverse_copy"]:
                direction = "SELL" if direction.upper() == "BUY" else "BUY"

            reserve_pending(master_ticket, master_account_id, account_id,
                            symbol, payload.get("contracts", 1), payload.get("price", 0), direction)

            if _config["delay_sec"] > 0:
                for _ in range(int(_config["delay_sec"] * 10)):
                    if stop_flag.is_set():
                        break
                    time.sleep(0.1)
                if stop_flag.is_set():
                    break

            sl = payload.get("sl", 0) if _config["copy_sl"] else 0
            tp = payload.get("tp", 0) if _config["copy_tp"] else 0

            if _config["risk_mode"] in ("FIXED", "FIXED_CONTRACTS"):
                contracts = calculate_contracts_fixed(_config["fixed_contracts"])
            elif _config["risk_mode"] == "RATIO":
                contracts = calculate_contracts_ratio(payload.get("contracts", 1), _config["lot_multiplier"])
                logger.info(f"{display}: RATIO master_c={payload.get('contracts',1)} mult={_config['lot_multiplier']} -> {contracts}c")
            elif _config["risk_mode"] == "RISK_PERCENT":
                if sl and payload.get("tick_size"):
                    balance = _get_account_balance(conn, login)
                    tick_size = payload.get("tick_size", 0.25)
                    tick_value = payload.get("tick_value", 12.5)
                    sl_ticks = _calc_sl_ticks(payload.get("price", 0), sl, tick_size)
                    contracts = calculate_contracts_risk_percent(balance, _config["risk_percent"], sl_ticks, tick_value)
                    logger.info(f"{display}: RISK_PERCENT balance={balance} risk%={_config['risk_percent']} ticks={sl_ticks} tick_val={tick_value} -> {contracts}c")
                else:
                    slave_balance = _get_account_balance(conn, login)
                    master_balance = payload.get("master_balance", 0)
                    contracts = calculate_contracts_balance_prop(payload.get("contracts", 1), slave_balance, master_balance)
                    logger.info(f"{display}: RISK_PERCENT sin SL, usando BALANCE_PROP slave={slave_balance} master={master_balance} -> {contracts}c")
            elif _config["risk_mode"] == "RISK_USD":
                if sl and payload.get("tick_size"):
                    tick_size = payload.get("tick_size", 0.25)
                    tick_value = payload.get("tick_value", 12.5)
                    sl_ticks = _calc_sl_ticks(payload.get("price", 0), sl, tick_size)
                    contracts = calculate_contracts_risk_usd(_config["risk_usd"], sl_ticks, tick_value)
                    logger.info(f"{display}: RISK_USD risk={_config['risk_usd']} price={payload.get('price', 0)} sl={sl} ticks={sl_ticks} tick_val={tick_value} -> {contracts}c")
                else:
                    slave_balance = _get_account_balance(conn, login)
                    master_balance = payload.get("master_balance", 0)
                    contracts = calculate_contracts_balance_prop(payload.get("contracts", 1), slave_balance, master_balance)
                    logger.info(f"{display}: RISK_USD sin SL, usando BALANCE_PROP slave={slave_balance} master={master_balance} -> {contracts}c")
            elif _config["risk_mode"] == "BALANCE_PROP":
                slave_balance = _get_account_balance(conn, login)
                master_balance = payload.get("master_balance", 0)
                contracts = calculate_contracts_balance_prop(payload.get("contracts", 1), slave_balance, master_balance)
                logger.info(f"{display}: BALANCE_PROP master_c={payload.get('contracts',1)} slave_bal={slave_balance} master_bal={master_balance} -> {contracts}c")
            else:
                contracts = payload.get("contracts", 1)

            if _config["max_contracts"] > 0 and contracts > _config["max_contracts"]:
                contracts = _config["max_contracts"]

            limit_hit = _check_daily_limits()
            if limit_hit:
                limit_type, pnl_value = limit_hit
                _pause_slave(f"{limit_type} diario alcanzado: ${pnl_value:.2f}")
                continue

            logger.info(f"{display}: OPEN {symbol} {direction} x{contracts} (mode={_config['risk_mode']} sl={sl} tp={tp} max_c={_config['max_contracts']} fixed={_config['fixed_contracts']})")
            result = conn.open_position(symbol, contracts, direction, sl, tp, _config["magic_number"], account=login)
            if result and result.get("ok"):
                slave_ticket = str(result.get("position_id", ""))
                confirm_open(master_ticket, account_id, slave_ticket)
                _log_trade(master_account_id, account_id, TradeAction.OPEN, symbol, contracts,
                           payload.get("price", 0), sl, tp, TradeResult.SUCCESS,
                           master_ticket=master_ticket, slave_ticket=slave_ticket)
                _emit_event(event_queue, "copy_ok", {"slave": display, "symbol": symbol, "action": "OPEN",
                           "contracts": contracts, "master_ticket": master_ticket})
                logger.info(f"{display}: OPEN OK {symbol} x{contracts}")
            else:
                mark_pending_error(master_ticket, account_id)
                _log_trade(master_account_id, account_id, TradeAction.OPEN, symbol, contracts,
                           payload.get("price", 0), sl, tp, TradeResult.FAILED,
                           master_ticket=master_ticket)
                _emit_event(event_queue, "copy_error", {"slave": display, "symbol": symbol, "action": "OPEN",
                           "contracts": contracts, "master_ticket": master_ticket,
                           "error": result.get("error", "Unknown") if result else "No response"})
                logger.error(f"{display}: OPEN FAIL {symbol} x{contracts} | {result.get('error', 'no result') if result else 'result is None'}")

        elif action == "CLOSE":
            master_ticket = payload["position_ticket"]
            slave_position_id = get_slave_ticket(master_ticket, account_id)
            if not slave_position_id:
                logger.warning(f"{display}: no mapping for master_ticket={master_ticket} (maybe position was from before restart?)")
                continue

            symbol = payload.get("symbol", "")
            result = conn.close_position(slave_position_id, symbol, account=login)
            if result and result.get("ok"):
                mark_closed(master_ticket, account_id)
                _log_trade(master_account_id, account_id, TradeAction.CLOSE, payload.get("symbol", ""),
                           payload.get("contracts", 0), 0, None, None, TradeResult.SUCCESS,
                           master_ticket=master_ticket, slave_ticket=_stable_ticket(str(slave_position_id)))
                _emit_event(event_queue, "copy_ok", {"slave": display, "symbol": payload.get("symbol", ""),
                           "action": "CLOSE", "master_ticket": master_ticket, "source": "hydrax"})
                logger.info(f"{display}: CLOSE OK {payload.get('symbol','?')} [HydraX]")
            else:
                _log_trade(master_account_id, account_id, TradeAction.CLOSE, payload.get("symbol", ""),
                           payload.get("contracts", 0), 0, None, None, TradeResult.FAILED,
                           master_ticket=master_ticket, slave_ticket=_stable_ticket(str(slave_position_id)))
                logger.error(f"{display}: CLOSE FAIL {payload.get('symbol','?')} | {result.get('error', 'no result') if result else 'result is None'}")

        elif action == "MODIFY":
            if not _config["copy_modify"]:
                continue
            master_ticket = payload["position_ticket"]
            slave_position_id = get_slave_ticket(master_ticket, account_id)
            if not slave_position_id:
                continue

            symbol = payload.get("symbol", "")
            new_sl = payload.get("new_sl", 0) or 0
            new_tp = payload.get("new_tp", 0) or 0

            if _config["delay_sec"] > 0:
                for _ in range(int(_config["delay_sec"] * 10)):
                    if stop_flag.is_set(): break
                    time.sleep(0.1)
                if stop_flag.is_set(): break

            result = conn.modify_position(symbol, new_sl if _config["copy_sl"] else 0,
                                          new_tp if _config["copy_tp"] else 0,
                                          _config["magic_number"], account=login,
                                          position_id=slave_position_id)
            if result and result.get("ok"):
                _log_trade(master_account_id, account_id, TradeAction.MODIFY, symbol, 0, 0,
                           new_sl, new_tp, TradeResult.SUCCESS,
                           master_ticket=master_ticket, slave_ticket=_stable_ticket(str(slave_position_id)))
                _emit_event(event_queue, "copy_ok", {"slave": display, "symbol": symbol, "action": "MODIFY"})
                logger.info(f"{display}: MODIFY OK {symbol} SL={new_sl} TP={new_tp}")
            else:
                _log_trade(master_account_id, account_id, TradeAction.MODIFY, symbol, 0, 0,
                           new_sl, new_tp, TradeResult.FAILED, master_ticket=master_ticket)

    conn.disconnect()
    logger.info(f"{display}: worker stopped")
