import time
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5

from app.config import settings

FILLING_MODES = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
MAX_RETRIES = 5
RETRY_DELAY = 0.5


def connect_mt5(login: int, password: str, server: str, terminal_path: str) -> bool:
    if not mt5.initialize(path=terminal_path):
        return False

    authorized = mt5.login(login=login, password=password, server=server)
    return authorized


def disconnect_mt5():
    mt5.shutdown()


def get_account_info() -> Optional[dict]:
    info = mt5.account_info()
    if info is None:
        return None
    return info._asdict()


def get_positions(symbol: Optional[str] = None) -> list[dict]:
    positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions is None:
        return []
    return [p._asdict() for p in positions]


def get_symbol_info(symbol: str) -> Optional[dict]:
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    return info._asdict()


def get_symbol_tick(symbol: str) -> Optional[dict]:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    return tick._asdict()


def get_orders() -> list[dict]:
    orders = mt5.orders_get()
    if orders is None:
        return []
    return [o._asdict() for o in orders]


def get_history_deals_since(start: datetime) -> list[dict]:
    deals = mt5.history_deals_get(start, datetime.now())
    if deals is None:
        return []
    return [d._asdict() for d in deals]


def open_position(symbol: str, volume: float, side: str, sl: float = 0, tp: float = 0,
                  magic: int = 0, comment: str = "", deviation: int = 50) -> dict:
    order_type = mt5.ORDER_TYPE_BUY if side.upper() == "BUY" else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"ok": False, "error": f"no tick para {symbol}"}
    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    last_error = "todos los filling modes fallaron"
    for filling in FILLING_MODES:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "deviation": deviation,
            "magic": magic,
            "comment": comment or "",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        try:
            result = mt5.order_send(request)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if result is None:
            continue
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return {"ok": True, "position_id": int(result.order), "price": price}
        last_error = f"{result.comment or 'retcode'} (retcode {result.retcode})"

    return {"ok": False, "error": f"open fallo: {last_error}"}


def close_position(symbol: str, position: int, side: str, volume: Optional[float] = None,
                   magic: int = 0, comment: str = "", deviation: int = 50) -> dict:
    if volume is None:
        pos = next((p for p in (mt5.positions_get() or []) if int(p.ticket) == int(position)), None)
        if pos is None:
            return {"ok": False, "error": f"no existe posicion {position}"}
        volume = pos.volume

    close_type = mt5.ORDER_TYPE_SELL if side.upper() == "BUY" else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"ok": False, "error": f"no tick para {symbol}"}
    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    last_error = "intentos agotados"
    for attempt in range(1, MAX_RETRIES + 1):
        for filling in FILLING_MODES:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": close_type,
                "position": int(position),
                "price": price,
                "deviation": deviation,
                "magic": magic,
                "comment": comment or "",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            try:
                result = mt5.order_send(request)
            except Exception as e:
                return {"ok": False, "error": str(e)}
            if result is None:
                continue
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return {"ok": True, "retcode": result.retcode}
            last_error = result.comment or f"retcode {result.retcode}"
        time.sleep(RETRY_DELAY)

    return {"ok": False, "error": f"close fallo tras {MAX_RETRIES} intentos: {last_error}"}


def modify_position(symbol: str, position: int, sl: float = 0, tp: float = 0,
                    magic: int = 0, comment: str = "") -> dict:
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": int(position),
        "sl": float(sl) if sl else 0.0,
        "tp": float(tp) if tp else 0.0,
        "magic": magic,
        "comment": comment or "",
    }
    try:
        result = mt5.order_send(request)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if result is None:
        return {"ok": False, "error": "order_send devolvio None"}
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return {"ok": True}
    return {"ok": False, "error": result.comment or f"retcode {result.retcode}"}


def cancel_pending_orders() -> int:
    removed = 0
    for o in get_orders():
        try:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": int(o.get("ticket", 0)),
                "symbol": o.get("symbol", ""),
                "type_time": mt5.ORDER_TIME_GTC,
            }
            result = mt5.order_send(request)
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                removed += 1
        except Exception:
            pass
    return removed


def mt5_available() -> bool:
    try:
        import MetaTrader5 as _mt5
        return True
    except ImportError:
        return False


def get_last_error():
    try:
        return mt5.last_error()
    except Exception:
        return None


def effective_tick_value(symbol_info: dict) -> float:
    """Tick value por lote corregido.

    MT5 puede reportar trade_tick_value escalado (~10x menor en metales como
    XAUUSD, p. ej. 0.1 en vez de 1.0 con contract=100 y tick_size=0.01).
    El valor real derivado es contract_size * tick_size; usamos el maximo de
    ambos para no subestimar el riesgo.
    """
    try:
        reported = float(symbol_info.get("trade_tick_value") or 0)
        ts = float(symbol_info.get("trade_tick_size") or 0)
        contract = float(symbol_info.get("trade_contract_size") or 0)
        derived = contract * ts
        if reported > 0 and derived > reported:
            return derived
        return reported if reported > 0 else derived
    except Exception:
        return float(symbol_info.get("trade_tick_value") or 0)


def test_connection(login: int, password: str, server: str, terminal_path: str) -> dict:
    connected = connect_mt5(login, password, server, terminal_path)
    if not connected:
        error = mt5.last_error()
        disconnect_mt5()
        return {
            "success": False,
            "message": f"Connection failed: {error}",
            "balance": None,
            "equity": None,
            "server": None,
        }

    info = get_account_info()
    disconnect_mt5()

    if info is None:
        return {
            "success": False,
            "message": "Connected but could not retrieve account info",
            "balance": None,
            "equity": None,
            "server": None,
        }

    return {
        "success": True,
        "message": "Connection successful",
        "balance": info.get("balance"),
        "equity": info.get("equity"),
        "server": info.get("server"),
    }
