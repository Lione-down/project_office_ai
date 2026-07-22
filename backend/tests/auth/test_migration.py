from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path
from sqlalchemy import create_engine, inspect

from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_auth_migration_upgrades_empty_database(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "auth-migration.sqlite3"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("OFFICE_AI_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config()

    try:
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    tables = set(inspect(create_engine(f"sqlite:///{database_path}")).get_table_names())
    assert {"users", "user_sessions", "invite_codes", "credit_ledger"} <= tables


def test_auth_migration_is_the_single_head() -> None:
    config = alembic_config()

    heads = ScriptDirectory.from_config(config).get_heads()

    assert heads == ["20260722_0002"]
