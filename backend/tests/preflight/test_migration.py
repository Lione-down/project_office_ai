from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.briefs import Brief
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_preflight_migration_is_the_current_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0016"]
    assert scripts.get_revision("20260723_0010").down_revision == "20260723_0009"


def test_brief_model_exposes_preflight_snapshot_and_estimated_credits() -> None:
    assert {"preflight_snapshot", "estimated_credits"} <= {
        column.key for column in Brief.__table__.columns
    }


def test_preflight_migration_adds_only_brief_snapshot_columns(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "preflight.db"
    monkeypatch.setenv(
        "OFFICE_AI_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )
    get_settings.cache_clear()
    try:
        command.upgrade(alembic_config(), "20260723_0010")
    finally:
        get_settings.cache_clear()

    inspector = inspect(create_engine(f"sqlite:///{database_path}"))
    columns = {column["name"] for column in inspector.get_columns("briefs")}
    tables = set(inspector.get_table_names())

    assert {"preflight_snapshot", "estimated_credits"} <= columns
    assert "generation_tasks" not in tables
    assert "outbox_events" not in tables
