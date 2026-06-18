import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Boolean, Enum, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class AccountRole(str, enum.Enum):
    MASTER = "MASTER"
    SLAVE = "SLAVE"


class RiskMode(str, enum.Enum):
    FIXED = "FIXED"
    RISK_PERCENT = "RISK_PERCENT"
    RISK_USD = "RISK_USD"
    RISK_OF_MASTER = "RISK_OF_MASTER"
    RATIO = "RATIO"
    BALANCE_PROP = "BALANCE_PROP"


class SymbolMode(str, enum.Enum):
    ALL = "ALL"
    WHITELIST = "WHITELIST"
    BLACKLIST = "BLACKLIST"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    role = Column(Enum(AccountRole), nullable=False)
    login = Column(Integer, nullable=False)
    password = Column(Text, nullable=False)
    server = Column(String(100), nullable=False)
    terminal_path = Column(String(500), nullable=False)
    poll_interval = Column(Float, default=0.5)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    slave_config = relationship("SlaveConfig", back_populates="account", uselist=False, cascade="all, delete-orphan")
    master_links = relationship(
        "SlaveMasterLink",
        foreign_keys="SlaveMasterLink.slave_id",
        back_populates="slave",
        cascade="all, delete-orphan",
    )
    slave_links = relationship(
        "SlaveMasterLink",
        foreign_keys="SlaveMasterLink.master_id",
        back_populates="master",
        cascade="all, delete-orphan",
    )


class SlaveConfig(Base):
    __tablename__ = "slave_config"

    id = Column(String, primary_key=True, default=gen_uuid)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, nullable=False)
    risk_mode = Column(Enum(RiskMode), default=RiskMode.RISK_PERCENT)
    fixed_lots = Column(Float, default=0.01)
    risk_percent = Column(Float, default=0.5)
    risk_usd = Column(Float, default=50.0)
    lot_multiplier = Column(Float, default=1.0)
    max_lots = Column(Float, default=100.0)
    max_positions = Column(Integer, default=100)
    max_drawdown_pct = Column(Float, nullable=True)
    daily_loss_limit = Column(Float, nullable=True)
    autocopy_enable = Column(Boolean, default=True)
    copy_sl = Column(Boolean, default=True)
    copy_tp = Column(Boolean, default=True)
    inverse_copy = Column(Boolean, default=False)
    delay_sec = Column(Float, default=0.0)
    symbol_mode = Column(Enum(SymbolMode), default=SymbolMode.ALL)
    symbol_filter = Column(JSON, default=list)
    order_comment = Column(String(100), nullable=True)
    magic_number = Column(Integer, default=0)

    account = relationship("Account", back_populates="slave_config")


class SlaveMasterLink(Base):
    __tablename__ = "slave_master_link"

    id = Column(String, primary_key=True, default=gen_uuid)
    slave_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    master_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    active = Column(Boolean, default=True)

    slave = relationship("Account", foreign_keys=[slave_id], back_populates="master_links")
    master = relationship("Account", foreign_keys=[master_id], back_populates="slave_links")
