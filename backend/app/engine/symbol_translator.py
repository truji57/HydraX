from app.database import SessionLocal
from app.models.symbol_map import SymbolMap
from app.utils.logger import get_logger

logger = get_logger("hydrax.symbols")


def translate_symbol(base_symbol: str, from_server: str, to_server: str) -> str:
    """Traduce un simbolo del master (from_server) al servidor del slave (to_server).

    Si no hay mapeo, devuelve el simbolo original tal cual (los simbolos con el mismo
    nombre en ambos brokers pasan sin cambios).
    """
    db = SessionLocal()
    try:
        mappings = {(m.base_symbol, m.broker_server): m.broker_symbol for m in db.query(SymbolMap).all()}
    finally:
        db.close()

    if not mappings:
        return base_symbol

    from_symbol = mappings.get((base_symbol, from_server), base_symbol)

    for (bs, srv), sym in mappings.items():
        if srv == from_server and sym == from_symbol:
            return mappings.get((bs, to_server), bs)
        if srv == from_server and bs == from_symbol:
            return mappings.get((bs, to_server), bs)

    for (bs, srv), sym in mappings.items():
        if srv == from_server and (sym == base_symbol or bs == base_symbol):
            return mappings.get((bs, to_server), base_symbol)

    return base_symbol