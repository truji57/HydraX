from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.account import Account
from app.utils.events import record_event
from app.schemas.account import (
    AccountCreate, AccountUpdate, AccountResponse, SlaveConfigUpdate,
    SlaveConfigResponse, SlaveMasterLinkRequest, AccountTestResult,
)
from app.services.account_service import (
    get_accounts, get_account, create_account, update_account, delete_account,
    get_slave_config, update_slave_config, get_slave_masters, update_slave_masters,
    get_master_slaves,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
def list_accounts(role: str | None = None, db: Session = Depends(get_db)):
    return get_accounts(db, role=role)


@router.get("/nt8-available")
def nt8_available(host: str = "localhost", port: int = 5555):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.engine.nt8_connector import NT8Connector

    conn = NT8Connector(host, port)
    names = conn.get_accounts()
    if not names:
        return {"ok": True, "accounts": []}

    def active(name: str) -> bool:
        try:
            c = NT8Connector(host, port)
            info = c.get_account(name)
            c.disconnect()
            if info and info.get("ok"):
                balance = float(info.get("balance", 0) or 0)
                positions = int(info.get("positions", 0) or 0)
                realized = float(info.get("realized", 0) or 0)
                unrealized = float(info.get("unrealized", 0) or 0)
                if balance == 0 and positions == 0 and realized == 0 and unrealized == 0:
                    return False
            return True
        except Exception:
            return True

    processed = set()
    active_names = []
    with ThreadPoolExecutor(max_workers=min(len(names), 8)) as executor:
        futures = {executor.submit(active, n): n for n in names}
        try:
            for future in as_completed(futures, timeout=15):
                name = futures[future]
                processed.add(name)
                try:
                    if future.result(timeout=8):
                        active_names.append(name)
                except Exception:
                    active_names.append(name)
        except Exception:
            pass

    final = [n for n in names if n in active_names or n not in processed]
    return {"ok": True, "accounts": final}


@router.post("", response_model=AccountResponse, status_code=201)
def create(account: AccountCreate, db: Session = Depends(get_db)):
    acc = create_account(db, account)
    record_event(db, "account_created", {
        "name": acc.name, "role": acc.role.value,
        "platform": (acc.platform.value if acc.platform else "NT8"),
        "login": acc.login, "server": acc.server,
    })
    return acc


@router.get("/{account_id}", response_model=AccountResponse)
def get_one(account_id: str, db: Session = Depends(get_db)):
    acc = get_account(db, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


@router.put("/{account_id}", response_model=AccountResponse)
def update(account_id: str, account: AccountUpdate, db: Session = Depends(get_db)):
    acc = update_account(db, account_id, account)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    record_event(db, "account_updated", {
        "name": acc.name, "role": acc.role.value,
        "platform": (acc.platform.value if acc.platform else "NT8"),
        "login": acc.login,
    })
    return acc


@router.delete("/{account_id}", status_code=204)
def delete(account_id: str, db: Session = Depends(get_db)):
    acc = get_account(db, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    name = acc.name
    if not delete_account(db, account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    record_event(db, "account_deleted", {"name": name})


@router.post("/{account_id}/test", response_model=AccountTestResult)
def test_account(account_id: str, db: Session = Depends(get_db)):
    acc = get_account(db, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if acc.platform and acc.platform.value == "MT5":
        return _test_mt5(acc)
    return _test_nt8(acc)


def _test_nt8(acc) -> AccountTestResult:
    try:
        import socket, json
        s = socket.socket()
        s.settimeout(3)
        s.connect((acc.bridge_host, acc.bridge_port))
        s.sendall(json.dumps({"action": "ACCOUNT", "account": acc.login}).encode() + b"\n")
        resp = b""
        while b"\n" not in resp:
            chunk = s.recv(4096)
            if not chunk: break
            resp += chunk
        s.close()
        text = resp.decode("utf-8-sig").strip()
        data = json.loads(text)
        if data.get("ok"):
            msg = f"{data.get('name', acc.name)} - Balance: {data.get('balance', '?')} | {data.get('positions', 0)} posiciones"
            return AccountTestResult(success=True, message=msg, balance=data.get("balance"), server=f"{acc.bridge_host}:{acc.bridge_port}")
        return AccountTestResult(success=False, message=data.get("error", "Respuesta inesperada"), server=f"{acc.bridge_host}:{acc.bridge_port}")
    except Exception as e:
        return AccountTestResult(success=False, message=f"No se pudo conectar al bridge: {e}", server=f"{acc.bridge_host}:{acc.bridge_port}")


def _test_mt5(acc) -> AccountTestResult:
    try:
        import MetaTrader5  # noqa: F401
        from app.utils.mt5_helpers import test_connection
        from app.utils.crypto import decrypt_password
    except ImportError:
        return AccountTestResult(
            success=False,
            message="Paquete MetaTrader5 no instalado. Ejecuta: pip install MetaTrader5",
            server=acc.server,
        )

    password = ""
    try:
        password = decrypt_password(acc.password) if acc.password else ""
    except Exception:
        password = ""

    try:
        result = test_connection(int(acc.login or 0), password, acc.server or "", acc.terminal_path or "")
    except Exception as e:
        return AccountTestResult(success=False, message=f"Error en conexion MT5: {e}", server=acc.server)

    if result.get("success"):
        return AccountTestResult(
            success=True,
            message=f"{acc.name} - Balance: {result.get('balance', '?')} | Equity: {result.get('equity', '?')}",
            balance=result.get("balance"),
            server=result.get("server") or acc.server,
        )
    return AccountTestResult(success=False, message=result.get("message", "Fallo de conexion"), server=acc.server)


@router.get("/slaves/{account_id}/config", response_model=SlaveConfigResponse)
def get_config(account_id: str, db: Session = Depends(get_db)):
    config = get_slave_config(db, account_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.put("/slaves/{account_id}/config", response_model=SlaveConfigResponse)
def update_config(account_id: str, config: SlaveConfigUpdate, db: Session = Depends(get_db)):
    result = update_slave_config(db, account_id, config)
    acc = db.query(Account).filter(Account.id == account_id).first()
    record_event(db, "slave_config_updated", {
        "name": acc.name if acc else account_id,
        "account_id": account_id,
    })
    return result


@router.get("/slaves/{slave_id}/masters", response_model=list[dict])
def list_slave_masters(slave_id: str, db: Session = Depends(get_db)):
    masters = get_slave_masters(db, slave_id)
    return [{"slave_id": slave_id, "master_id": m.id, "active": True} for m in masters]


@router.put("/slaves/{slave_id}/masters")
def set_slave_masters(slave_id: str, data: SlaveMasterLinkRequest, db: Session = Depends(get_db)):
    update_slave_masters(db, slave_id, data)
    acc = db.query(Account).filter(Account.id == slave_id).first()
    record_event(db, "slave_masters_updated", {
        "name": acc.name if acc else slave_id,
        "slave_id": slave_id,
        "masters": data.master_ids,
    })
    return {"slave_id": slave_id, "master_ids": data.master_ids}


@router.get("/masters/{master_id}/slaves", response_model=list[AccountResponse])
def list_master_slaves(master_id: str, db: Session = Depends(get_db)):
    return get_master_slaves(db, master_id)
