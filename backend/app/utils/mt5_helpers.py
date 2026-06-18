import time
from typing import Optional

import MetaTrader5 as mt5

from app.config import settings


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


def mt5_available() -> bool:
    try:
        import MetaTrader5 as _mt5
        return True
    except ImportError:
        return False


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
