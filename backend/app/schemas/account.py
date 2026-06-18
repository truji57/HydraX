from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.account import AccountRole, RiskMode, SymbolMode


class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: AccountRole
    login: int = Field(..., gt=0)
    password: str
    server: str
    terminal_path: str
    poll_interval: float = Field(0.5, gt=0)
    active: bool = True


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    login: Optional[int] = Field(None, gt=0)
    password: Optional[str] = None
    server: Optional[str] = None
    terminal_path: Optional[str] = None
    poll_interval: Optional[float] = Field(None, gt=0)
    active: Optional[bool] = None


class AccountResponse(BaseModel):
    id: str
    name: str
    role: AccountRole
    login: int
    server: str
    terminal_path: str
    poll_interval: float
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SlaveConfigBase(BaseModel):
    risk_mode: RiskMode = RiskMode.RISK_PERCENT
    fixed_lots: float = 0.01
    risk_percent: float = 0.5
    risk_usd: float = 50.0
    lot_multiplier: float = 1.0
    max_lots: float = 100.0
    max_positions: int = 100
    max_drawdown_pct: Optional[float] = None
    daily_loss_limit: Optional[float] = None
    autocopy_enable: bool = True
    copy_sl: bool = True
    copy_tp: bool = True
    inverse_copy: bool = False
    delay_sec: float = 0.0
    symbol_mode: SymbolMode = SymbolMode.ALL
    symbol_filter: list[str] = []
    order_comment: Optional[str] = None
    magic_number: int = 0


class SlaveConfigUpdate(SlaveConfigBase):
    pass


class SlaveConfigResponse(SlaveConfigBase):
    id: str
    account_id: str

    model_config = {"from_attributes": True}


class SlaveMasterLinkRequest(BaseModel):
    master_ids: list[str]


class SlaveMasterLinkResponse(BaseModel):
    slave_id: str
    master_id: str
    active: bool

    model_config = {"from_attributes": True}


class AccountTestResult(BaseModel):
    success: bool
    message: str
    balance: Optional[float] = None
    equity: Optional[float] = None
    server: Optional[str] = None
