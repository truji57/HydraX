from app.utils.logger import get_logger

logger = get_logger("hydrax.events")

EVENT_LOG_MAX = 5000


def record_event(db, event_type: str, data: dict | None = None):
    """Guarda un evento en EventLog y poda los mas antiguos para acotar el tamaño."""
    try:
        from app.models.event_log import EventLog

        db.add(EventLog(type=event_type, data=data or {}))
        db.commit()
        try:
            old_ids = [r.id for r in db.query(EventLog.id)
                       .order_by(EventLog.timestamp.desc())
                       .offset(EVENT_LOG_MAX).all()]
            if old_ids:
                db.query(EventLog).filter(EventLog.id.in_(old_ids)).delete(synchronize_session=False)
                db.commit()
        except Exception:
            pass
    except Exception:
        pass


def record_event_standalone(event_type: str, data: dict | None = None):
    """Igual que record_event pero abriendo sesion propia (p. ej. lifecycle)."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        record_event(db, event_type, data)
    finally:
        db.close()