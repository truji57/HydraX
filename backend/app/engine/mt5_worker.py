"""Workers MetaTrader 5 - monitor para masters y executor para slaves (via paquete MetaTrader5).

Portado de la OldVersion (master_monitor.py / slave_executor.py) al estilo del
nt8_worker.py actual. Cada proceso inicializa su propio terminal MT5.
"""
import time
import traceback
import multiprocessing as mp
from datetime import datetime

from app.database import SessionLocal
from app.models.account import SlaveConfig
from app.models.trade_log import TradeLog, TradeAction, TradeResult
from app.engine.risk_calculator import (
    calculate_lots_fixed, calculate_lots_risk_percent, calculate_lots_risk_usd,
    calculate_lots_ratio, calculate_lots_balance_prop,
)
from app.engine.ticket_mapper import (
    reserve_pending, confirm_open, mark_pending_error, mark_closed, get_slave_ticket,
)
from app.models.ticket_map import TicketMap, TicketStatus
from app.engine.command_router import is_slave_linked_to_master
from app.utils.logger import get_logger
from app.utils.crypto import decrypt_password
from app.utils import mt5_helpers
from app.utils.mt5_helpers import (
    connect_mt5, disconnect_mt5, get_account_info, get_positions, get_orders,
    get_history_deals_since, open_position, close_position, modify_position,
    cancel_pending_orders,
)

logger = get_logger("hydrax.mt5")

ORDER_TYPE_MAP = {0: "BUY_LIMIT", 1: "SELL_LIMIT", 2: "BUY_STOP", 3: "SELL_STOP",
                  4: "BUY_STOP_LIMIT", 5: "SELL_STOP_LIMIT"}


def _decrypt_password(enc: str) -> str:
    try:
        return decrypt_password(enc) if enc else ""
    except Exception:
        return ""


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


def _account_stats(account_id: str) -> dict:
    try:
        info = get_account_info()
        if not info:
            return {"account_id": account_id, "connected": False}
        positions = get_positions()
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        realized = sum(float(d.get("profit", 0) or 0) for d in get_history_deals_since(day_start))
        floating = float(info.get("profit", 0) or 0)
        return {
            "account_id": account_id,
            "balance": float(info.get("balance", 0) or 0),
            "equity": float(info.get("equity", 0) or 0),
            "unrealized": floating,
            "day_pnl": realized + floating,
            "positions": len(positions),
            "server": info.get("server"),
            "connected": True,
        }
    except Exception:
        return {"account_id": account_id, "connected": False}


def _emit_stats(event_queue, account_id: str):
    if event_queue is not None:
        _emit_event(event_queue, "mt5_account_stats", _account_stats(account_id))


def mt5_master_monitor(account_id: str, name: str, login: int, password_enc: str,
                       server: str, terminal_path: str, poll_interval: float,
                       slave_queues: dict, stop_flag: mp.Event, event_queue: mp.Queue):
    display = name or f"mt5-master-{login}"

    if not connect_mt5(int(login), _decrypt_password(password_enc), server, terminal_path):
        err = mt5_helpers.get_last_error()
        logger.error(f"{display}: connection failed: {err}")
        _emit_event(event_queue, "worker_error", {"worker": display, "role": "master",
                                                  "error": f"No se pudo conectar a MT5 ({server}): {err}"})
        return

    logger.info(f"{display}: connected to {server}")

    _emit_stats(event_queue, account_id)

    def snapshot():
        snap = {}
        for p in get_positions():
            snap[int(p["ticket"])] = {
                "ticket": int(p["ticket"]), "symbol": p.get("symbol", ""),
                "volume": float(p.get("volume", 0) or 0),
                "price_open": float(p.get("price_open", 0) or 0),
                "sl": float(p.get("sl", 0) or 0), "tp": float(p.get("tp", 0) or 0),
                "type": int(p.get("type", 0)),
                "side": "BUY" if int(p.get("type", 0)) == 0 else "SELL",
            }
        return snap

    prev_positions = snapshot()
    for t, p in prev_positions.items():
        logger.info(f"{display}: ignoring existing position ticket={t}")

    prev_orders = {int(o.get("ticket", 0)) for o in get_orders()}
    for ot in prev_orders:
        logger.info(f"{display}: ignoring existing pending order ticket={ot}")

    master_balance = 0.0
    try:
        info = get_account_info()
        if info:
            master_balance = float(info.get("balance", 0) or 0)
    except Exception:
        pass

    try:
        stats_counter = 0
        while not stop_flag.is_set():
            cur_positions = snapshot()

            for t, p in cur_positions.items():
                if t not in prev_positions:
                    logger.info(f"{display}: new position ticket={t} {p['symbol']} {p['side']} {p['volume']} lots")
                    cmd = {
                        "action": "OPEN",
                        "payload": {
                            "symbol": p["symbol"],
                            "side": p["side"],
                            "price": p["price_open"],
                            "sl": p["sl"],
                            "tp": p["tp"],
                            "master_ticket": t,
                            "master_account_id": account_id,
                            "master_name": display,
                            "server_master": server,
                            "volume": p["volume"],
                            "price_open": p["price_open"],
                            "master_balance": master_balance,
                        },
                    }
                    for q in slave_queues.values():
                        if not stop_flag.is_set():
                            q.put(cmd)
                    _emit_event(event_queue, "position_open", {
                        "master": display, "symbol": p["symbol"], "direction": p["side"],
                        "volume": p["volume"], "ticket": t,
                    })

            for t, p in prev_positions.items():
                if t not in cur_positions:
                    logger.info(f"{display}: closed position ticket={t} {p['symbol']}")
                    cmd = {
                        "action": "CLOSE",
                        "payload": {
                            "position_ticket": t,
                            "symbol": p["symbol"],
                            "side": p["side"],
                            "volume": p["volume"],
                            "master_account_id": account_id,
                            "server_master": server,
                        },
                    }
                    for q in slave_queues.values():
                        if not stop_flag.is_set():
                            q.put(cmd)
                    _emit_event(event_queue, "position_close", {
                        "master": display, "symbol": p["symbol"], "ticket": t,
                    })

            for t, cur in cur_positions.items():
                if t in prev_positions:
                    prev = prev_positions[t]
                    if abs(prev["sl"] - cur["sl"]) > 1e-6 or abs(prev["tp"] - cur["tp"]) > 1e-6:
                        logger.info(f"{display}: modify ticket={t} {cur['symbol']} SL {prev['sl']}->{cur['sl']} TP {prev['tp']}->{cur['tp']}")
                        cmd = {
                            "action": "MODIFY",
                            "payload": {
                                "position_ticket": t,
                                "symbol": cur["symbol"],
                                "new_sl": cur["sl"],
                                "new_tp": cur["tp"],
                                "master_account_id": account_id,
                                "server_master": server,
                            },
                        }
                        for q in slave_queues.values():
                            if not stop_flag.is_set():
                                q.put(cmd)
                        _emit_event(event_queue, "position_modify", {
                            "master": display, "symbol": cur["symbol"], "ticket": t,
                            "new_sl": cur["sl"], "new_tp": cur["tp"],
                        })

            prev_positions = cur_positions

            cur_orders = {int(o.get("ticket", 0)) for o in get_orders()}
            all_orders = {int(o.get("ticket", 0)): o for o in get_orders()}
            for ot in cur_orders - prev_orders:
                o = all_orders.get(ot)
                if o:
                    otype = ORDER_TYPE_MAP.get(int(o.get("type", -1)), "UNKNOWN")
                    logger.info(f"{display}: new pending order ticket={ot} {o.get('symbol')} {otype}")
                    _emit_event(event_queue, "order_pending", {
                        "master": display, "symbol": o.get("symbol"), "type": otype,
                        "volume": o.get("volume_current"), "price": o.get("price_open"), "ticket": ot,
                    })
            for ot in prev_orders - cur_orders:
                _emit_event(event_queue, "order_removed", {"master": display, "ticket": ot})
            prev_orders = cur_orders

            try:
                info = get_account_info()
                if info:
                    master_balance = float(info.get("balance", 0) or 0)
            except Exception:
                pass

            for _ in range(int(max(poll_interval or 0.5, 0.1) * 10)):
                if stop_flag.is_set():
                    break
                time.sleep(0.1)

            stats_counter += 1
            if stats_counter % 8 == 0:
                _emit_stats(event_queue, account_id)

    except Exception as e:
        logger.error(f"{display}: error in monitor loop: {e}\n{traceback.format_exc()}")
    finally:
        disconnect_mt5()
        logger.info(f"{display}: monitor stopped")


def mt5_slave_executor(account_id: str, name: str, login: int, password_enc: str,
                       server: str, terminal_path: str, filling_mode: str | None,
                       risk_mode: str, risk_percent: float, risk_usd: float,
                       fixed_lots: float, lot_multiplier: float, max_lots: float,
                       max_positions: int, autocopy_enable: bool, copy_sl: bool,
                       copy_tp: bool, inverse_copy: bool, copy_modify: bool,
                       sync_close: bool,
                       daily_loss_enabled: bool, daily_loss_limit: float,
                       daily_profit_enabled: bool, daily_profit_limit: float,
                       delay_sec: float, magic_number: int,
                       queue: mp.Queue, stop_flag: mp.Event, event_queue: mp.Queue):
    display = name or f"mt5-slave-{login}"

    if not connect_mt5(int(login), _decrypt_password(password_enc), server, terminal_path):
        err = mt5_helpers.get_last_error()
        logger.error(f"{display}: connection failed: {err}")
        _emit_event(event_queue, "worker_error", {"worker": display, "role": "slave",
                                                  "error": f"No se pudo conectar a MT5 ({server}): {err}"})
        return

    logger.info(f"{display}: connected to {server}")

    _emit_stats(event_queue, account_id)

    _force_filling = mt5_helpers._resolve_filling(filling_mode)
    if _force_filling is not None:
        logger.info(f"{display}: filling mode forzado por cuenta: {filling_mode}")

    _config = {
        "risk_mode": risk_mode, "risk_percent": risk_percent, "risk_usd": risk_usd,
        "filling_mode": filling_mode,
        "fixed_lots": fixed_lots, "lot_multiplier": lot_multiplier,
        "max_lots": max_lots, "max_positions": max_positions,
        "autocopy_enable": autocopy_enable, "copy_sl": copy_sl,
        "copy_tp": copy_tp, "inverse_copy": inverse_copy,
        "copy_modify": copy_modify, "sync_close": sync_close,
        "daily_loss_enabled": daily_loss_enabled, "daily_loss_limit": daily_loss_limit,
        "daily_loss_mode": "USD",
        "daily_profit_enabled": daily_profit_enabled, "daily_profit_limit": daily_profit_limit,
        "daily_profit_mode": "USD",
        "delay_sec": delay_sec, "magic_number": magic_number,
    }

    def reload_config():
        db = SessionLocal()
        try:
            cfg = db.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
            if cfg:
                _config["risk_mode"] = cfg.risk_mode.value if cfg.risk_mode else "FIXED"
                _config["risk_percent"] = cfg.risk_percent or 0.5
                _config["risk_usd"] = cfg.risk_usd or 50.0
                _config["fixed_lots"] = getattr(cfg, "fixed_lots", None) or _config["fixed_lots"]
                _config["lot_multiplier"] = cfg.lot_multiplier or 1.0
                _config["max_lots"] = getattr(cfg, "max_lots", None) or _config["max_lots"]
                _config["max_positions"] = cfg.max_positions or 100
                _config["autocopy_enable"] = cfg.autocopy_enable if cfg.autocopy_enable is not None else True
                _config["copy_sl"] = cfg.copy_sl if cfg.copy_sl is not None else True
                _config["copy_tp"] = cfg.copy_tp if cfg.copy_tp is not None else True
                _config["inverse_copy"] = cfg.inverse_copy or False
                _config["copy_modify"] = cfg.copy_modify if cfg.copy_modify is not None else True
                _config["sync_close"] = cfg.sync_close if cfg.sync_close is not None else False
                _config["delay_sec"] = cfg.delay_sec or 0.0
                _config["magic_number"] = cfg.magic_number or 0
                _config["daily_loss_enabled"] = cfg.daily_loss_enabled or False
                _config["daily_loss_limit"] = cfg.daily_loss_limit or 0.0
                _config["daily_profit_enabled"] = cfg.daily_profit_enabled or False
                _config["daily_profit_limit"] = cfg.daily_profit_limit or 0.0
        except Exception:
            pass
        finally:
            db.close()

    def _check_daily_limits():
        if not _config["daily_loss_enabled"] and not _config["daily_profit_enabled"]:
            return None
        try:
            info = get_account_info()
            if not info:
                return None
            balance = float(info.get("balance", 0) or 0)
            floating = float(info.get("profit", 0) or 0)
            day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            realized = sum(float(d.get("profit", 0) or 0) for d in get_history_deals_since(day_start))
            day_pnl = realized + floating
            day_start_balance = balance - day_pnl

            loss_limit = _config["daily_loss_limit"]
            if _config.get("daily_loss_mode", "USD") == "PERCENT":
                loss_limit = day_start_balance * (loss_limit / 100.0)
            profit_limit = _config["daily_profit_limit"]
            if _config.get("daily_profit_mode", "USD") == "PERCENT":
                profit_limit = day_start_balance * (profit_limit / 100.0)

            logger.debug(f"{display}: limits check day_pnl={day_pnl:.2f} loss={loss_limit} profit={profit_limit}")
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
            for p in get_positions():
                ticket = int(p.get("ticket", 0) or 0)
                symbol = p.get("symbol", "")
                side = "BUY" if int(p.get("type", 0)) == 0 else "SELL"
                if ticket:
                    close_position(symbol, ticket, side, filling=_force_filling)
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

    def _account_balance() -> float:
        try:
            info = get_account_info()
            if info:
                return float(info.get("balance", 0) or 0)
        except Exception:
            pass
        return 0.0

    idle_cycles = 0

    try:
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
                    _emit_stats(event_queue, account_id)
                    if _config["autocopy_enable"]:
                        limit_hit = _check_daily_limits()
                        if limit_hit:
                            limit_type, pnl_value = limit_hit
                            _pause_slave(f"{limit_type} diario alcanzado: ${pnl_value:.2f}")
                continue
            if stop_flag.is_set():
                break

            action = cmd.get("action")
            logger.info(f"{display}: received {action} from {cmd.get('payload', {}).get('master_name', '?')}")

            payload = cmd.get("payload", {})

            if action == "EMERGENCY_CLOSE":
                logger.warning(f"{display}: EMERGENCY CLOSE solicitado")
                try:
                    cancel_pending_orders()
                except Exception:
                    pass
                closed_ids = []
                for p in get_positions():
                    ticket = int(p.get("ticket", 0) or 0)
                    if not ticket:
                        continue
                    symbol = p.get("symbol", "")
                    side = "BUY" if int(p.get("type", 0)) == 0 else "SELL"
                    res = close_position(symbol, ticket, side, filling=_force_filling)
                    if res and res.get("ok"):
                        closed_ids.append(str(ticket))
                if closed_ids:
                    try:
                        db_ec = SessionLocal()
                        try:
                            db_ec.query(TicketMap).filter(
                                TicketMap.slave_account_id == account_id,
                                TicketMap.slave_ticket.in_(closed_ids),
                                TicketMap.status == TicketStatus.OPEN,
                            ).update({TicketMap.status: TicketStatus.CLOSED})
                            db_ec.commit()
                        finally:
                            db_ec.close()
                    except Exception:
                        pass
                _emit_stats(event_queue, account_id)
                _emit_event(event_queue, "copy_ok", {"slave": display, "action": "EMERGENCY_CLOSE", "closed": len(closed_ids)})
                continue

            reload_config()

            if not _config["autocopy_enable"]:
                payload_skip = cmd.get("payload", {})
                logger.warning(f"{display}: SKIP comando {action} {payload_skip.get('symbol', '')} por autocopy desactivado (pausado)")
                continue

            payload = cmd.get("payload", {})
            master_account_id = payload.get("master_account_id")

            if master_account_id and not is_slave_linked_to_master(account_id, master_account_id):
                logger.warning(f"{display}: skipped command from unlinked master {master_account_id}")
                continue

            symbol = payload.get("symbol", "")
            server_master = payload.get("server_master", "")
            if server_master and server_master != server:
                from app.engine.symbol_translator import translate_symbol
                translated = translate_symbol(symbol, server_master, server)
                if translated != symbol:
                    logger.info(f"{display}: simbolo {symbol} ({server_master}) -> {translated} ({server})")
                    symbol = translated

            if action == "OPEN":
                master_ticket = payload["master_ticket"]
                existing = get_slave_ticket(master_ticket, account_id)
                if existing is not None:
                    logger.warning(f"{display}: duplicate prevented master_ticket={master_ticket}")
                    continue

                direction = payload.get("side", "BUY")
                if _config["inverse_copy"]:
                    direction = "SELL" if direction.upper() == "BUY" else "BUY"

                reserve_pending(master_ticket, master_account_id, account_id,
                                symbol, payload.get("volume", 0), payload.get("price_open", 0), direction)

                if _config["delay_sec"] > 0:
                    for _ in range(int(_config["delay_sec"] * 10)):
                        if stop_flag.is_set():
                            break
                        time.sleep(0.1)
                    if stop_flag.is_set():
                        break

                entry_price = payload.get("price", 0)
                sl = payload.get("sl", 0.0) if _config["copy_sl"] else 0.0
                tp = payload.get("tp", 0.0) if _config["copy_tp"] else 0.0

                if _config["risk_mode"] in ("FIXED", "FIXED_CONTRACTS", "FIXED_LOTS"):
                    lots = calculate_lots_fixed(_config["fixed_lots"])
                elif _config["risk_mode"] == "RISK_PERCENT":
                    if not sl:
                        logger.info(f"{display}: RISK_PERCENT sin SL, usando BALANCE_PROP")
                        slave_balance = _account_balance()
                        master_balance = payload.get("master_balance", 0)
                        lots = calculate_lots_balance_prop(payload.get("volume", 0.01), slave_balance, master_balance)
                    else:
                        info = get_account_info()
                        sym_info = mt5_helpers.get_symbol_info(symbol)
                        if info is None or sym_info is None:
                            logger.error(f"{display}: cannot get account/symbol info")
                            mark_pending_error(master_ticket, account_id)
                            continue
                        try:
                            tick_value = mt5_helpers.effective_tick_value(sym_info, account_currency=info.get("currency"))
                            lots = calculate_lots_risk_percent(
                                float(info.get("balance", 0) or 0), _config["risk_percent"],
                                entry_price, sl,
                                float(sym_info.get("trade_tick_size", 0) or 0),
                                tick_value,
                                float(sym_info.get("volume_min", 0.01) or 0.01),
                                float(sym_info.get("volume_step", 0.01) or 0.01),
                            )
                        except Exception as e:
                            logger.error(f"{display}: lot calc error: {e}")
                            mark_pending_error(master_ticket, account_id)
                            continue
                elif _config["risk_mode"] == "RISK_USD":
                    if not sl:
                        logger.info(f"{display}: RISK_USD sin SL, usando BALANCE_PROP")
                        slave_balance = _account_balance()
                        master_balance = payload.get("master_balance", 0)
                        lots = calculate_lots_balance_prop(payload.get("volume", 0.01), slave_balance, master_balance)
                    else:
                        sym_info = mt5_helpers.get_symbol_info(symbol)
                        if sym_info is None:
                            logger.error(f"{display}: no symbol_info for {symbol}")
                            mark_pending_error(master_ticket, account_id)
                            continue
                        acc_info_usd = get_account_info()
                        try:
                            tick_value = mt5_helpers.effective_tick_value(
                                sym_info, account_currency=acc_info_usd.get("currency") if acc_info_usd else None)
                            lots = calculate_lots_risk_usd(
                                _config["risk_usd"], entry_price, sl,
                                float(sym_info.get("trade_tick_size", 0) or 0),
                                tick_value,
                                float(sym_info.get("volume_min", 0.01) or 0.01),
                                float(sym_info.get("volume_step", 0.01) or 0.01),
                            )
                        except Exception as e:
                            logger.error(f"{display}: lot calc error: {e}")
                            mark_pending_error(master_ticket, account_id)
                            continue
                elif _config["risk_mode"] == "RATIO":
                    lots = calculate_lots_ratio(payload.get("volume", 0.01), _config["lot_multiplier"])
                elif _config["risk_mode"] == "BALANCE_PROP":
                    slave_balance = _account_balance()
                    master_balance = payload.get("master_balance", 0)
                    lots = calculate_lots_balance_prop(payload.get("volume", 0.01), slave_balance, master_balance)
                else:
                    lots = payload.get("volume", 0.01)

                if _config["max_lots"] > 0 and lots > _config["max_lots"]:
                    lots = _config["max_lots"]

                limit_hit = _check_daily_limits()
                if limit_hit:
                    limit_type, pnl_value = limit_hit
                    _pause_slave(f"{limit_type} diario alcanzado: ${pnl_value:.2f}")
                    continue

                logger.info(f"{display}: OPEN {symbol} {direction} {lots:.2f} lots (mode={_config['risk_mode']} sl={sl} tp={tp})")
                result = open_position(symbol, lots, direction, sl, tp, _config["magic_number"], filling=_force_filling)
                if result and result.get("ok"):
                    slave_ticket = int(result["position_id"])
                    confirm_open(master_ticket, account_id, str(slave_ticket))
                    _log_trade(master_account_id, account_id, TradeAction.OPEN, symbol, lots,
                               entry_price, sl, tp, TradeResult.SUCCESS,
                               master_ticket=master_ticket, slave_ticket=str(slave_ticket))
                    _emit_event(event_queue, "copy_ok", {"slave": display, "symbol": symbol, "action": "OPEN",
                                                         "volume": lots, "master_ticket": master_ticket,
                                                         "slave_ticket": slave_ticket})
                    logger.info(f"{display}: OPEN OK {symbol} {lots:.2f} lots ticket={slave_ticket}")
                else:
                    mark_pending_error(master_ticket, account_id)
                    _log_trade(master_account_id, account_id, TradeAction.OPEN, symbol, lots,
                               entry_price, sl, tp, TradeResult.FAILED,
                               master_ticket=master_ticket)
                    _emit_event(event_queue, "copy_error", {"slave": display, "symbol": symbol, "action": "OPEN",
                                                            "volume": lots, "master_ticket": master_ticket,
                                                            "error": (result or {}).get("error", "No response")})
                    logger.error(f"{display}: OPEN FAIL {symbol} {lots:.2f} lots | {(result or {}).get('error', 'no result')}")

            elif action == "CLOSE":
                master_ticket = payload["position_ticket"]
                slave_ticket = get_slave_ticket(master_ticket, account_id)
                if not slave_ticket:
                    logger.warning(f"{display}: no mapping for master_ticket={master_ticket}")
                    continue

                if _config["delay_sec"] > 0:
                    for _ in range(int(_config["delay_sec"] * 10)):
                        if stop_flag.is_set():
                            break
                        time.sleep(0.1)
                    if stop_flag.is_set():
                        break

                side = payload.get("side", "BUY")
                result = close_position(symbol, int(slave_ticket), side, magic=_config["magic_number"], filling=_force_filling)
                if result and result.get("ok"):
                    mark_closed(master_ticket, account_id)
                    _log_trade(master_account_id, account_id, TradeAction.CLOSE, symbol,
                               payload.get("volume", 0), 0, None, None, TradeResult.SUCCESS,
                               master_ticket=master_ticket, slave_ticket=str(slave_ticket))
                    _emit_event(event_queue, "copy_ok", {"slave": display, "symbol": symbol, "action": "CLOSE",
                                                         "master_ticket": master_ticket, "source": "hydrax"})
                    logger.info(f"{display}: CLOSE OK {symbol} [HydraX]")
                else:
                    _log_trade(master_account_id, account_id, TradeAction.CLOSE, symbol,
                               payload.get("volume", 0), 0, None, None, TradeResult.FAILED,
                               master_ticket=master_ticket, slave_ticket=str(slave_ticket))
                    _emit_event(event_queue, "copy_error", {"slave": display, "symbol": symbol, "action": "CLOSE",
                                                            "master_ticket": master_ticket,
                                                            "error": (result or {}).get("error", "No response")})
                    logger.error(f"{display}: CLOSE FAIL {symbol} | {(result or {}).get('error', 'no result')}")

            elif action == "MODIFY":
                if not _config["copy_modify"]:
                    continue
                master_ticket = payload["position_ticket"]
                slave_ticket = get_slave_ticket(master_ticket, account_id)
                if not slave_ticket:
                    continue

                if _config["delay_sec"] > 0:
                    for _ in range(int(_config["delay_sec"] * 10)):
                        if stop_flag.is_set():
                            break
                        time.sleep(0.1)
                    if stop_flag.is_set():
                        break

                new_sl = payload.get("new_sl", 0.0) if _config["copy_sl"] else 0.0
                new_tp = payload.get("new_tp", 0.0) if _config["copy_tp"] else 0.0
                result = modify_position(symbol, int(slave_ticket), new_sl, new_tp, _config["magic_number"])
                if result and result.get("ok"):
                    _log_trade(master_account_id, account_id, TradeAction.MODIFY, symbol, 0, 0,
                               new_sl, new_tp, TradeResult.SUCCESS,
                               master_ticket=master_ticket, slave_ticket=str(slave_ticket))
                    _emit_event(event_queue, "copy_ok", {"slave": display, "symbol": symbol, "action": "MODIFY"})
                    logger.info(f"{display}: MODIFY OK {symbol} SL={new_sl} TP={new_tp}")
                else:
                    _log_trade(master_account_id, account_id, TradeAction.MODIFY, symbol, 0, 0,
                               new_sl, new_tp, TradeResult.FAILED, master_ticket=master_ticket)
                    _emit_event(event_queue, "copy_error", {"slave": display, "symbol": symbol, "action": "MODIFY",
                                                            "master_ticket": master_ticket,
                                                            "error": (result or {}).get("error", "No response")})

    except Exception:
        logger.error(f"{display}: {traceback.format_exc()}")
    finally:
        disconnect_mt5()
        logger.info(f"{display}: worker stopped")