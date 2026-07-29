from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.file_assets import FileAsset
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[3]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_presentation_output_migration_is_single_additive_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0019"]
    assert scripts.get_revision("20260723_0012").down_revision == "20260723_0011"


def test_file_asset_generation_task_link_has_named_foreign_key() -> None:
    foreign_keys = {
        foreign_key.name: foreign_key
        for foreign_key in FileAsset.__table__.foreign_keys
    }

    assert "fk_file_assets_generated_task" in foreign_keys
    assert (
        foreign_keys["fk_file_assets_generated_task"].target_fullname
        == "generation_tasks.id"
    )


def test_migration_upgrades_empty_database_without_adding_a_table(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "presentation-output.db"
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
    foreign_keys = {
        item["name"]: item for item in inspector.get_foreign_keys("file_assets")
    }

    assert len(set(inspector.get_table_names()) - {"alembic_version"}) == 30
    assert foreign_keys["fk_file_assets_generated_task"]["referred_table"] == (
        "generation_tasks"
    )
    assert foreign_keys["fk_file_assets_generated_task"]["constrained_columns"] == [
        "generated_task_id"
    ]
