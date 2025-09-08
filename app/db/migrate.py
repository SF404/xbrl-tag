# app/db/migrate.py
from pathlib import Path
from alembic import command
from alembic.config import Config
from app.core.config import get_config

def run_migrations() -> None:
    root = Path(__file__).resolve().parents[2]  # .../app/db
    alembic_ini = root / "alembic.ini"
    alembic_dir = root / "alembic"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", get_config().database_url)

    command.upgrade(cfg, "head")
