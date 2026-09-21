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
    from app.models.account import Account, SlaveConfig, SlaveMasterLink, SlaveTemplate, Platform, RiskMode, PnLMode
    from app.models.server import Server
    from app.models.symbol_map import SymbolMap
    from app.utils.crypto import decrypt_password

    def ev(v):
        return v.value if v is not None and hasattr(v, "value") else v

    accounts = []
    for a in db.query(Account).all():
        cfg = db.query(SlaveConfig).filter(SlaveConfig.account_id == a.id).first()
        links = db.query(SlaveMasterLink).filter(SlaveMasterLink.slave_id == a.id).all()
        pwd = ""
        try:
            pwd = decrypt_password(a.password)
        except Exception:
            pwd = a.password

        account = {
            "name": a.name, "role": a.role.value,
            "platform": ev(a.platform), "login": a.login, "password": pwd,
            "bridge_host": a.bridge_host, "bridge_port": a.bridge_port,
            "server": a.server, "terminal_path": a.terminal_path,
            "poll_interval": a.poll_interval, "active": a.active,
            "color": a.color, "copy_enable": a.copy_enable,
            "linked_masters": [link.master_id for link in links],
        }
        if cfg:
            account["config"] = {
                "risk_mode": ev(cfg.risk_mode), "risk_percent": cfg.risk_percent,
                "risk_usd": cfg.risk_usd, "fixed_contracts": cfg.fixed_contracts,
                "fixed_lots": cfg.fixed_lots, "lot_multiplier": cfg.lot_multiplier,
                "max_contracts": cfg.max_contracts, "max_lots": cfg.max_lots,
                "max_positions": cfg.max_positions, "autocopy_enable": cfg.autocopy_enable,
                "copy_sl": cfg.copy_sl, "copy_tp": cfg.copy_tp,
                "inverse_copy": cfg.inverse_copy, "copy_modify": cfg.copy_modify,
                "sync_close": cfg.sync_close,
                "daily_loss_enabled": cfg.daily_loss_enabled, "daily_loss_limit": cfg.daily_loss_limit,
                "daily_loss_mode": ev(cfg.daily_loss_mode),
                "daily_profit_enabled": cfg.daily_profit_enabled, "daily_profit_limit": cfg.daily_profit_limit,
                "daily_profit_mode": ev(cfg.daily_profit_mode),
                "delay_sec": cfg.delay_sec, "magic_number": cfg.magic_number,
                "template_id": cfg.template_id,
            }
        accounts.append(account)

    templates = []
    for t in db.query(SlaveTemplate).all():
        templates.append({
            "id": t.id, "name": t.name, "risk_mode": ev(t.risk_mode),
            "fixed_contracts": t.fixed_contracts, "fixed_lots": t.fixed_lots,
            "risk_percent": t.risk_percent, "risk_usd": t.risk_usd,
            "lot_multiplier": t.lot_multiplier, "max_contracts": t.max_contracts,
            "max_lots": t.max_lots, "max_positions": t.max_positions,
            "autocopy_enable": t.autocopy_enable, "copy_sl": t.copy_sl, "copy_tp": t.copy_tp,
            "inverse_copy": t.inverse_copy, "copy_modify": t.copy_modify,
            "sync_close": t.sync_close,
            "daily_loss_enabled": t.daily_loss_enabled, "daily_loss_limit": t.daily_loss_limit,
            "daily_loss_mode": ev(t.daily_loss_mode),
            "daily_profit_enabled": t.daily_profit_enabled, "daily_profit_limit": t.daily_profit_limit,
            "daily_profit_mode": ev(t.daily_profit_mode),
            "delay_sec": t.delay_sec, "magic_number": t.magic_number,
        })

    servers = [{"name": s.name, "platform": ev(s.platform)} for s in db.query(Server).all()]
    symbols = [{"base_symbol": m.base_symbol, "broker_server": m.broker_server,
                "broker_symbol": m.broker_symbol} for m in db.query(SymbolMap).all()]

    return JSONResponse(content={
        "version": get_version(), "exported_at": datetime.utcnow().isoformat(),
        "app": "hydrax", "accounts": accounts,
        "templates": templates, "servers": servers, "symbols": symbols,
    })


@router.post("/backup/import")
async def backup_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        content = await file.read()
        data = json.loads(content)
    except Exception as e:
        return {"ok": False, "error": f"Invalid JSON: {e}"}

    from app.models.account import (
        Account, SlaveConfig, SlaveMasterLink, SlaveTemplate, Platform, RiskMode, PnLMode,
    )
    from app.models.server import Server
    from app.models.symbol_map import SymbolMap
    from app.models.ticket_map import TicketMap
    from app.models.trade_log import TradeLog
    from app.utils.crypto import encrypt_password

    def coerce_enum(value, enum_cls):
        if not value:
            return None
        try:
            return enum_cls(value) if not isinstance(value, enum_cls) else value
        except Exception:
            return None

    try:
        db.query(SlaveMasterLink).delete()
        db.query(SlaveConfig).delete()
        db.query(SlaveTemplate).delete()
        db.query(TicketMap).delete()
        db.query(TradeLog).delete()
        db.query(Account).delete()
        db.query(Server).delete()
        db.query(SymbolMap).delete()
        db.flush()

        # Plantillas
        template_map = {}
        for t in data.get("templates", []):
            tmpl = SlaveTemplate(
                name=t.get("name") or f"template-{len(template_map)}",
                risk_mode=coerce_enum(t.get("risk_mode"), RiskMode),
                fixed_contracts=t.get("fixed_contracts", 1), fixed_lots=t.get("fixed_lots", 0.01),
                risk_percent=t.get("risk_percent", 0.5), risk_usd=t.get("risk_usd", 50.0),
                lot_multiplier=t.get("lot_multiplier", 1.0),
                max_contracts=t.get("max_contracts", 100), max_lots=t.get("max_lots", 10.0),
                max_positions=t.get("max_positions", 100),
                autocopy_enable=t.get("autocopy_enable", True),
                copy_sl=t.get("copy_sl", True), copy_tp=t.get("copy_tp", True),
                inverse_copy=t.get("inverse_copy", False),
                copy_modify=t.get("copy_modify", True), sync_close=t.get("sync_close", False),
                daily_loss_enabled=t.get("daily_loss_enabled", False),
                daily_loss_limit=t.get("daily_loss_limit", 0.0),
                daily_loss_mode=coerce_enum(t.get("daily_loss_mode"), PnLMode),
                daily_profit_enabled=t.get("daily_profit_enabled", False),
                daily_profit_limit=t.get("daily_profit_limit", 0.0),
                daily_profit_mode=coerce_enum(t.get("daily_profit_mode"), PnLMode),
                delay_sec=t.get("delay_sec", 0.0), magic_number=t.get("magic_number", 0),
            )
            db.add(tmpl)
            db.flush()
            if t.get("id"):
                template_map[t["id"]] = tmpl.id

        # Servidores
        for s in data.get("servers", []):
            name = (s.get("name") or "").strip()
            if name:
                db.add(Server(name=name, platform=coerce_enum(s.get("platform") or "MT5", Platform) or Platform.MT5))

        # Simbolos
        for m in data.get("symbols", []):
            base = (m.get("base_symbol") or "").strip()
            server = (m.get("broker_server") or "").strip()
            bsym = (m.get("broker_symbol") or "").strip()
            if base and server and bsym:
                db.add(SymbolMap(base_symbol=base, broker_server=server, broker_symbol=bsym))

        # Cuentas
        created_ids = {}
        for a in data.get("accounts", []):
            account = Account(
                name=a.get("name", "?"), role=a.get("role", "SLAVE"),
                platform=coerce_enum(a.get("platform") or "NT8", Platform) or Platform.NT8,
                login=str(a.get("login", 0)),
                password=encrypt_password(a.get("password", "")),
                bridge_host=a.get("bridge_host", "localhost"),
                bridge_port=a.get("bridge_port", 5555),
                server=a.get("server"), terminal_path=a.get("terminal_path"),
                poll_interval=a.get("poll_interval", 0.5),
                active=a.get("active", True),
                color=a.get("color", "#3b82f6"),
                copy_enable=a.get("copy_enable", True),
            )
            db.add(account)
            db.flush()
            created_ids[a.get("name")] = account.id

            cfg = a.get("config")
            if a.get("role") == "SLAVE" and cfg:
                db.add(SlaveConfig(
                    account_id=account.id,
                    risk_mode=coerce_enum(cfg.get("risk_mode") or "FIXED_CONTRACTS", RiskMode),
                    risk_percent=cfg.get("risk_percent", 0.5),
                    risk_usd=cfg.get("risk_usd", 50.0),
                    fixed_contracts=cfg.get("fixed_contracts", 1),
                    fixed_lots=cfg.get("fixed_lots", 0.01),
                    lot_multiplier=cfg.get("lot_multiplier", 1.0),
                    max_contracts=cfg.get("max_contracts", 100),
                    max_lots=cfg.get("max_lots", 10.0),
                    max_positions=cfg.get("max_positions", 100),
                    autocopy_enable=cfg.get("autocopy_enable", True),
                    copy_sl=cfg.get("copy_sl", True),
                    copy_tp=cfg.get("copy_tp", True),
                    inverse_copy=cfg.get("inverse_copy", False),
                    copy_modify=cfg.get("copy_modify", True),
                    sync_close=cfg.get("sync_close", False),
                    daily_loss_enabled=cfg.get("daily_loss_enabled", False),
                    daily_loss_limit=cfg.get("daily_loss_limit", 0.0),
                    daily_loss_mode=coerce_enum(cfg.get("daily_loss_mode") or "USD", PnLMode),
                    daily_profit_enabled=cfg.get("daily_profit_enabled", False),
                    daily_profit_limit=cfg.get("daily_profit_limit", 0.0),
                    daily_profit_mode=coerce_enum(cfg.get("daily_profit_mode") or "USD", PnLMode),
                    delay_sec=cfg.get("delay_sec", 0.0),
                    magic_number=cfg.get("magic_number", 0),
                    template_id=template_map.get(cfg.get("template_id")),
                ))

        for a in data.get("accounts", []):
            if a.get("role") == "SLAVE" and a.get("linked_masters"):
                slave_id = created_ids.get(a.get("name"))
                if slave_id:
                    for mid in a["linked_masters"]:
                        for name, aid in created_ids.items():
                            if aid == mid or name == mid:
                                db.add(SlaveMasterLink(slave_id=slave_id, master_id=aid, active=True))
                                break

        db.commit()
        return {"ok": True, "message": f"Importado: {len(data.get('accounts', []))} cuentas, "
                                       f"{len(data.get('templates', []))} plantillas, "
                                       f"{len(data.get('servers', []))} servidores, "
                                       f"{len(data.get('symbols', []))} simbolos"}
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
