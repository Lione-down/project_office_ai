from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_evidence_migration_is_the_current_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260723_0007"]
    assert scripts.get_revision("20260723_0007").down_revision == "20260723_0006"


def test_evidence_metadata_migration_adds_only_bounded_manifest_fields(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "evidence.db"
    monkeypatch.setenv(
        "OFFICE_AI_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )
    get_settings.cache_clear()
    config = alembic_config()

    try:
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    columns = {
        column["name"]
        for column in inspect(create_engine(f"sqlite:///{database_path}")).get_columns(
            "file_assets"
        )
    }
    assert {
        "manifest_key",
        "manifest_status",
        "manifest_sha256",
        "manifest_schema_version",
        "evidence_engine_version",
        "evidence_warning_count",
        "evidence_blocker_count",
        "evidence_generated_at",
        "processing_retry_count",
        "processing_retry_after",
    }.issubset(columns)
