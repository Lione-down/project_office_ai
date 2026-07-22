from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path
from io import StringIO
from sqlalchemy import create_engine, inspect

from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def alembic_offline_config(output_buffer: StringIO) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output_buffer)
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


def test_auth_migration_remains_in_provider_revision_chain() -> None:
    config = alembic_config()
    scripts = ScriptDirectory.from_config(config)

    provider_revision = scripts.get_revision("20260722_0004")

    assert scripts.get_revision("20260722_0003") is not None
    assert provider_revision.down_revision == "20260722_0003"


def test_auth_comment_migration_emits_mysql_chinese_comments(monkeypatch) -> None:
    monkeypatch.delenv("OFFICE_AI_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    output = StringIO()

    try:
        command.upgrade(alembic_offline_config(output), "head", sql=True)
    finally:
        get_settings.cache_clear()

    sql = output.getvalue()
    assert "用户账号表" in sql
    assert "用户手机号" in sql
    assert "刷新令牌哈希" in sql
    assert "邀请码哈希" in sql
    assert "积分流水类型" in sql
