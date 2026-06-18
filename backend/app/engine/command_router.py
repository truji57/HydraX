from app.database import SessionLocal
from app.models.account import SlaveMasterLink
from app.models.account import SlaveConfig
from app.utils.logger import get_logger

logger = get_logger("hydrax.router")


def get_linked_slave_ids(master_id: str) -> list[str]:
    db = SessionLocal()
    try:
        links = (
            db.query(SlaveMasterLink)
            .filter(
                SlaveMasterLink.master_id == master_id,
                SlaveMasterLink.active == True,
            )
            .all()
        )
        return [link.slave_id for link in links]
    finally:
        db.close()


def is_slave_linked_to_master(slave_id: str, master_id: str) -> bool:
    db = SessionLocal()
    try:
        link = (
            db.query(SlaveMasterLink)
            .filter(
                SlaveMasterLink.slave_id == slave_id,
                SlaveMasterLink.master_id == master_id,
                SlaveMasterLink.active == True,
            )
            .first()
        )
        return link is not None
    finally:
        db.close()
