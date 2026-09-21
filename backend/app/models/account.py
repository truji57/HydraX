import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Boolean, Enum, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class AccountRole(str, enum.Enum):
    MASTER = "MASTER"
    SLAVE = "SLAVE"


class Platform(str, enum.Enum):
    NT8 = "NT8"
    MT5 = "MT5"


class RiskMode(str, enum.Enum):
    FIXED = "FIXED"  # legado NT8, migrado a FIXED_CONTRACTS
    FIXED_CONTRACTS = "FIXED_CONTRACTS"
    FIXED_LOTS = "FIXED_LOTS"
    RISK_PERCENT = "RISK_PERCENT"
    RISK_USD = "RISK_USD"
    RATIO = "RATIO"
    BALANCE_PROP = "BALANCE_PROP"


class PnLMode(str, enum.Enum):
    USD = "USD"
    PERCENT = "PERCENT"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    role = Column(Enum(AccountRole), nullable=False)
    platform = Column(Enum(Platform), default=Platform.NT8, nullable=False)
    login = Column(String(50), nullable=False)
    password = Column(Text, nullable=False)
    bridge_host = Column(String(100), default="localhost")
    bridge_port = Column(Integer, default=5555)
    server = Column(String(100), nullable=True)
    terminal_path = Column(String(300), nullable=True)
    filling_mode = Column(String(10), nullable=True)
    poll_interval = Column(Float, default=0.5)
    active = Column(Boolean, default=True)
    color = Column(String(7), default="#3b82f6")
    copy_enable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    slave_config = relationship("SlaveConfig", back_populates="account", uselist=False, cascade="all, delete-orphan")
    master_links = relationship(
        "SlaveMasterLink",
        foreign_keys="SlaveMasterLink.slave_id",
        back_populates="slave",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    slave_links = relationship(
        "SlaveMasterLink",
        foreign_keys="SlaveMasterLink.master_id",
        back_populates="master",
        cascade="all, delete-orphan",
    )

    @property
    def linked_masters(self) -> list[str]:
        return [link.master.name for link in self.master_links if link.active and link.master.role == AccountRole.MASTER]


class SlaveConfig(Base):
    __tablename__ = "slave_config"

    id = Column(String, primary_key=True, default=gen_uuid)
    account_id = Column(String, ForeignKey("accounts.id", ondelete="CASCADE"), unique=True, nullable=False)
    risk_mode = Column(Enum(RiskMode), default=RiskMode.FIXED_CONTRACTS)
    fixed_contracts = Column(Integer, default=1)
    fixed_lots = Column(Float, default=0.01)
    risk_percent = Column(Float, default=0.5)
    risk_usd = Column(Float, default=50.0)
    lot_multiplier = Column(Float, default=1.0)
    max_contracts = Column(Integer, default=100)
    max_lots = Column(Float, default=10.0)
    max_positions = Column(Integer, default=100)
    autocopy_enable = Column(Boolean, default=True)
    copy_sl = Column(Boolean, default=True)
    copy_tp = Column(Boolean, default=True)
    inverse_copy = Column(Boolean, default=False)
    copy_modify = Column(Boolean, default=True)
    sync_close = Column(Boolean, default=False)
    template_id = Column(String, ForeignKey("slave_templates.id", ondelete="SET NULL"), nullable=True)
    daily_loss_enabled = Column(Boolean, default=False)
    daily_loss_limit = Column(Float, default=0.0)
    daily_loss_mode = Column(Enum(PnLMode), default=PnLMode.USD)
    daily_profit_enabled = Column(Boolean, default=False)
    daily_profit_limit = Column(Float, default=0.0)
    daily_profit_mode = Column(Enum(PnLMode), default=PnLMode.USD)
    daily_pnl = Column(Float, default=0.0)
    last_pnl_reset = Column(DateTime, nullable=True)
    paused_by_limit = Column(Boolean, default=False)
    delay_sec = Column(Float, default=0.0)
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


class SlaveTemplate(Base):
    __tablename__ = "slave_templates"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False, unique=True)
    risk_mode = Column(Enum(RiskMode), default=RiskMode.FIXED_CONTRACTS)
    fixed_contracts = Column(Integer, default=1)
    fixed_lots = Column(Float, default=0.01)
    risk_percent = Column(Float, default=0.5)
    risk_usd = Column(Float, default=50.0)
    lot_multiplier = Column(Float, default=1.0)
    max_contracts = Column(Integer, default=100)
    max_lots = Column(Float, default=10.0)
    max_positions = Column(Integer, default=100)
    autocopy_enable = Column(Boolean, default=True)
    copy_sl = Column(Boolean, default=True)
    copy_tp = Column(Boolean, default=True)
    inverse_copy = Column(Boolean, default=False)
    copy_modify = Column(Boolean, default=True)
    sync_close = Column(Boolean, default=False)
    daily_loss_enabled = Column(Boolean, default=False)
    daily_loss_limit = Column(Float, default=0.0)
    daily_loss_mode = Column(Enum(PnLMode), default=PnLMode.USD)
    daily_profit_enabled = Column(Boolean, default=False)
    daily_profit_limit = Column(Float, default=0.0)
    daily_profit_mode = Column(Enum(PnLMode), default=PnLMode.USD)
    delay_sec = Column(Float, default=0.0)
    magic_number = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
