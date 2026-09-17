from typing import Optional
from sqlalchemy.orm import Session
from app.models.account import Account, SlaveConfig, SlaveMasterLink
from app.schemas.account import AccountCreate, AccountUpdate, SlaveConfigUpdate, SlaveMasterLinkRequest
from app.utils.crypto import encrypt_password
from app.utils.logger import get_logger

logger = get_logger("hydrax.account_service")


def get_accounts(db: Session, role: Optional[str] = None) -> list[Account]:
    query = db.query(Account)
    if role:
        query = query.filter(Account.role == role)
    return query.order_by(Account.created_at.desc()).all()


def get_account(db: Session, account_id: str) -> Optional[Account]:
    return db.query(Account).filter(Account.id == account_id).first()


def create_account(db: Session, data: AccountCreate) -> Account:
    account = Account(
        name=data.name, role=data.role, platform=data.platform, login=data.login,
        password=encrypt_password(data.password),
        bridge_host=data.bridge_host, bridge_port=data.bridge_port,
        server=data.server, terminal_path=data.terminal_path,
        poll_interval=data.poll_interval, active=data.active,
    )
    db.add(account)
    db.flush()
    if data.role == "SLAVE":
        db.add(SlaveConfig(account_id=account.id))
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: str, data: AccountUpdate) -> Optional[Account]:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["password"] = encrypt_password(update_data["password"])
    old_role = account.role
    for key, value in update_data.items():
        setattr(account, key, value)
    if old_role != "SLAVE" and account.role == "SLAVE":
        existing = db.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
        if not existing:
            db.add(SlaveConfig(account_id=account_id))
    if old_role == "MASTER" and account.role != "MASTER":
        db.query(SlaveMasterLink).filter(SlaveMasterLink.master_id == account_id).delete()
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: str) -> bool:
    from app.models.ticket_map import TicketMap
    from app.models.trade_log import TradeLog

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return False
    db.query(TicketMap).filter(
        (TicketMap.master_account_id == account_id) | (TicketMap.slave_account_id == account_id)
    ).delete(synchronize_session=False)
    db.query(TradeLog).filter(
        (TradeLog.master_account_id == account_id) | (TradeLog.slave_account_id == account_id)
    ).delete(synchronize_session=False)
    db.query(SlaveMasterLink).filter(
        (SlaveMasterLink.master_id == account_id) | (SlaveMasterLink.slave_id == account_id)
    ).delete(synchronize_session=False)
    db.delete(account)
    db.commit()
    return True


def get_slave_config(db: Session, account_id: str) -> Optional[SlaveConfig]:
    return db.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()


def update_slave_config(db: Session, account_id: str, data: SlaveConfigUpdate) -> Optional[SlaveConfig]:
    config = db.query(SlaveConfig).filter(SlaveConfig.account_id == account_id).first()
    if not config:
        config = SlaveConfig(account_id=account_id)
        db.add(config)
        db.flush()
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    if update_data.get("autocopy_enable"):
        config.paused_by_limit = False
    db.commit()
    db.refresh(config)
    return config


def get_slave_masters(db: Session, slave_id: str) -> list[Account]:
    links = db.query(SlaveMasterLink).filter(SlaveMasterLink.slave_id == slave_id, SlaveMasterLink.active == True).all()
    master_ids = [link.master_id for link in links]
    return db.query(Account).filter(Account.id.in_(master_ids)).all() if master_ids else []


def update_slave_masters(db: Session, slave_id: str, data: SlaveMasterLinkRequest):
    db.query(SlaveMasterLink).filter(SlaveMasterLink.slave_id == slave_id).delete()
    slave = db.query(Account).filter(Account.id == slave_id).first()
    slave_platform = getattr(slave, "platform", None) if slave else None
    if slave_platform is not None and hasattr(slave_platform, "value"):
        slave_platform = slave_platform.value
    for master_id in data.master_ids:
        if slave_platform is None:
            db.add(SlaveMasterLink(slave_id=slave_id, master_id=master_id, active=True))
            continue
        master = db.query(Account).filter(Account.id == master_id).first()
        master_platform = getattr(master, "platform", None) if master else None
        if master_platform is not None and hasattr(master_platform, "value"):
            master_platform = master_platform.value
        if master_platform == slave_platform:
            db.add(SlaveMasterLink(slave_id=slave_id, master_id=master_id, active=True))
        else:
            logger.warning(f"Ignorando enlace slave={slave_id} ({slave_platform}) con master={master_id} ({master_platform}): plataformas distintas")
    db.commit()
    return get_slave_masters(db, slave_id)


def get_master_slaves(db: Session, master_id: str) -> list[Account]:
    links = db.query(SlaveMasterLink).filter(SlaveMasterLink.master_id == master_id, SlaveMasterLink.active == True).all()
    slave_ids = [link.slave_id for link in links]
    return db.query(Account).filter(Account.id.in_(slave_ids)).all() if slave_ids else []
