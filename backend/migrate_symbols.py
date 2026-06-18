"""Migra symbols_map.yaml del HydraX antiguo a la base de datos nueva."""
import yaml
from app.database import init_db, SessionLocal
from app.models.symbol_map import SymbolMap

OLD_YAML = "../HydraX - OLD stable version/symbols_map.yaml"

def migrate():
    init_db()
    db = SessionLocal()

    with open(OLD_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    count = 0
    skipped = 0
    for base_symbol, servers in data.items():
        if base_symbol == "tipo":
            continue
        for broker_server, broker_symbol in servers.items():
            if broker_server == "tipo":
                continue
            existing = db.query(SymbolMap).filter(
                SymbolMap.base_symbol == base_symbol,
                SymbolMap.broker_server == broker_server,
            ).first()
            if existing:
                skipped += 1
                continue
            db.add(SymbolMap(
                base_symbol=base_symbol,
                broker_server=broker_server,
                broker_symbol=broker_symbol,
            ))
            count += 1
            print(f"  {base_symbol} | {broker_server} -> {broker_symbol}")

    db.commit()
    db.close()
    print(f"\n{count} entradas importadas (skipped {skipped} existing).")

if __name__ == "__main__":
    migrate()
