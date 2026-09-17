import time
import multiprocessing as mp
import threading
from collections import deque

from app.database import SessionLocal
from app.models.account import Account, SlaveConfig
from app.engine.nt8_worker import nt8_master_monitor, nt8_slave_executor
from app.engine.mt5_worker import mt5_master_monitor, mt5_slave_executor
from app.utils.logger import get_logger

logger = get_logger("hydrax.orchestrator")

_copier_running = False
_copier_start_time: float | None = None
_active_masters = 0
_active_slaves = 0
_worker_status: dict[str, dict] = {}

_last_nt8_heartbeat: float | None = None
_heartbeat_probe_started = False
_heartbeat_probe_lock = threading.Lock()

MT5_ACCOUNT_STATS: dict[str, dict] = {}

NT8_HB_TIMEOUT = 6.0  # segundos sin respuesta del bridge = desconectado

MAX_RESTARTS_PER_MINUTE = 3
RESTART_WINDOW_SECONDS = 60


def set_copier_state(running: bool, masters: int = 0, slaves: int = 0):
    global _copier_running, _active_masters, _active_slaves, _copier_start_time
    _copier_running = running
    _active_masters = masters
    _active_slaves = slaves
    _copier_start_time = time.time() if running else None


def get_copier_state():
    uptime = None
    if _copier_start_time:
        uptime = time.time() - _copier_start_time
    nt8_connected = _last_nt8_heartbeat is not None and (time.time() - _last_nt8_heartbeat) < NT8_HB_TIMEOUT
    mt5_connected = any(
        s.get("platform") == "MT5" and s.get("alive")
        for s in _worker_status.values()
    )
    return {
        "running": _copier_running,
        "uptime_seconds": uptime,
        "active_masters": _active_masters,
        "active_slaves": _active_slaves,
        "workers": _worker_status.copy(),
        "nt8_connected": nt8_connected,
        "nt8_last_heartbeat": _last_nt8_heartbeat,
        "mt5_connected": mt5_connected,
    }


def _nt8_heartbeat_probe():
    global _last_nt8_heartbeat
    from app.engine.nt8_connector import NT8Connector
    while True:
        try:
            db = SessionLocal()
            try:
                master = (db.query(Account)
                          .filter(Account.role == "MASTER", Account.active == True)
                          .order_by(Account.created_at.asc())
                          .first())
                if master:
                    conn = NT8Connector(master.bridge_host, master.bridge_port)
                    if conn.connect():
                        _last_nt8_heartbeat = time.time()
            finally:
                db.close()
        except Exception:
            pass
        time.sleep(3)


def _platform(account: Account) -> str:
    return (account.platform.value if account.platform else "NT8")


class CopierOrchestrator:
    def __init__(self):
        self._master_processes: dict[str, mp.Process] = {}
        self._slave_processes: dict[str, mp.Process] = {}
        self._slave_queues: dict[str, mp.Queue] = {}
        self._queues_by_platform: dict[str, dict] = {}
        self._master_stop_flags: dict[str, mp.Event] = {}
        self._slave_stop_flags: dict[str, mp.Event] = {}
        self._event_queue: mp.Queue | None = None
        self._running = False
        self._lock = threading.Lock()

        self._master_configs: dict[str, dict] = {}
        self._slave_configs: dict[str, dict] = {}
        self._restart_timestamps: dict[str, deque] = {}

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        with self._lock:
            if self._running:
                return {"ok": False, "message": "Already running"}

            self._running = True
            self._clear_state()
            MT5_ACCOUNT_STATS.clear()
            self._event_queue = mp.Queue()

            fixed = 0
            try:
                from app.engine.ticket_mapper import reconcile_stale_positions
                fixed = reconcile_stale_positions()
                if fixed:
                    logger.info(f"Auto-sync: {fixed} posiciones reconciliadas")
            except Exception:
                pass

            db = SessionLocal()
            try:
                masters = db.query(Account).filter(Account.role == "MASTER", Account.active == True).all()
                slaves = db.query(Account).filter(Account.role == "SLAVE", Account.active == True).all()

                if not masters:
                    self._running = False
                    return {"ok": False, "message": "No hay cuentas master activas"}

                nt8_masters = [m for m in masters if _platform(m) == "NT8"]
                mt5_masters = [m for m in masters if _platform(m) == "MT5"]

                if nt8_masters:
                    from app.engine.nt8_connector import NT8Connector
                    bridges_ok = False
                    failed_bridges = []
                    for master in nt8_masters:
                        conn = NT8Connector(master.bridge_host, master.bridge_port)
                        if conn.connect():
                            bridges_ok = True
                        else:
                            failed_bridges.append(f"{master.name} ({master.bridge_host}:{master.bridge_port})")
                        conn.disconnect()
                    if not bridges_ok and not mt5_masters:
                        self._running = False
                        return {"ok": False, "message": f"No se pudo conectar a NT8. Verifica que NT8 este abierto con el bridge. Fallos: {'; '.join(failed_bridges)}"}
                    if not bridges_ok:
                        logger.warning("NT8 bridge no disponible; se inician solo masters MT5")

                for slave in slaves:
                    config = db.query(SlaveConfig).filter(SlaveConfig.account_id == slave.id).first()
                    if not config:
                        continue

                    q = mp.Queue(maxsize=100)
                    stop_flag = mp.Event()
                    platform = _platform(slave)
                    self._slave_queues[slave.id] = q
                    self._slave_stop_flags[slave.id] = stop_flag
                    self._queues_by_platform.setdefault(platform, {})[slave.id] = q

                    slave_cfg = {
                        "account_id": slave.id, "name": slave.name, "login": slave.login,
                        "platform": platform,
                        "bridge_host": slave.bridge_host, "bridge_port": slave.bridge_port,
                        "server": slave.server, "terminal_path": slave.terminal_path,
                        "password": slave.password,
                        "risk_mode": config.risk_mode.value if config.risk_mode else "FIXED",
                        "risk_percent": config.risk_percent or 0.5, "risk_usd": config.risk_usd or 50.0,
                        "fixed_contracts": config.fixed_contracts or 1,
                        "fixed_lots": config.fixed_lots or 0.01,
                        "lot_multiplier": config.lot_multiplier or 1.0,
                        "max_contracts": config.max_contracts or 100,
                        "max_lots": config.max_lots or 10.0,
                        "max_positions": config.max_positions or 100,
                        "autocopy_enable": config.autocopy_enable if config.autocopy_enable is not None else True,
                        "copy_sl": config.copy_sl if config.copy_sl is not None else True,
                        "copy_tp": config.copy_tp if config.copy_tp is not None else True,
                        "inverse_copy": config.inverse_copy or False,
                        "copy_modify": config.copy_modify if config.copy_modify is not None else True,
                        "sync_close": config.sync_close if config.sync_close is not None else False,
                        "daily_loss_enabled": config.daily_loss_enabled if config.daily_loss_enabled else False,
                        "daily_loss_limit": config.daily_loss_limit or 0.0,
                        "daily_profit_enabled": config.daily_profit_enabled if config.daily_profit_enabled else False,
                        "daily_profit_limit": config.daily_profit_limit or 0.0,
                        "delay_sec": config.delay_sec or 0.0,
                        "magic_number": config.magic_number or 0,
                    }
                    self._slave_configs[slave.id] = slave_cfg

                    if platform == "MT5":
                        p = mp.Process(
                            target=mt5_slave_executor,
                            args=self._mt5_slave_args(slave_cfg, q, stop_flag),
                            name=f"slave-{slave.id}",
                        )
                    else:
                        p = mp.Process(
                            target=nt8_slave_executor,
                            args=self._nt8_slave_args(slave_cfg, q, stop_flag),
                            name=f"slave-{slave.id}",
                        )
                    p.start()
                    self._slave_processes[slave.id] = p
                    _worker_status[f"slave:{slave.name}"] = {
                        "pid": p.pid, "alive": p.is_alive(), "account_id": slave.id, "platform": platform,
                    }

                for master in masters:
                    stop_flag = mp.Event()
                    self._master_stop_flags[master.id] = stop_flag
                    platform = _platform(master)

                    master_cfg = {
                        "account_id": master.id, "name": master.name, "platform": platform,
                        "login": master.login,
                        "bridge_host": master.bridge_host, "bridge_port": master.bridge_port,
                        "server": master.server, "terminal_path": master.terminal_path,
                        "password": master.password,
                        "poll_interval": max(master.poll_interval or 0.5, 0.1),
                    }
                    self._master_configs[master.id] = master_cfg

                    if platform == "MT5":
                        target = mt5_master_monitor
                        args = (
                            master.id, master.name, int(self._safe_int(master.login)), master.password,
                            master.server or "", master.terminal_path or "",
                            master_cfg["poll_interval"],
                            self._queues_by_platform.get("MT5", {}), stop_flag, self._event_queue,
                        )
                    else:
                        target = nt8_master_monitor
                        args = (
                            master.id, master.name, master.bridge_host, master.bridge_port,
                            master.login, master_cfg["poll_interval"],
                            self._queues_by_platform.get("NT8", {}), stop_flag, self._event_queue,
                        )

                    p = mp.Process(target=target, args=args, name=f"master-{master.id}")
                    p.start()
                    self._master_processes[master.id] = p
                    _worker_status[f"master:{master.name}"] = {
                        "pid": p.pid, "alive": p.is_alive(), "account_id": master.id, "platform": platform,
                    }

            finally:
                db.close()

            set_copier_state(True, len(masters), len(slaves))
            threading.Thread(target=self._broadcast_events, daemon=True).start()
            threading.Thread(target=self._monitor_workers, daemon=True).start()
            return {"ok": True, "message": f"Started: {len(masters)} masters, {len(slaves)} slaves"}

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _nt8_slave_args(self, cfg: dict, q: mp.Queue, stop_flag: mp.Event):
        return (
            cfg["account_id"], cfg["name"], cfg["login"], cfg["bridge_host"], cfg["bridge_port"],
            cfg["risk_mode"], cfg["risk_percent"], cfg["risk_usd"],
            cfg["fixed_contracts"], cfg["lot_multiplier"],
            cfg["max_contracts"], cfg["max_positions"],
            cfg["autocopy_enable"], cfg["copy_sl"], cfg["copy_tp"],
            cfg["inverse_copy"], cfg["copy_modify"], cfg["sync_close"],
            cfg["daily_loss_enabled"], cfg["daily_loss_limit"],
            cfg["daily_profit_enabled"], cfg["daily_profit_limit"],
            cfg["delay_sec"], cfg["magic_number"],
            q, stop_flag, self._event_queue,
        )

    def _mt5_slave_args(self, cfg: dict, q: mp.Queue, stop_flag: mp.Event):
        return (
            cfg["account_id"], cfg["name"], self._safe_int(cfg["login"]),
            cfg["password"], cfg["server"] or "", cfg["terminal_path"] or "",
            cfg["risk_mode"], cfg["risk_percent"], cfg["risk_usd"],
            float(cfg.get("fixed_lots", 0.01) or 0.01),
            cfg["lot_multiplier"],
            float(cfg.get("max_lots", 10.0) or 10.0),
            cfg["max_positions"],
            cfg["autocopy_enable"], cfg["copy_sl"], cfg["copy_tp"],
            cfg["inverse_copy"], cfg["copy_modify"], cfg["sync_close"],
            cfg["daily_loss_enabled"], cfg["daily_loss_limit"],
            cfg["daily_profit_enabled"], cfg["daily_profit_limit"],
            cfg["delay_sec"], cfg["magic_number"],
            q, stop_flag, self._event_queue,
        )

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            for flag in self._master_stop_flags.values():
                flag.set()
            for flag in self._slave_stop_flags.values():
                flag.set()
            for q in self._slave_queues.values():
                try:
                    q.put(None, timeout=0.1)
                except Exception:
                    pass
            for p in self._master_processes.values():
                if p.is_alive():
                    p.join(timeout=2)
                    if p.is_alive():
                        p.terminate()
            for p in self._slave_processes.values():
                if p.is_alive():
                    p.join(timeout=2)
                    if p.is_alive():
                        p.terminate()
            self._clear_state()
            _worker_status.clear()
            MT5_ACCOUNT_STATS.clear()
            set_copier_state(False, 0, 0)

    def _clear_state(self):
        self._master_processes.clear()
        self._slave_processes.clear()
        self._slave_queues.clear()
        self._queues_by_platform.clear()
        self._master_stop_flags.clear()
        self._slave_stop_flags.clear()
        self._event_queue = None
        self._master_configs.clear()
        self._slave_configs.clear()
        self._restart_timestamps.clear()

    def _can_restart(self, account_id: str) -> bool:
        now = time.time()
        if account_id not in self._restart_timestamps:
            self._restart_timestamps[account_id] = deque()
        timestamps = self._restart_timestamps[account_id]
        while timestamps and now - timestamps[0] > RESTART_WINDOW_SECONDS:
            timestamps.popleft()
        if len(timestamps) >= MAX_RESTARTS_PER_MINUTE:
            return False
        timestamps.append(now)
        return True

    def _restart_master(self, account_id: str):
        cfg = self._master_configs.get(account_id)
        if not cfg:
            logger.error(f"Cannot restart master {account_id}: no config found")
            return

        if not self._can_restart(account_id):
            logger.error(f"Master {cfg.get('name', account_id)}: max restarts reached ({MAX_RESTARTS_PER_MINUTE}/min), giving up")
            return

        if not self._event_queue:
            logger.error(f"Cannot restart master {account_id}: event_queue is None")
            return

        logger.info(f"Restarting master: {cfg.get('name', account_id)} (attempt {len(self._restart_timestamps.get(account_id, deque()))})")

        stop_flag = mp.Event()
        self._master_stop_flags[account_id] = stop_flag

        try:
            if cfg.get("platform") == "MT5":
                target = mt5_master_monitor
                args = (
                    cfg["account_id"], cfg["name"], self._safe_int(cfg["login"]),
                    cfg["password"], cfg["server"] or "", cfg["terminal_path"] or "",
                    cfg["poll_interval"],
                    self._queues_by_platform.get("MT5", {}), stop_flag, self._event_queue,
                )
            else:
                target = nt8_master_monitor
                args = (
                    cfg["account_id"], cfg["name"], cfg["bridge_host"], cfg["bridge_port"],
                    cfg["login"], cfg["poll_interval"],
                    self._queues_by_platform.get("NT8", {}), stop_flag, self._event_queue,
                )
            p = mp.Process(target=target, args=args, name=f"master-{account_id}")
            p.start()
            self._master_processes[account_id] = p
            _worker_status[f"master:{cfg['name']}"] = {
                "pid": p.pid, "alive": p.is_alive(), "account_id": account_id,
                "platform": cfg.get("platform", "NT8"),
            }
            logger.info(f"Master restarted: {cfg.get('name', account_id)} PID={p.pid}")
        except Exception as e:
            logger.error(f"Failed to restart master {account_id}: {e}")

    def _restart_slave(self, account_id: str):
        cfg = self._slave_configs.get(account_id)
        if not cfg:
            logger.error(f"Cannot restart slave {account_id}: no config found")
            return

        if not self._can_restart(account_id):
            logger.error(f"Slave {cfg.get('name', account_id)}: max restarts reached ({MAX_RESTARTS_PER_MINUTE}/min), giving up")
            return

        if not self._event_queue:
            logger.error(f"Cannot restart slave {account_id}: event_queue is None")
            return

        logger.info(f"Restarting slave: {cfg.get('name', account_id)} (attempt {len(self._restart_timestamps.get(account_id, deque()))})")

        q = mp.Queue(maxsize=100)
        stop_flag = mp.Event()

        if account_id in self._slave_queues:
            old_q = self._slave_queues[account_id]
            try:
                old_q.close()
                old_q.join_thread()
            except Exception:
                pass

        platform = cfg.get("platform", "NT8")
        self._slave_queues[account_id] = q
        self._queues_by_platform.setdefault(platform, {})[account_id] = q
        self._slave_stop_flags[account_id] = stop_flag

        try:
            if platform == "MT5":
                target = mt5_slave_executor
                args = self._mt5_slave_args(cfg, q, stop_flag)
            else:
                target = nt8_slave_executor
                args = self._nt8_slave_args(cfg, q, stop_flag)
            p = mp.Process(target=target, args=args, name=f"slave-{account_id}")
            p.start()
            self._slave_processes[account_id] = p
            _worker_status[f"slave:{cfg['name']}"] = {
                "pid": p.pid, "alive": p.is_alive(), "account_id": account_id, "platform": platform,
            }
            logger.info(f"Slave restarted: {cfg.get('name', account_id)} PID={p.pid}")
        except Exception as e:
            logger.error(f"Failed to restart slave {account_id}: {e}")

    def _broadcast_events(self):
        import asyncio
        from app.ws.manager import manager as ws_manager
        from app.models.event_log import EventLog
        from app.database import SessionLocal
        loop = asyncio.new_event_loop()
        while self._running:
            try:
                event = self._event_queue.get(timeout=1)
                if event is None:
                    continue
                # Stats internas de cuentas MT5: se cachean (solo RUNNING), no se persisten ni se emiten
                if event["type"] == "mt5_account_stats":
                    data = event.get("data", {})
                    if self._running and data.get("account_id"):
                        MT5_ACCOUNT_STATS[data["account_id"]] = data
                    continue
                try:
                    db = SessionLocal()
                    try:
                        db.add(EventLog(type=event["type"], data=event.get("data", {})))
                        db.commit()
                        EventLog_MAX = 5000
                        old_ids = [r.id for r in db.query(EventLog.id)
                                   .order_by(EventLog.timestamp.desc())
                                   .offset(EventLog_MAX).all()]
                        if old_ids:
                            db.query(EventLog).filter(EventLog.id.in_(old_ids)).delete(synchronize_session=False)
                            db.commit()
                    finally:
                        db.close()
                except Exception:
                    pass
                try:
                    loop.run_until_complete(ws_manager.broadcast(event["type"], event.get("data", {})))
                except Exception:
                    pass
            except Exception:
                pass
        loop.close()

    def _check_workers_alive(self):
        dead_masters = []
        dead_slaves = []

        for mid, p in list(self._master_processes.items()):
            alive = p.is_alive()
            for key, status in list(_worker_status.items()):
                if status.get("account_id") == mid:
                    _worker_status[key] = {**status, "alive": alive}
                    if not alive:
                        dead_masters.append(mid)
                    break

        for sid, p in list(self._slave_processes.items()):
            alive = p.is_alive()
            for key, status in list(_worker_status.items()):
                if status.get("account_id") == sid:
                    _worker_status[key] = {**status, "alive": alive}
                    if not alive:
                        dead_slaves.append(sid)
                    break

        return dead_masters, dead_slaves

    def _monitor_workers(self):
        while self._running:
            dead_masters, dead_slaves = self._check_workers_alive()

            with self._lock:
                if not self._running:
                    break
                for mid in dead_masters:
                    logger.warning(f"Worker DOWN: master:{mid}")
                    if mid in self._master_processes:
                        old_proc = self._master_processes.pop(mid, None)
                        if old_proc and old_proc.is_alive():
                            self._master_processes[mid] = old_proc
                            continue
                        old_flag = self._master_stop_flags.pop(mid, None)
                        if old_proc:
                            try:
                                old_proc.join(timeout=1)
                            except Exception:
                                pass
                    self._restart_master(mid)

                for sid in dead_slaves:
                    logger.warning(f"Worker DOWN: slave:{sid}")
                    if sid in self._slave_processes:
                        old_proc = self._slave_processes.pop(sid, None)
                        if old_proc and old_proc.is_alive():
                            self._slave_processes[sid] = old_proc
                            continue
                        if old_proc:
                            try:
                                old_proc.join(timeout=1)
                            except Exception:
                                pass
                    self._restart_slave(sid)

            time.sleep(5)


_orchestrator: CopierOrchestrator | None = None
_orch_lock = threading.Lock()


def get_orchestrator() -> CopierOrchestrator:
    global _orchestrator, _heartbeat_probe_started
    with _orch_lock:
        if _orchestrator is None:
            _orchestrator = CopierOrchestrator()
        if not _heartbeat_probe_started:
            _heartbeat_probe_started = True
            threading.Thread(target=_nt8_heartbeat_probe, daemon=True).start()
        return _orchestrator