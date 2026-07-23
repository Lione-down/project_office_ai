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


def test_asset_migration_upgrades_empty_database(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "asset-migration.sqlite3"
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
    unique_constraints = {
        item["name"] for item in inspector.get_unique_constraints("file_assets")
    }
    project_unique_constraints = {
        item["name"] for item in inspector.get_unique_constraints("projects")
    }

    assert {"projects", "file_assets"} <= tables
    assert "uq_file_assets_storage_location" in unique_constraints
    assert "uq_file_assets_user_idempotency" in unique_constraints
    assert "uq_projects_active_default_owner" in project_unique_constraints


def test_asset_migration_is_the_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert len(scripts.get_heads()) == 1
    assert scripts.get_revision("20260722_0005").down_revision == "20260722_0004"


def test_asset_migration_emits_mysql_chinese_comments(monkeypatch) -> None:
    monkeypatch.delenv("OFFICE_AI_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    output = StringIO()

    try:
        command.upgrade(alembic_config(output), "head", sql=True)
    finally:
        get_settings.cache_clear()

    sql = output.getvalue()
    assert "用户项目表" in sql
    assert "文件资产表" in sql
    assert "存储定位键" in sql
