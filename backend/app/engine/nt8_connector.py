"""TCP connector al bridge C# de NinjaTrader 8."""
import socket
import json
import time
import threading
from app.utils.logger import get_logger

logger = get_logger("hydrax.nt8")


class NT8Connector:
    def __init__(self, host: str = "localhost", port: int = 5555):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def connect(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((self.host, self.port))
            s.close()
            return True
        except Exception:
            return False

    def disconnect(self):
        with self._lock:
            if self._sock:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

    def _ensure_connected(self) -> socket.socket | None:
        with self._lock:
            if self._sock is not None:
                return self._sock
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(10)
                self._sock.connect((self.host, self.port))
                return self._sock
            except Exception:
                self._sock = None
                return None

    def _send(self, data: dict) -> dict | None:
        for attempt in range(2):
            sock = self._ensure_connected()
            if sock is None:
                return None
            try:
                msg = json.dumps(data) + "\n"
                sock.sendall(msg.encode())
                response = b""
                while b"\n" not in response:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                if response:
                    return json.loads(response.decode("utf-8-sig").strip())
            except Exception as e:
                if attempt == 0:
                    logger.debug(f"NT8: retry after {e}")
                    with self._lock:
                        try:
                            self._sock.close()
                        except Exception:
                            pass
                        self._sock = None
                else:
                    logger.warning(f"NT8: {e}, reconnecting...")
        return None

    def get_account(self, account_name: str = "") -> dict | None:
        resp = self._send({"action": "ACCOUNT", "account": account_name})
        return resp

    def get_accounts(self) -> list[str]:
        resp = self._send({"action": "ACCOUNTS"})
        if resp and resp.get("ok"):
            return [str(x) for x in resp.get("accounts", [])]
        return []

    def get_positions(self, account_name: str = "") -> list[dict]:
        resp = self._send({"action": "POSITIONS", "account": account_name})
        if resp and resp.get("ok"):
            return resp.get("positions", [])
        return []

    def get_orders(self, account_name: str = "") -> list[dict]:
        resp = self._send({"action": "ORDERS", "account": account_name})
        if resp and resp.get("ok"):
            return resp.get("orders", [])
        return []

    def open_position(self, symbol: str, contracts: int, direction: str,
                      sl: float = 0, tp: float = 0, magic: int = 0,
                      comment: str = "", account: str = "") -> dict | None:
        return self._send({
            "action": "OPEN",
            "symbol": symbol,
            "contracts": contracts,
            "direction": direction,
            "sl": sl,
            "tp": tp,
            "magic": magic,
            "comment": comment,
            "account": account,
        })

    def close_position(self, position_id: str, symbol: str = "", account: str = "") -> dict | None:
        return self._send({
            "action": "CLOSE",
            "position_id": position_id,
            "symbol": symbol,
            "account": account,
        })

    def modify_position(self, symbol: str, sl: float = 0, tp: float = 0, magic: int = 0, account: str = "", position_id: str = "") -> dict | None:
        data = {
            "action": "MODIFY",
            "symbol": symbol,
            "sl": sl,
            "tp": tp,
            "magic": magic,
            "account": account,
        }
        if position_id:
            data["position_id"] = position_id
        return self._send(data)
