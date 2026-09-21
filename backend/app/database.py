from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

from app.config import settings

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    } if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import account, ticket_map, trade_log, event_log, server, symbol_map  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_slave_ticket()
    _migrate_add_color()
    _migrate_copy_enable()
    _migrate_template_id()
    _migrate_daily_limits()
    _migrate_slave_templates()
    _migrate_platform()
    _migrate_mt5_risk()


def _migrate_slave_ticket():
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(
                "SELECT type FROM pragma_table_info('ticket_map') WHERE name='slave_ticket'"
            ).fetchone()
            if result and result[0].upper() == "INTEGER":
                from app.utils.logger import get_logger
                logger = get_logger("hydrax.db")
                logger.info("Migrating ticket_map.slave_ticket from INTEGER to TEXT")
                conn.exec_driver_sql("ALTER TABLE ticket_map ADD COLUMN slave_ticket_tmp TEXT")
                conn.exec_driver_sql("UPDATE ticket_map SET slave_ticket_tmp = CAST(slave_ticket AS TEXT)")
                conn.exec_driver_sql("ALTER TABLE ticket_map DROP COLUMN slave_ticket")
                conn.exec_driver_sql("ALTER TABLE ticket_map RENAME COLUMN slave_ticket_tmp TO slave_ticket")
                conn.commit()
    except Exception:
        pass


def _migrate_add_color():
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(
                "SELECT name FROM pragma_table_info('accounts') WHERE name='color'"
            ).fetchone()
            if not result:
                from app.utils.logger import get_logger
                logger = get_logger("hydrax.db")
                logger.info("Migrating: adding accounts.color column")
                conn.exec_driver_sql("ALTER TABLE accounts ADD COLUMN color VARCHAR(7) DEFAULT '#3b82f6'")
                conn.commit()
    except Exception:
        pass


def _migrate_copy_enable():
    """Add copy_enable to accounts, copy_modify to slave_config and slave_templates."""
    try:
        with engine.connect() as conn:
            for col, table in [("copy_enable", "accounts"), ("copy_modify", "slave_config"), ("copy_modify", "slave_templates"), ("sync_close", "slave_config"), ("sync_close", "slave_templates")]:
                result = conn.exec_driver_sql(
                    f"SELECT name FROM pragma_table_info('{table}') WHERE name='{col}'"
                ).fetchone()
                if not result:
                    from app.utils.logger import get_logger
                    logger = get_logger("hydrax.db")
                    logger.info(f"Migrating: adding {table}.{col} column")
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} BOOLEAN DEFAULT 1")
                conn.commit()
    except Exception:
        pass


def _migrate_template_id():
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(
                "SELECT name FROM pragma_table_info('slave_config') WHERE name='template_id'"
            ).fetchone()
            if not result:
                from app.utils.logger import get_logger
                logger = get_logger("hydrax.db")
                logger.info("Migrating: adding slave_config.template_id column")
                conn.exec_driver_sql("ALTER TABLE slave_config ADD COLUMN template_id VARCHAR(36) DEFAULT NULL")
                conn.commit()
    except Exception:
        pass


def _migrate_slave_templates():
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='slave_templates'"
            ).fetchone()
            if not result:
                from app.utils.logger import get_logger
                logger = get_logger("hydrax.db")
                logger.info("Migrating: creating slave_templates table")
                Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["slave_templates"]])
                conn.commit()
    except Exception:
        pass


def _migrate_daily_limits():
    try:
        with engine.connect() as conn:
            for col, table in [
                ("daily_loss_enabled", "slave_config"), ("daily_loss_limit", "slave_config"),
                ("daily_profit_enabled", "slave_config"), ("daily_profit_limit", "slave_config"),
                ("daily_pnl", "slave_config"), ("last_pnl_reset", "slave_config"),
                ("daily_loss_enabled", "slave_templates"), ("daily_loss_limit", "slave_templates"),
                ("daily_profit_enabled", "slave_templates"), ("daily_profit_limit", "slave_templates"),
                ("paused_by_limit", "slave_config"),
                ("daily_loss_mode", "slave_config"), ("daily_profit_mode", "slave_config"),
                ("daily_loss_mode", "slave_templates"), ("daily_profit_mode", "slave_templates"),
            ]:
                result = conn.exec_driver_sql(f"SELECT name FROM pragma_table_info('{table}') WHERE name='{col}'").fetchone()
                if not result:
                    from app.utils.logger import get_logger
                    log = get_logger("hydrax.db")
                    log.info(f"Migrating: adding {table}.{col}")
                    dt = "BOOLEAN DEFAULT 0" if ("enabled" in col or col == "paused_by_limit") else ("VARCHAR(10) DEFAULT 'USD'" if "mode" in col else "FLOAT DEFAULT 0.0")
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {dt}")
                    conn.commit()
            c2 = conn.exec_driver_sql("SELECT last_pnl_reset FROM slave_config WHERE last_pnl_reset IS NOT NULL AND typeof(last_pnl_reset) != 'text'").fetchone()
            if c2:
                conn.exec_driver_sql("UPDATE slave_config SET last_pnl_reset = NULL WHERE typeof(last_pnl_reset) != 'text'")
                conn.commit()
    except Exception:
        pass


def _migrate_platform():
    """Add platform/server/terminal_path to accounts (hybrid NT8 + MT5)."""
    try:
        with engine.connect() as conn:
            columns = {
                "platform": "ALTER TABLE accounts ADD COLUMN platform VARCHAR(10) DEFAULT 'NT8'",
                "server": "ALTER TABLE accounts ADD COLUMN server VARCHAR(100) DEFAULT NULL",
                "terminal_path": "ALTER TABLE accounts ADD COLUMN terminal_path VARCHAR(300) DEFAULT NULL",
                "filling_mode": "ALTER TABLE accounts ADD COLUMN filling_mode VARCHAR(10) DEFAULT NULL",
            }
            for col, ddl in columns.items():
                result = conn.exec_driver_sql(
                    f"SELECT name FROM pragma_table_info('accounts') WHERE name='{col}'"
                ).fetchone()
                if not result:
                    from app.utils.logger import get_logger
                    logger = get_logger("hydrax.db")
                    logger.info(f"Migrating: adding accounts.{col} column")
                    conn.exec_driver_sql(ddl)
                    conn.commit()
    except Exception:
        pass


def _migrate_mt5_risk():
    """MT5 risk: modo FIXED_CONTRACTS/FIXED_LOTS + columnas fixed_lots/max_lots."""
    try:
        with engine.connect() as conn:
            for table in ("slave_config", "slave_templates"):
                for col, ddl in [
                    ("fixed_lots", f"ALTER TABLE {table} ADD COLUMN fixed_lots FLOAT DEFAULT 0.01"),
                    ("max_lots", f"ALTER TABLE {table} ADD COLUMN max_lots FLOAT DEFAULT 10.0"),
                ]:
                    result = conn.exec_driver_sql(
                        f"SELECT name FROM pragma_table_info('{table}') WHERE name='{col}'"
                    ).fetchone()
                    if not result:
                        from app.utils.logger import get_logger
                        logger = get_logger("hydrax.db")
                        logger.info(f"Migrating: adding {table}.{col} column")
                        conn.exec_driver_sql(ddl)
                        conn.commit()
            conn.exec_driver_sql(
                "UPDATE slave_config SET risk_mode='FIXED_CONTRACTS' WHERE risk_mode='FIXED'"
            )
            conn.exec_driver_sql(
                "UPDATE slave_templates SET risk_mode='FIXED_CONTRACTS' WHERE risk_mode='FIXED'"
            )
            conn.commit()
    except Exception:
        pass
