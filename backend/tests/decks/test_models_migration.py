from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.settings.config import get_settings
from app.skills.catalog import KNOWLEDGE_EDUCATION_SKILL


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_deck_migration_is_the_current_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0018"]
    assert scripts.get_revision("20260729_0017").down_revision == "20260729_0016"


def test_deck_migration_adds_three_tables_and_knowledge_skill(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "decks.db"
    monkeypatch.setenv(
        "OFFICE_AI_DATABASE_URL",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )
    get_settings.cache_clear()
    try:
        command.upgrade(alembic_config(), "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert {
        "deck_drafts",
        "deck_draft_revisions",
        "deck_draft_inputs",
    } <= set(inspector.get_table_names())
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT skill_code, version, checksum FROM skills "
                "WHERE skill_code = 'ppt.knowledge-education.v1'"
            )
        ).one()

    assert row == (
        KNOWLEDGE_EDUCATION_SKILL.skill_code,
        KNOWLEDGE_EDUCATION_SKILL.version,
        KNOWLEDGE_EDUCATION_SKILL.checksum,
    )
