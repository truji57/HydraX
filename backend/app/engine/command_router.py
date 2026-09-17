from app.database import SessionLocal
from app.models.account import SlaveMasterLink, Account
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
        if link is None:
            return False
        slave = db.query(Account).filter(Account.id == slave_id).first()
        master = db.query(Account).filter(Account.id == master_id).first()
        if not slave or not master:
            return False
        slave_platform = (slave.platform or "NT8").value if hasattr(slave.platform, "value") else slave.platform or "NT8"
        master_platform = (master.platform or "NT8").value if hasattr(master.platform, "value") else master.platform or "NT8"
        return slave_platform == master_platform
    finally:
        db.close()
