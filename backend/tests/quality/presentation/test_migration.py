from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.file_assets import FileAsset
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[3]
QUALITY_COLUMNS = {
    "quality_status",
    "quality_report_key",
    "quality_report_sha256",
    "quality_report_schema_version",
    "quality_engine_version",
    "quality_preview_keys",
    "quality_validated_key",
    "quality_validated_sha256",
    "quality_validated_byte_size",
    "quality_repair_attempt_count",
    "quality_checked_at",
}


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_quality_metadata_migration_is_single_additive_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260727_0015"]
    assert scripts.get_revision("20260723_0013").down_revision == "20260723_0012"


def test_file_asset_model_contains_versioned_quality_metadata() -> None:
    assert QUALITY_COLUMNS.issubset(FileAsset.__table__.columns.keys())


def test_quality_migration_upgrades_empty_database_without_adding_a_table(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "presentation-quality.db"
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
    columns = {item["name"] for item in inspector.get_columns("file_assets")}

    assert len(set(inspector.get_table_names()) - {"alembic_version"}) == 22
    assert QUALITY_COLUMNS.issubset(columns)
