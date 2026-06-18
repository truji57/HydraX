import time
import multiprocessing as mp
from dataclasses import dataclass

import MetaTrader5 as mt5

from app.utils.logger import get_logger
from app.utils.crypto import decrypt_password

logger = get_logger("hydrax.master")


@dataclass
class PositionSnapshot:
    ticket: int
    symbol: str
    volume: float
    price_open: float
    sl: float
    tp: float
    type: int


def master_monitor_worker(
    account_id: str,
    name: str,
    login: int,
    password_enc: str,
    server: str,
    terminal_path: str,
    poll_interval: float,
    slave_queues: dict,
    stop_flag: mp.Event,
    event_queue: mp.Queue,
):
    display = name or f"master-{login}"

    if not mt5.initialize(path=terminal_path, timeout=10000):
        logger.error(f"{display}: init failed (timeout 10s): {mt5.last_error()}")
        return

    password = decrypt_password(password_enc)
    if not mt5.login(login=login, password=password, server=server):
        logger.error(f"{display}: login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    logger.info(f"{display}: connected to {server}")

    prev_positions: dict[int, PositionSnapshot] = {}
    for p in mt5.positions_get() or []:
        prev_positions[int(p.ticket)] = PositionSnapshot(
            ticket=int(p.ticket),
            symbol=p.symbol,
            volume=float(p.volume),
            price_open=float(p.price_open),
            sl=float(p.sl),
            tp=float(p.tp),
            type=int(p.type),
        )
        logger.info(f"{display}: ignoring existing position ticket={p.ticket}")

    prev_orders = {int(o.ticket) for o in (mt5.orders_get() or [])}
    for ot in prev_orders:
        logger.info(f"{display}: ignoring existing pending order ticket={ot}")

    try:
        while not stop_flag.is_set():
            positions = mt5.positions_get() or []
            cur_positions = {
                int(p.ticket): PositionSnapshot(
                    ticket=int(p.ticket),
                    symbol=p.symbol,
                    volume=float(p.volume),
                    price_open=float(p.price_open),
                    sl=float(p.sl),
                    tp=float(p.tp),
                    type=int(p.type),
                )
                for p in positions
            }

            for t, p in cur_positions.items():
                if t not in prev_positions:
                    direction = "BUY" if p.type == 0 else "SELL"
                    logger.info(f"{display}: new position ticket={p.ticket} {p.symbol} {direction} {p.volume} lots")
                    cmd = {
                        "action": "OPEN",
                        "payload": {
                            "symbol": p.symbol,
                            "side": direction,
                            "price": p.price_open,
                            "sl": p.sl,
                            "tp": p.tp,
                            "master_ticket": p.ticket,
                            "master_account_id": account_id,
                            "master_name": display,
                            "server_master": server,
                            "volume": p.volume,
                            "price_open": p.price_open,
                        },
                    }
                    for q in slave_queues.values():
                        if not stop_flag.is_set():
                            q.put(cmd)
                    try:
                        event_queue.put({
                            "type": "position_open",
                            "data": {
                                "master": display,
                                "symbol": p.symbol,
                                "direction": direction,
                                "volume": p.volume,
                                "ticket": p.ticket,
                            },
                        })
                    except Exception:
                        pass

            for t, p in prev_positions.items():
                if t not in cur_positions:
                    direction = "BUY" if p.type == 0 else "SELL"
                    logger.info(f"{display}: closed position ticket={p.ticket} {p.symbol}")
                    cmd = {
                        "action": "CLOSE",
                        "payload": {
                            "position_ticket": p.ticket,
                            "symbol": p.symbol,
                            "side": direction,
                            "volume": p.volume,
                            "master_account_id": account_id,
                            "server_master": server,
                        },
                    }
                    for q in slave_queues.values():
                        if not stop_flag.is_set():
                            q.put(cmd)
                    try:
                        event_queue.put({
                            "type": "position_close",
                            "data": {
                                "master": display,
                                "symbol": p.symbol,
                                "ticket": p.ticket,
                            },
                        })
                    except Exception:
                        pass

            for t, cur in cur_positions.items():
                if t in prev_positions:
                    prev = prev_positions[t]
                    if abs(prev.sl - cur.sl) > 1e-6 or abs(prev.tp - cur.tp) > 1e-6:
                        logger.info(
                            f"{display}: modify ticket={t} {cur.symbol} "
                            f"SL {prev.sl}->{cur.sl} TP {prev.tp}->{cur.tp}"
                        )
                        cmd = {
                            "action": "MODIFY",
                            "payload": {
                                "position_ticket": t,
                                "symbol": cur.symbol,
                                "new_sl": cur.sl,
                                "new_tp": cur.tp,
                                "master_account_id": account_id,
                                "server_master": server,
                            },
                        }
                        for q in slave_queues.values():
                            if not stop_flag.is_set():
                                q.put(cmd)
                        try:
                            event_queue.put({
                                "type": "position_modify",
                                "data": {
                                    "master": display,
                                    "symbol": cur.symbol,
                                    "ticket": t,
                                    "new_sl": cur.sl,
                                    "new_tp": cur.tp,
                                },
                            })
                        except Exception:
                            pass

            prev_positions = cur_positions

            cur_orders = {int(o.ticket) for o in (mt5.orders_get() or [])}
            for ot in cur_orders - prev_orders:
                order_info = next((o for o in (mt5.orders_get() or []) if int(o.ticket) == ot), None)
                if order_info:
                    otype = {0: "BUY_LIMIT", 1: "SELL_LIMIT", 2: "BUY_STOP", 3: "SELL_STOP", 4: "BUY_STOP_LIMIT", 5: "SELL_STOP_LIMIT"}.get(order_info.type, f"TYPE_{order_info.type}")
                    logger.info(f"{display}: new pending order ticket={ot} {order_info.symbol} {otype}")
                    try:
                        event_queue.put({
                            "type": "order_pending",
                            "data": {
                                "master": display,
                                "symbol": order_info.symbol,
                                "type": otype,
                                "volume": order_info.volume_current,
                                "price": order_info.price_open,
                                "ticket": ot,
                            },
                        })
                    except Exception:
                        pass
            for ot in prev_orders - cur_orders:
                logger.info(f"{display}: pending order removed ticket={ot}")
                try:
                    event_queue.put({
                        "type": "order_removed",
                        "data": {
                            "master": display,
                            "ticket": ot,
                        },
                    })
                except Exception:
                    pass
            prev_orders = cur_orders

            for _ in range(int(poll_interval * 10)):
                if stop_flag.is_set():
                    break
                time.sleep(0.1)

    except Exception as e:
        logger.error(f"{display}: error in monitor loop: {e}")
    finally:
        mt5.shutdown()
        logger.info(f"{display}: monitor stopped")
