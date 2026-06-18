from app.database import SessionLocal
from app.models.symbol_map import SymbolMap
from app.utils.logger import get_logger

logger = get_logger("hydrax.symbols")


def translate_symbol(base_symbol: str, from_server: str, to_server: str) -> str:
    db = SessionLocal()
    try:
        mappings = {}
        for m in db.query(SymbolMap).all():
            mappings[(m.base_symbol, m.broker_server)] = m.broker_symbol

        from_symbol = mappings.get((base_symbol, from_server), base_symbol)

        for (bs, srv), sym in mappings.items():
            if srv == from_server and sym == from_symbol:
                result = mappings.get((bs, to_server))
                if result:
                    return result
            if srv == from_server and bs == from_symbol:
                result = mappings.get((bs, to_server))
                if result:
                    return result

        return base_symbol
    finally:
        db.close()
