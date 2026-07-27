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


def test_terminology_migration_precedes_the_current_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260727_0015"]
    assert scripts.get_revision("20260723_0008").down_revision == "20260723_0007"
    assert scripts.get_revision("20260723_0009").down_revision == "20260723_0008"
    assert scripts.get_revision("20260723_0010").down_revision == "20260723_0009"


def test_terminology_migration_adds_versioned_library_tables(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "terminology.db"
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
    assert {"term_libraries", "term_items"} <= set(inspector.get_table_names())
    library_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("term_libraries")
    }
    item_uniques = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("term_items")
    }

    assert "uq_term_libraries_library_version" in library_uniques
    assert "uq_term_items_snapshot_item" in item_uniques
