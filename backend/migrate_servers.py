import yaml
from app.database import init_db, SessionLocal
from app.models.server import Server
from app.models.symbol_map import SymbolMap

OLD_YAML = "../HydraX - OLD stable version/symbols_map.yaml"

def migrate_servers_from_symbol_map():
    db = SessionLocal()
    try:
        distinct = set()
        for row in db.query(SymbolMap.broker_server).distinct().all():
            distinct.add(row[0])

        count = 0
        for name in sorted(distinct):
            if not db.query(Server).filter(Server.name == name).first():
                db.add(Server(name=name))
                count += 1
                print(f"  + {name}")

        db.commit()
        print(f"\n{count} servers importados.")
    finally:
        db.close()


def migrate_servers_from_yaml():
    db = SessionLocal()
    try:
        with open(OLD_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        servers_set = set()
        for base_symbol, servers_dict in data.items():
            if base_symbol == "tipo":
                continue
            for broker_server in servers_dict:
                if broker_server != "tipo":
                    servers_set.add(broker_server)

        count = 0
        for name in sorted(servers_set):
            if not db.query(Server).filter(Server.name == name).first():
                db.add(Server(name=name))
                count += 1
                print(f"  + {name}")

        db.commit()
        print(f"\n{count} servers importados desde el YAML.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Migrando servers desde la DB existente...")
    migrate_servers_from_symbol_map()
    print("\nMigrando servers desde el YAML antiguo...")
    migrate_servers_from_yaml()
