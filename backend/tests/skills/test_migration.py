from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.settings.config import get_settings
from app.skills.catalog import ALPHA_SKILLS


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_brief_migration_is_the_current_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0016"]
    assert scripts.get_revision("20260723_0009").down_revision == "20260723_0008"


def test_brief_migration_is_self_contained_from_runtime_application_code() -> None:
    migration = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "20260723_0009_skills_and_structured_briefs.py"
    ).read_text(encoding="utf-8")

    assert "from app." not in migration
    assert "import app." not in migration


def test_brief_migration_adds_tables_and_seeds_exact_alpha_skills(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "briefs.db"
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
    assert {"skills", "briefs", "provider_calls"} <= set(inspector.get_table_names())
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT skill_code, version, checksum "
                "FROM skills ORDER BY skill_code DESC"
            )
        ).all()

    assert rows == [
        (skill.skill_code, skill.version, skill.checksum) for skill in ALPHA_SKILLS
    ]
