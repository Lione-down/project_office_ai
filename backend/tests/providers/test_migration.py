from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(output_buffer: StringIO | None = None) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_provider_migration_upgrades_empty_database(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "provider-migration.sqlite3"
    monkeypatch.setenv(
        "OFFICE_AI_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )
    get_settings.cache_clear()

    try:
        command.upgrade(alembic_config(), "head")
    finally:
        get_settings.cache_clear()

    inspector = inspect(create_engine(f"sqlite:///{database_path}"))
    tables = set(inspector.get_table_names())
    credential_uniques = {
        item["name"]
        for item in inspector.get_unique_constraints("provider_credentials")
    }
    model_uniques = {
        item["name"] for item in inspector.get_unique_constraints("ai_models")
    }

    assert {
        "ai_providers",
        "provider_credentials",
        "ai_models",
        "audit_logs",
    } <= tables
    assert "uq_provider_credentials_provider_fingerprint" in credential_uniques
    assert "uq_ai_models_provider_code_credential" in model_uniques


def test_provider_migration_remains_in_the_single_head_chain() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())
    heads = scripts.get_heads()

    assert heads == ["20260722_0005"]
    assert scripts.get_revision("20260722_0005").down_revision == "20260722_0004"


def test_provider_migration_emits_mysql_chinese_comments(monkeypatch) -> None:
    monkeypatch.delenv("OFFICE_AI_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    output = StringIO()

    try:
        command.upgrade(alembic_config(output), "head", sql=True)
    finally:
        get_settings.cache_clear()

    sql = output.getvalue()
    assert "AI Provider配置表" in sql
    assert "应用层加密API Key" in sql
    assert "允许的Skill代码" in sql
    assert "脱敏上下文" in sql
