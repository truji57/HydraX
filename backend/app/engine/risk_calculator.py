from app.utils.logger import get_logger

logger = get_logger("hydrax.risk")

EPS = 1e-6


def calculate_lots_fixed(fixed_lots: float) -> float:
    return max(0.01, fixed_lots)


def calculate_lots_risk_percent(
    balance: float,
    risk_percent: float,
    entry_price: float,
    sl_price: float,
    tick_size: float,
    tick_value: float,
    volume_min: float = 0.01,
    volume_step: float = 0.01,
) -> float:
    risk_usd = balance * (risk_percent / 100.0)
    return _calculate_lots_from_risk_usd(risk_usd, entry_price, sl_price, tick_size, tick_value, volume_min, volume_step)


def calculate_lots_risk_usd(
    risk_usd: float,
    entry_price: float,
    sl_price: float,
    tick_size: float,
    tick_value: float,
    volume_min: float = 0.01,
    volume_step: float = 0.01,
) -> float:
    return _calculate_lots_from_risk_usd(risk_usd, entry_price, sl_price, tick_size, tick_value, volume_min, volume_step)


def _calculate_lots_from_risk_usd(
    risk_usd: float,
    entry_price: float,
    sl_price: float,
    tick_size: float,
    tick_value: float,
    volume_min: float = 0.01,
    volume_step: float = 0.01,
) -> float:
    if not sl_price or sl_price == 0:
        raise ValueError("SL invalido")
    if tick_value <= 0:
        raise ValueError("tick_value invalido")

    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= EPS:
        raise ValueError("SL demasiado cerca del entry")

    ticks = sl_distance / tick_size
    loss_per_lot = ticks * tick_value
    if loss_per_lot <= 0:
        raise ValueError("loss_per_lot <= 0")

    lots = risk_usd / loss_per_lot
    lots_rounded = max(volume_min, (lots // volume_step) * volume_step)
    return round(lots_rounded, 2)


def calculate_lots_ratio(master_lots: float, lot_multiplier: float) -> float:
    return round(master_lots * lot_multiplier, 2)


def calculate_lots_balance_prop(
    master_lots: float,
    slave_balance: float,
    master_balance: float,
) -> float:
    if master_balance <= 0:
        raise ValueError("master_balance invalido")
    ratio = slave_balance / master_balance
    return round(master_lots * ratio, 2)
