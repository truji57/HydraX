from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os, json
from datetime import datetime
from pathlib import Path

from app.database import get_db
from app.schemas.copier import HealthResponse
from app.config import settings, get_version

router = APIRouter(prefix="/api/system", tags=["system"])


class DirEntry(BaseModel):
    name: str
    path: str
    is_dir: bool


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[DirEntry]
    drives: list[str]


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    try:
        db.connection()
        db_ok = True
    except Exception:
        db_ok = False
    return HealthResponse(status="ok", version=get_version(), db_connected=db_ok)


@router.get("/backup/export")
def backup_export(db: Session = Depends(get_db)):
    from app.models.account import Account, SlaveConfig, SlaveMasterLink
    from app.utils.crypto import decrypt_password

    accounts = []
    for a in db.query(Account).all():
        cfg = db.query(SlaveConfig).filter(SlaveConfig.account_id == a.id).first()
        links = db.query(SlaveMasterLink).filter(SlaveMasterLink.slave_id == a.id).all()
        pwd = ""
        try: pwd = decrypt_password(a.password)
        except: pwd = a.password

        accounts.append({
            "name": a.name, "role": a.role.value, "login": a.login, "password": pwd,
            "bridge_host": a.bridge_host, "bridge_port": a.bridge_port,
            "poll_interval": a.poll_interval, "active": a.active,
            "config": {
                "risk_mode": cfg.risk_mode.value if cfg and cfg.risk_mode else "FIXED",
                "risk_percent": cfg.risk_percent if cfg else 0.5,
                "risk_usd": cfg.risk_usd if cfg else 50.0,
                "fixed_contracts": cfg.fixed_contracts if cfg else 1,
                "lot_multiplier": cfg.lot_multiplier if cfg else 1.0,
                "max_contracts": cfg.max_contracts if cfg else 100,
                "max_positions": cfg.max_positions if cfg else 100,
                "autocopy_enable": cfg.autocopy_enable if cfg else True,
                "copy_sl": cfg.copy_sl if cfg else True,
                "copy_tp": cfg.copy_tp if cfg else True,
                "inverse_copy": cfg.inverse_copy if cfg else False,
                "delay_sec": cfg.delay_sec if cfg else 0.0,
                "magic_number": cfg.magic_number if cfg else 0,
            } if cfg else None,
            "linked_masters": [link.master_id for link in links],
        })

    return JSONResponse(content={"version": get_version(), "exported_at": datetime.utcnow().isoformat(), "accounts": accounts})


@router.post("/backup/import")
async def backup_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        data = json.loads(content)
    except Exception as e:
        return {"ok": False, "error": f"Invalid JSON: {e}"}

    from app.models.account import Account, SlaveConfig, SlaveMasterLink
    from app.models.ticket_map import TicketMap
    from app.models.trade_log import TradeLog
    from app.utils.crypto import encrypt_password

    try:
        db.query(SlaveMasterLink).delete()
        db.query(SlaveConfig).delete()
        db.query(TicketMap).delete()
        db.query(TradeLog).delete()
        db.query(Account).delete()
        db.flush()

        created_ids = {}
        for a in data.get("accounts", []):
            account = Account(
                name=a["name"], role=a["role"], login=a.get("login", 0),
                password=encrypt_password(a.get("password", "")),
                bridge_host=a.get("bridge_host", "localhost"),
                bridge_port=a.get("bridge_port", 5555),
                poll_interval=a.get("poll_interval", 0.5),
                active=a.get("active", True),
            )
            db.add(account)
            db.flush()
            created_ids[a["name"]] = account.id

            if a["role"] == "SLAVE" and a.get("config"):
                cfg = a["config"]
                db.add(SlaveConfig(
                    account_id=account.id,
                    risk_mode=cfg.get("risk_mode", "FIXED"),
                    risk_percent=cfg.get("risk_percent", 0.5),
                    risk_usd=cfg.get("risk_usd", 50.0),
                    fixed_contracts=cfg.get("fixed_contracts", 1),
                    lot_multiplier=cfg.get("lot_multiplier", 1.0),
                    max_contracts=cfg.get("max_contracts", 100),
                    max_positions=cfg.get("max_positions", 100),
                    autocopy_enable=cfg.get("autocopy_enable", True),
                    copy_sl=cfg.get("copy_sl", True),
                    copy_tp=cfg.get("copy_tp", True),
                    inverse_copy=cfg.get("inverse_copy", False),
                    delay_sec=cfg.get("delay_sec", 0.0),
                    magic_number=cfg.get("magic_number", 0),
                ))

        for a in data.get("accounts", []):
            if a["role"] == "SLAVE" and a.get("linked_masters"):
                slave_id = created_ids.get(a["name"])
                if slave_id:
                    for mid in a["linked_masters"]:
                        for name, aid in created_ids.items():
                            if aid == mid or name == mid:
                                db.add(SlaveMasterLink(slave_id=slave_id, master_id=aid, active=True))
                                break

        db.commit()
        return {"ok": True, "message": f"Importado: {len(data.get('accounts',[]))} cuentas"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}


@router.get("/update-check")
def update_check():
    import subprocess
    from app.config import get_version, BASE_DIR
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "origin"],
            capture_output=True, text=True, cwd=str(BASE_DIR.parent), timeout=10
        )
        if result.returncode != 0:
            return {"update_available": False}
        tags = []
        for line in result.stdout.strip().split("\n"):
            if line and "refs/tags/v" in line:
                tag = line.split("refs/tags/")[-1].strip()
                if not tag.endswith("^{}"):
                    tags.append(tag)
        if not tags:
            return {"update_available": False}
        tags.sort(key=lambda t: [int(x) for x in t.lstrip("v").split(".")])
        latest_remote = tags[-1]
        local = get_version()
        return {
            "update_available": latest_remote.lstrip("v") != local,
            "current": local,
            "latest": latest_remote.lstrip("v"),
        }
    except Exception:
        return {"update_available": False}


@router.get("/changelog")
def changelog():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent.parent / "changelog.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/copy-bridge")
def copy_bridge():
    import shutil
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    addons = Path.home() / "Documents" / "NinjaTrader 8" / "bin" / "Custom" / "AddOns"
    config_dst = Path.home() / "Documents" / "NinjaTrader 8" / "hydrax_config.json"

    if not addons.exists():
        return {"ok": False, "error": f"Carpeta AddOns no encontrada: {addons}. Asegurate de tener NT8 instalado."}

    copied = []
    for file_name, dst in [("NT8HydraX.cs", addons / "NT8HydraX.cs"), ("hydrax_config.json", config_dst)]:
        src = project_root / "bridge" / file_name
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(file_name)

    if not copied:
        return {"ok": False, "error": "No se encontraron archivos para copiar"}
    return {"ok": True, "message": f"Copiado a NT8: {', '.join(copied)}. Recompila en NT8 (F5)."}


@router.get("/bridge-config")
def get_bridge_config():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent.parent.parent / "bridge" / "hydrax_config.json"
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            return {"ok": True, "port": cfg.get("port", 5555)}
        except Exception:
            pass
    return {"ok": True, "port": 5555}


@router.post("/bridge-config")
def set_bridge_config(data: dict):
    import json
    from pathlib import Path
    port = data.get("port", 5555)
    path = Path(__file__).resolve().parent.parent.parent.parent / "bridge" / "hydrax_config.json"
    try:
        path.write_text(json.dumps({"port": int(port)}), encoding="utf-8")
        return {"ok": True, "message": f"Puerto guardado: {port}. Ahora haz clic en Copiar a NT8 para aplicar el cambio."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
