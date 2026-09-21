from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.account import SlaveTemplate, RiskMode, PnLMode
from app.utils.events import record_event
from app.schemas.account import (
    SlaveTemplateCreate, SlaveTemplateUpdate, SlaveTemplateResponse,
)

router = APIRouter(prefix="/api/templates", tags=["templates"])

TEMPLATE_FIELDS = [
    "risk_mode", "fixed_contracts", "fixed_lots", "risk_percent", "risk_usd",
    "lot_multiplier", "max_contracts", "max_lots", "max_positions",
    "autocopy_enable", "copy_sl", "copy_tp", "inverse_copy", "copy_modify",
    "sync_close", "daily_loss_enabled", "daily_loss_limit", "daily_loss_mode",
    "daily_profit_enabled", "daily_profit_limit", "daily_profit_mode",
    "delay_sec", "magic_number",
]


def _enum_val(v):
    return v.value if v is not None and hasattr(v, "value") else v


def _coerce(payload: dict) -> dict:
    for key in ("risk_mode",):
        if payload.get(key):
            payload[key] = RiskMode(payload[key])
    for key in ("daily_loss_mode", "daily_profit_mode"):
        if payload.get(key):
            payload[key] = PnLMode(payload[key])
    return payload


@router.get("", response_model=list[SlaveTemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return db.query(SlaveTemplate).order_by(SlaveTemplate.name).all()


@router.post("", response_model=SlaveTemplateResponse, status_code=201)
def create_template(data: SlaveTemplateCreate, db: Session = Depends(get_db)):
    t = SlaveTemplate(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    record_event(db, "template_created", {"name": t.name, "risk_mode": t.risk_mode.value if t.risk_mode else None})
    return t


@router.put("/{template_id}", response_model=SlaveTemplateResponse)
def update_template(template_id: str, data: SlaveTemplateUpdate, db: Session = Depends(get_db)):
    from app.models.account import SlaveConfig

    t = db.query(SlaveTemplate).filter(SlaveTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(t, key, value)
    db.flush()

    slaves = db.query(SlaveConfig).filter(SlaveConfig.template_id == template_id).all()
    for sc in slaves:
        sc.risk_mode = t.risk_mode
        sc.fixed_contracts = t.fixed_contracts
        sc.fixed_lots = t.fixed_lots
        sc.risk_percent = t.risk_percent
        sc.risk_usd = t.risk_usd
        sc.lot_multiplier = t.lot_multiplier
        sc.max_contracts = t.max_contracts
        sc.max_lots = t.max_lots
        sc.max_positions = t.max_positions
        sc.autocopy_enable = t.autocopy_enable
        sc.copy_sl = t.copy_sl
        sc.copy_tp = t.copy_tp
        sc.inverse_copy = t.inverse_copy
        sc.copy_modify = t.copy_modify
        sc.sync_close = t.sync_close
        sc.daily_loss_enabled = t.daily_loss_enabled
        sc.daily_loss_limit = t.daily_loss_limit
        sc.daily_loss_mode = t.daily_loss_mode
        sc.daily_profit_enabled = t.daily_profit_enabled
        sc.daily_profit_limit = t.daily_profit_limit
        sc.daily_profit_mode = t.daily_profit_mode
        sc.delay_sec = t.delay_sec
        sc.magic_number = t.magic_number

    db.commit()
    db.refresh(t)
    record_event(db, "template_updated", {
        "name": t.name, "risk_mode": t.risk_mode.value if t.risk_mode else None,
        "slaves_actualizados": len(slaves),
    })
    return t


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, db: Session = Depends(get_db)):
    from app.models.account import SlaveConfig

    t = db.query(SlaveTemplate).filter(SlaveTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    # Desvincular los slaves que la usaban (SQLite no aplica FOREIGN KEY por defecto)
    db.query(SlaveConfig).filter(SlaveConfig.template_id == template_id).update(
        {SlaveConfig.template_id: None}, synchronize_session=False
    )
    name = t.name
    db.delete(t)
    db.commit()
    record_event(db, "template_deleted", {"name": name})


@router.get("/export")
def export_templates(db: Session = Depends(get_db)):
    rows = db.query(SlaveTemplate).order_by(SlaveTemplate.name).all()
    templates = []
    for t in rows:
        item = {"name": t.name}
        for f in TEMPLATE_FIELDS:
            item[f] = _enum_val(getattr(t, f))
        templates.append(item)
    return {"app": "hydrax", "kind": "templates", "version": 1, "templates": templates}


@router.post("/import")
def import_templates(data: dict, db: Session = Depends(get_db)):
    existing = {t.name.lower(): t for t in db.query(SlaveTemplate).all()}
    count = 0
    for item in data.get("templates", []):
        name = (item.get("name") or "").strip()
        if not name:
            continue
        payload = _coerce({f: item.get(f) for f in TEMPLATE_FIELDS if f in item and item.get(f) is not None})
        if name.lower() in existing:
            t = existing[name.lower()]
            for k, v in payload.items():
                setattr(t, k, v)
        else:
            db.add(SlaveTemplate(name=name, **payload))
        count += 1
    db.commit()
    record_event(db, "template_imported", {"templates": count})
    return {"ok": True, "imported": count}
