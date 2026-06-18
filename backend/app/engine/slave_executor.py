import time
import traceback
import multiprocessing as mp
from datetime import datetime

import MetaTrader5 as mt5

from app.database import SessionLocal
from app.models.account import SlaveConfig
from app.models.trade_log import TradeLog, TradeAction, TradeResult
from app.engine.risk_calculator import (
    calculate_lots_fixed,
    calculate_lots_risk_percent,
    calculate_lots_risk_usd,
    calculate_lots_ratio,
    calculate_lots_balance_prop,
)
from app.engine.symbol_translator import translate_symbol
from app.engine.ticket_mapper import (
    reserve_pending,
    confirm_open,
    mark_pending_error,
    mark_closed,
    get_slave_ticket,
)
from app.engine.command_router import is_slave_linked_to_master
from app.utils.logger import get_logger
from app.utils.crypto import decrypt_password

logger = get_logger("hydrax.slave")

FILLING_MODES = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
MAX_RETRIES = 5
RETRY_DELAY = 0.5
EPS = 1e-6


def _log_trade(master_id: str | None, slave_id: str, action: TradeAction, symbol: str,
               volume: float, price: float, sl: float | None, tp: float | None,
               result: TradeResult, master_ticket: int | None = None,
               slave_ticket: int | None = None,
               error_code: int | None = None, error_msg: str | None = None):
    try:
        db = SessionLocal()
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
        db.close()
    except Exception:
        pass


def _emit_event(event_queue, event_type: str, data: dict):
    if event_queue is not None:
        try:
            event_queue.put({"type": event_type, "data": data})
        except Exception:
            pass


def _open_position(display: str, symbol: str, side: str, price: float, sl: float,
                   tp: float, lots: float, order_comment: str, magic: int = 0) -> int | None:
    order_type = mt5.ORDER_TYPE_BUY if side.upper() == "BUY" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"{display}: no tick for {symbol}")
        return None
    price_exec = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    for filling in FILLING_MODES:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lots),
            "type": order_type,
            "price": price_exec,
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "deviation": 20,
            "magic": 0,
            "comment": order_comment or "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        logger.info(f"{display}: OPEN {symbol} {lots:.2f} lots SL={sl} TP={tp} filling={filling}")
        result = mt5.order_send(request)

        if result is None:
            logger.error(f"{display}: order_send returned None filling={filling}")
            continue

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"{display}: OPEN success slave_ticket={result.order}")
            return result.order
        else:
            logger.warning(f"{display}: OPEN failed {symbol} filling={filling} retcode={result.retcode}")

    logger.error(f"{display}: OPEN failed for {symbol} with all filling modes")
    return None


def _close_position(display: str, symbol: str, side: str, slave_ticket: int,
                    order_comment: str, magic: int = 0) -> bool:
    close_type = mt5.ORDER_TYPE_SELL if side.upper() == "BUY" else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"{display}: no tick for {symbol}")
        return False
    price_close = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    pos = next((p for p in mt5.positions_get() or [] if p.ticket == slave_ticket), None)
    if pos is None:
        logger.warning(f"{display}: no slave position with ticket {slave_ticket}")
        return False
    volume = pos.volume

    for attempt in range(1, MAX_RETRIES + 1):
        for filling in FILLING_MODES:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": close_type,
                "position": int(slave_ticket),
                "price": price_close,
                "deviation": 20,
            "magic": magic,
                "comment": order_comment or "",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }

            logger.info(f"{display}: CLOSE attempt={attempt} ticket={slave_ticket} filling={filling}")
            result = mt5.order_send(request)

            if result is None:
                logger.error(f"{display}: order_send returned None filling={filling}")
                continue

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"{display}: CLOSE success ticket={slave_ticket}")
                return True
            else:
                logger.warning(f"{display}: CLOSE failed retcode={result.retcode}")

        time.sleep(RETRY_DELAY)

    logger.error(f"{display}: CLOSE failed after {MAX_RETRIES} attempts ticket={slave_ticket}")
    return False


def _modify_position(display: str, symbol: str, slave_ticket: int, new_sl: float,
                     new_tp: float, magic: int = 0) -> bool:
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": int(slave_ticket),
        "sl": float(new_sl) if new_sl else 0.0,
        "tp": float(new_tp) if new_tp else 0.0,
        "magic": magic,
        "comment": "",
    }

    logger.info(f"{display}: MODIFY ticket={slave_ticket} SL={new_sl} TP={new_tp}")
    result = mt5.order_send(request)

    if result is None:
        logger.error(f"{display}: MODIFY order_send returned None")
        return False

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"{display}: MODIFY success ticket={slave_ticket}")
        return True
    else:
        logger.error(f"{display}: MODIFY failed retcode={result.retcode}")
        return False


def slave_worker(
    account_id: str,
    name: str,
    login: int,
    password_enc: str,
    server: str,
    terminal_path: str,
    risk_mode: str,
    risk_percent: float,
    risk_usd: float,
    fixed_lots: float,
    lot_multiplier: float,
    max_lots: float,
    max_positions: int,
    autocopy_enable: bool,
    copy_sl: bool,
    copy_tp: bool,
    inverse_copy: bool,
    delay_sec: float,
    symbol_mode: str,
    symbol_filter: list,
    order_comment: str,
    magic_number: int,
    queue: mp.Queue,
    stop_flag: mp.Event,
    event_queue: mp.Queue = None,
):
    display = name or f"slave-{login}"

    try:
        if not autocopy_enable:
            logger.info(f"{display}: autocopy disabled, worker not starting")
            return

        if not mt5.initialize(path=terminal_path, timeout=10000):
            logger.error(f"{display}: init failed (timeout 10s): {mt5.last_error()}")
            return

        password = decrypt_password(password_enc)
        if not mt5.login(login=login, password=password, server=server):
            logger.error(f"{display}: login failed: {mt5.last_error()}")
            mt5.shutdown()
            return

        logger.info(f"{display}: connected to {server}")

        _config = {
            "risk_mode": risk_mode, "risk_percent": risk_percent, "risk_usd": risk_usd,
            "fixed_lots": fixed_lots, "lot_multiplier": lot_multiplier,
            "max_lots": max_lots, "max_positions": max_positions,
            "autocopy_enable": autocopy_enable, "copy_sl": copy_sl,
            "copy_tp": copy_tp, "inverse_copy": inverse_copy,
            "delay_sec": delay_sec, "symbol_mode": symbol_mode,
            "symbol_filter": symbol_filter, "order_comment": order_comment,
            "magic_number": magic_number,
        }

        def reload_config():
            try:
                db = SessionLocal()
                cfg = db.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
                db.close()
                if cfg:
                    _config["risk_mode"] = cfg.risk_mode.value if cfg.risk_mode else "RISK_PERCENT"
                    _config["risk_percent"] = cfg.risk_percent or 0.5
                    _config["risk_usd"] = cfg.risk_usd or 50.0
                    _config["fixed_lots"] = cfg.fixed_lots or 0.01
                    _config["lot_multiplier"] = cfg.lot_multiplier or 1.0
                    _config["max_lots"] = cfg.max_lots or 100.0
                    _config["max_positions"] = cfg.max_positions or 100
                    _config["autocopy_enable"] = cfg.autocopy_enable if cfg.autocopy_enable is not None else True
                    _config["copy_sl"] = cfg.copy_sl if cfg.copy_sl is not None else True
                    _config["copy_tp"] = cfg.copy_tp if cfg.copy_tp is not None else True
                    _config["inverse_copy"] = cfg.inverse_copy or False
                    _config["delay_sec"] = cfg.delay_sec or 0.0
                    _config["symbol_mode"] = cfg.symbol_mode.value if cfg.symbol_mode else "ALL"
                    _config["symbol_filter"] = cfg.symbol_filter or []
                    _config["order_comment"] = cfg.order_comment or ""
                    _config["magic_number"] = cfg.magic_number or 0
            except Exception:
                pass

        while not stop_flag.is_set():
            cmd = None
            try:
                cmd = queue.get(timeout=0.5)
            except Exception:
                pass

            if cmd is None:
                continue
            if stop_flag.is_set():
                break

            reload_config()

            if not _config["autocopy_enable"]:
                continue

            action = cmd.get("action")
            payload = cmd.get("payload", {})
            master_account_id = payload.get("master_account_id")

            if master_account_id and not is_slave_linked_to_master(account_id, master_account_id):
                continue

            from_server = payload.get("server_master", "")
            sym_master = payload.get("symbol", "")

            symbol = translate_symbol(sym_master, from_server, server)
            if symbol is None:
                logger.warning(f"{display}: no translation for {sym_master} ({from_server} -> {server})")
                continue

            if _config["symbol_mode"] == "WHITELIST" and _config["symbol_filter"] and sym_master not in _config["symbol_filter"]:
                continue
            if _config["symbol_mode"] == "BLACKLIST" and _config["symbol_filter"] and sym_master in _config["symbol_filter"]:
                continue

            if action == "OPEN":
                master_ticket = payload["master_ticket"]
                direction = payload["side"]

                if _config["inverse_copy"]:
                    direction = "SELL" if direction.upper() == "BUY" else "BUY"

                existing = get_slave_ticket(master_ticket, account_id)
                if existing is not None:
                    logger.warning(f"{display}: duplicate prevented master_ticket={master_ticket}")
                    continue

                reserve_pending(
                    master_ticket, master_account_id, account_id,
                    symbol, payload.get("volume", 0), payload.get("price_open", 0),
                    direction,
                )

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

                if _config["risk_mode"] == "FIXED":
                    lots = calculate_lots_fixed(_config["fixed_lots"])
                elif _config["risk_mode"] == "RISK_PERCENT":
                    acc_info = mt5.account_info()
                    if acc_info is None:
                        logger.error(f"{display}: cannot get account info")
                        mark_pending_error(master_ticket, account_id)
                        continue
                    sym_info = mt5.symbol_info(symbol)
                    if sym_info is None:
                        logger.error(f"{display}: no symbol_info for {symbol}")
                        mark_pending_error(master_ticket, account_id)
                        continue
                    try:
                        lots = calculate_lots_risk_percent(
                            acc_info.balance, _config["risk_percent"], entry_price, sl,
                            sym_info.trade_tick_size, sym_info.trade_tick_value,
                            sym_info.volume_min, sym_info.volume_step or 0.01,
                        )
                    except Exception as e:
                        logger.error(f"{display}: lot calc error: {e}")
                        mark_pending_error(master_ticket, account_id)
                        continue
                elif _config["risk_mode"] == "RISK_USD":
                    sym_info = mt5.symbol_info(symbol)
                    if sym_info is None:
                        logger.error(f"{display}: no symbol_info for {symbol}")
                        mark_pending_error(master_ticket, account_id)
                        continue
                    try:
                        lots = calculate_lots_risk_usd(
                            _config["risk_usd"], entry_price, sl,
                            sym_info.trade_tick_size, sym_info.trade_tick_value,
                            sym_info.volume_min, sym_info.volume_step or 0.01,
                        )
                    except Exception as e:
                        logger.error(f"{display}: lot calc error: {e}")
                        mark_pending_error(master_ticket, account_id)
                        continue
                elif _config["risk_mode"] == "RATIO":
                    master_lots = payload.get("volume", 0.01)
                    lots = calculate_lots_ratio(master_lots, _config["lot_multiplier"])
                elif _config["risk_mode"] == "BALANCE_PROP":
                    acc_info = mt5.account_info()
                    master_balance = payload.get("master_balance", 0)
                    if acc_info and master_balance > 0:
                        master_lots = payload.get("volume", 0.01)
                        lots = calculate_lots_balance_prop(master_lots, acc_info.balance, master_balance)
                    else:
                        lots = payload.get("volume", 0.01)
                else:
                    lots = payload.get("volume", 0.01)

                if _config["max_lots"] > 0 and lots > _config["max_lots"]:
                    logger.warning(f"{display}: lots {lots:.2f} capped to max_lots {_config['max_lots']:.2f}")
                    lots = _config["max_lots"]

                slave_ticket = _open_position(display, symbol, direction, entry_price, sl, tp, lots, _config["order_comment"], _config["magic_number"])

                if slave_ticket:
                    confirm_open(master_ticket, account_id, slave_ticket)
                    _log_trade(master_account_id, account_id, TradeAction.OPEN, symbol, lots,
                               entry_price, sl, tp, TradeResult.SUCCESS,
                               master_ticket=master_ticket, slave_ticket=slave_ticket)
                    _emit_event(event_queue, "copy_ok", {
                        "slave": display, "symbol": symbol, "action": "OPEN",
                        "volume": lots, "slave_ticket": slave_ticket, "master_ticket": master_ticket,
                    })
                else:
                    mark_pending_error(master_ticket, account_id)
                    _log_trade(master_account_id, account_id, TradeAction.OPEN, symbol, lots,
                               entry_price, sl, tp, TradeResult.FAILED,
                               master_ticket=master_ticket)
                    _emit_event(event_queue, "copy_error", {
                        "slave": display, "symbol": symbol, "action": "OPEN",
                        "volume": lots, "master_ticket": master_ticket,
                        "error": "OPEN failed after all filling modes",
                    })

            elif action == "CLOSE":
                master_ticket = payload["position_ticket"]

                if _config["delay_sec"] > 0:
                    for _ in range(int(_config["delay_sec"] * 10)):
                        if stop_flag.is_set():
                            break
                        time.sleep(0.1)
                    if stop_flag.is_set():
                        break

                slave_ticket = get_slave_ticket(master_ticket, account_id)
                if not slave_ticket:
                    logger.warning(f"{display}: no mapping for master_ticket={master_ticket}")
                    continue

                side = payload.get("side", "BUY")
                ok = _close_position(display, symbol, side, slave_ticket, _config["order_comment"], _config["magic_number"])

                if ok:
                    mark_closed(master_ticket, account_id)
                    _log_trade(master_account_id, account_id, TradeAction.CLOSE, symbol,
                               payload.get("volume", 0), 0, None, None, TradeResult.SUCCESS,
                               master_ticket=master_ticket, slave_ticket=slave_ticket)
                    _emit_event(event_queue, "copy_ok", {
                        "slave": display, "symbol": symbol, "action": "CLOSE",
                        "slave_ticket": slave_ticket, "master_ticket": master_ticket,
                    })
                else:
                    _log_trade(master_account_id, account_id, TradeAction.CLOSE, symbol,
                               payload.get("volume", 0), 0, None, None, TradeResult.FAILED,
                               master_ticket=master_ticket, slave_ticket=slave_ticket)
                    _emit_event(event_queue, "copy_error", {
                        "slave": display, "symbol": symbol, "action": "CLOSE",
                        "slave_ticket": slave_ticket, "master_ticket": master_ticket,
                        "error": "CLOSE failed after retries",
                    })

            elif action == "MODIFY":
                master_ticket = payload["position_ticket"]

                if _config["delay_sec"] > 0:
                    for _ in range(int(_config["delay_sec"] * 10)):
                        if stop_flag.is_set():
                            break
                        time.sleep(0.1)
                    if stop_flag.is_set():
                        break

                slave_ticket = get_slave_ticket(master_ticket, account_id)
                if not slave_ticket:
                    logger.warning(f"{display}: no mapping for master_ticket={master_ticket}")
                    continue

                new_sl = payload.get("new_sl", 0.0) if _config["copy_sl"] else None
                new_tp = payload.get("new_tp", 0.0) if _config["copy_tp"] else None
                if new_sl is None and new_tp is None:
                    continue
                if _modify_position(display, symbol, slave_ticket, new_sl or 0.0, new_tp or 0.0, _config["magic_number"]):
                    _log_trade(master_account_id, account_id, TradeAction.MODIFY, symbol,
                               0, 0, new_sl or 0.0, new_tp or 0.0, TradeResult.SUCCESS,
                               master_ticket=master_ticket, slave_ticket=slave_ticket)
                    _emit_event(event_queue, "copy_ok", {
                        "slave": display, "symbol": symbol, "action": "MODIFY",
                        "slave_ticket": slave_ticket, "master_ticket": master_ticket,
                        "new_sl": new_sl, "new_tp": new_tp,
                    })
                else:
                    _log_trade(master_account_id, account_id, TradeAction.MODIFY, symbol,
                               0, 0, new_sl or 0.0, new_tp or 0.0, TradeResult.FAILED,
                               master_ticket=master_ticket, slave_ticket=slave_ticket)
                    _emit_event(event_queue, "copy_error", {
                        "slave": display, "symbol": symbol, "action": "MODIFY",
                        "slave_ticket": slave_ticket, "master_ticket": master_ticket,
                        "error": "MODIFY failed",
                    })

    except Exception:
        logger.error(f"{display}: {traceback.format_exc()}")
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
        logger.info(f"{display}: worker stopped")
