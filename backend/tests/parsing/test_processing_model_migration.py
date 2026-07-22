from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.file_assets import FileAsset
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(output_buffer: StringIO | None = None) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_file_asset_records_safe_processing_metadata() -> None:
    columns = set(FileAsset.__table__.columns.keys())

    assert {
        "parsed_storage_key",
        "parser_name",
        "parser_version",
        "processing_warnings",
        "processing_error_code",
        "processing_error_message",
        "processing_started_at",
        "processed_at",
    } <= columns


def test_processing_migration_upgrades_empty_database(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "processing-migration.sqlite3"
    monkeypatch.setenv(
        "OFFICE_AI_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )
    get_settings.cache_clear()

    try:
        command.upgrade(alembic_config(), "head")
    finally:
        get_settings.cache_clear()

    columns = {
        item["name"]
        for item in inspect(create_engine(f"sqlite:///{database_path}")).get_columns(
            "file_assets"
        )
    }
    assert {
        "parsed_storage_key",
        "parser_name",
        "parser_version",
        "processing_warnings",
        "processing_error_code",
        "processing_error_message",
        "processing_started_at",
        "processed_at",
    } <= columns


def test_processing_migration_is_single_head_and_emits_mysql_comments(
    monkeypatch,
) -> None:
    assert ScriptDirectory.from_config(alembic_config()).get_heads() == [
        "20260723_0006"
    ]
    monkeypatch.delenv("OFFICE_AI_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    output = StringIO()

    try:
        command.upgrade(alembic_config(output), "head", sql=True)
    finally:
        get_settings.cache_clear()

    sql = output.getvalue()
    assert "解析结果存储键" in sql
    assert "脱敏处理错误" in sql
