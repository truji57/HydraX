from typing import Optional

from sqlalchemy.orm import Session

from app.models.account import Account, SlaveConfig, SlaveMasterLink
from app.schemas.account import AccountCreate, AccountUpdate, SlaveConfigUpdate, SlaveMasterLinkRequest
from app.utils.crypto import encrypt_password


def get_accounts(db: Session, role: Optional[str] = None) -> list[Account]:
    query = db.query(Account)
    if role:
        query = query.filter(Account.role == role)
    return query.order_by(Account.created_at.desc()).all()


def get_account(db: Session, account_id: str) -> Optional[Account]:
    return db.query(Account).filter(Account.id == account_id).first()


def create_account(db: Session, data: AccountCreate) -> Account:
    account = Account(
        name=data.name,
        role=data.role,
        login=data.login,
        password=encrypt_password(data.password),
        server=data.server,
        terminal_path=data.terminal_path,
        poll_interval=data.poll_interval,
        active=data.active,
    )
    db.add(account)
    db.flush()

    if data.role == "SLAVE":
        config = SlaveConfig(account_id=account.id)
        db.add(config)

    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: str, data: AccountUpdate) -> Optional[Account]:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return None

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password"] = encrypt_password(update_data["password"])

    for key, value in update_data.items():
        setattr(account, key, value)

    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: str) -> bool:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return False
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

    db.commit()
    db.refresh(config)
    return config


def get_slave_masters(db: Session, slave_id: str) -> list[Account]:
    links = db.query(SlaveMasterLink).filter(
        SlaveMasterLink.slave_id == slave_id,
        SlaveMasterLink.active == True
    ).all()
    master_ids = [link.master_id for link in links]
    return db.query(Account).filter(Account.id.in_(master_ids)).all() if master_ids else []


def update_slave_masters(db: Session, slave_id: str, data: SlaveMasterLinkRequest):
    db.query(SlaveMasterLink).filter(SlaveMasterLink.slave_id == slave_id).delete()

    for master_id in data.master_ids:
        link = SlaveMasterLink(slave_id=slave_id, master_id=master_id, active=True)
        db.add(link)

    db.commit()
    return get_slave_masters(db, slave_id)


def get_master_slaves(db: Session, master_id: str) -> list[Account]:
    links = db.query(SlaveMasterLink).filter(
        SlaveMasterLink.master_id == master_id,
        SlaveMasterLink.active == True
    ).all()
    slave_ids = [link.slave_id for link in links]
    return db.query(Account).filter(Account.id.in_(slave_ids)).all() if slave_ids else []


def get_masters(db: Session) -> list[Account]:
    return db.query(Account).filter(Account.role == "MASTER", Account.active == True).all()


def get_slaves(db: Session) -> list[Account]:
    return db.query(Account).filter(Account.role == "SLAVE").all()


def get_active_slaves(db: Session) -> list[Account]:
    return db.query(Account).filter(
        Account.role == "SLAVE",
        Account.active == True,
    ).all()
