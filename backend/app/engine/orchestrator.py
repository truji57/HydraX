import asyncio
import json
import multiprocessing as mp
import threading
import time

from app.database import SessionLocal
from app.models.account import Account, SlaveConfig
from app.engine.master_monitor import master_monitor_worker
from app.engine.slave_executor import slave_worker
from app.utils.logger import get_logger

logger = get_logger("hydrax.orchestrator")

_copier_running = False
_copier_start_time: float | None = None
_active_masters = 0
_active_slaves = 0
_worker_status: dict[str, dict] = {}


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
    return {
        "running": _copier_running,
        "uptime_seconds": uptime,
        "active_masters": _active_masters,
        "active_slaves": _active_slaves,
        "workers": _worker_status.copy(),
    }


class CopierOrchestrator:
    def __init__(self):
        self._master_processes: list[mp.Process] = []
        self._slave_processes: dict[str, mp.Process] = {}
        self._slave_queues: dict[str, mp.Queue] = {}
        self._master_stop_flags: list[mp.Event] = []
        self._slave_stop_flags: dict[str, mp.Event] = {}
        self._event_queue: mp.Queue | None = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        with self._lock:
            if self._running:
                return {"ok": False, "message": "Already running"}

            self._running = True
            self._clear_state()
            self._event_queue = mp.Queue()

            db = SessionLocal()
            try:
                masters = db.query(Account).filter(Account.role == "MASTER", Account.active == True).all()
                slaves = db.query(Account).filter(Account.role == "SLAVE", Account.active == True).all()

                if not masters:
                    self._running = False
                    return {"ok": False, "message": "No hay cuentas master activas configuradas"}

                for slave in slaves:
                    config = db.query(SlaveConfig).filter(SlaveConfig.account_id == slave.id).first()
                    if not config:
                        continue

                    q = mp.Queue()
                    stop_flag = mp.Event()
                    self._slave_queues[slave.id] = q
                    self._slave_stop_flags[slave.id] = stop_flag

                    p = mp.Process(
                        target=slave_worker,
                        args=(
                            slave.id, slave.name, slave.login, slave.password,
                            slave.server, slave.terminal_path,
                            config.risk_mode.value if config.risk_mode else "RISK_PERCENT",
                            config.risk_percent or 0.5,
                            config.risk_usd or 50.0, config.fixed_lots or 0.01,
                            config.lot_multiplier or 1.0, config.max_lots or 100.0,
                            config.max_positions or 100,
                            config.autocopy_enable if config.autocopy_enable is not None else True,
                            config.copy_sl if config.copy_sl is not None else True,
                            config.copy_tp if config.copy_tp is not None else True,
                            config.inverse_copy or False, config.delay_sec or 0.0,
                            config.symbol_mode.value if config.symbol_mode else "ALL",
                            config.symbol_filter or [], config.order_comment or "",
                            config.magic_number or 0,
                            q, stop_flag, self._event_queue,
                        ),
                        name=f"slave-{slave.id}",
                    )
                    p.start()
                    self._slave_processes[slave.id] = p
                    _worker_status[f"slave:{slave.name}"] = {"pid": p.pid, "alive": p.is_alive(), "account_id": slave.id}
                    logger.info(f"Slave started: {slave.name} PID={p.pid}")

                for master in masters:
                    stop_flag = mp.Event()
                    self._master_stop_flags.append(stop_flag)

                    p = mp.Process(
                        target=master_monitor_worker,
                        args=(
                            master.id, master.name, master.login, master.password,
                            master.server, master.terminal_path,
                            master.poll_interval or 0.5,
                            self._slave_queues, stop_flag, self._event_queue,
                        ),
                        name=f"master-{master.id}",
                    )
                    p.start()
                    self._master_processes.append(p)
                    _worker_status[f"master:{master.name}"] = {"pid": p.pid, "alive": p.is_alive(), "account_id": master.id}
                    logger.info(f"Master started: {master.name} PID={p.pid}")

            finally:
                db.close()

            set_copier_state(True, len(masters), len(slaves))
            threading.Thread(target=self._broadcast_events, daemon=True).start()
            threading.Thread(target=self._monitor_workers, daemon=True).start()
            return {"ok": True, "message": f"Started: {len(masters)} masters, {len(slaves)} slaves"}

    def stop(self):
        with self._lock:
            if not self._running:
                return

            self._running = False
            logger.info("Stopping copier...")

            for flag in self._master_stop_flags:
                flag.set()
            for flag in self._slave_stop_flags.values():
                flag.set()

            for q in self._slave_queues.values():
                try:
                    q.put(None, timeout=0.1)
                except Exception:
                    pass

            start = time.time()
            timeout = 10
            while time.time() - start < timeout:
                all_dead = True
                for p in self._master_processes:
                    if p.is_alive():
                        all_dead = False
                        p.join(timeout=0.5)
                for p in self._slave_processes.values():
                    if p.is_alive():
                        all_dead = False
                        p.join(timeout=0.5)
                if all_dead:
                    break

            for p in self._master_processes:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=1)
                    if p.is_alive():
                        p.kill()

            for p in self._slave_processes.values():
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=1)
                    if p.is_alive():
                        p.kill()

            self._clear_state()
            _worker_status.clear()
            set_copier_state(False, 0, 0)
            logger.info("Copier stopped")

    def _clear_state(self):
        self._master_processes.clear()
        self._slave_processes.clear()
        self._slave_queues.clear()
        self._master_stop_flags.clear()
        self._slave_stop_flags.clear()
        self._event_queue = None

    def _broadcast_events(self):
        from app.ws.manager import manager as ws_manager
        while self._running:
            try:
                event = self._event_queue.get(timeout=1)
                if event is None:
                    continue
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(ws_manager.broadcast(event["type"], event.get("data", {})))
                    loop.close()
                except Exception:
                    pass
            except Exception:
                pass

    def _monitor_workers(self):
        while self._running:
            for key, proc in list(_worker_status.items()):
                alive = False
                for mp_proc in self._master_processes:
                    if mp_proc.pid == proc.get("pid"):
                        alive = mp_proc.is_alive()
                        break
                if not alive:
                    for mp_proc in self._slave_processes.values():
                        if mp_proc.pid == proc.get("pid"):
                            alive = mp_proc.is_alive()
                            break
                _worker_status[key] = {**proc, "alive": alive}
                if not alive:
                    logger.warning(f"Worker DOWN: {key} (PID={proc.get('pid')})")

            time.sleep(5)


_orchestrator: CopierOrchestrator | None = None


def get_orchestrator() -> CopierOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CopierOrchestrator()
    return _orchestrator
