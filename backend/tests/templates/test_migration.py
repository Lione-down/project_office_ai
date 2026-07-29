from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_template_catalog_migration_is_the_current_single_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0019"]
    assert scripts.get_revision("20260729_0018").down_revision == "20260729_0017"


def test_template_catalog_migration_seeds_three_certified_ppt_versions(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "templates.db"
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
    columns = {item["name"] for item in inspect(engine).get_columns("templates")}
    assert "checksum" in columns
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT template_code, version, checksum, source, status "
                "FROM templates WHERE template_type = 'pptx' "
                "ORDER BY sort_order, template_code"
            )
        ).all()

    assert [row[0] for row in rows] == [
        "ppt.executive-blue.v1",
        "ppt.operating-review.v1",
        "ppt.data-story.v1",
    ]
    assert all(
        row[1] == 1
        and len(row[2]) == 64
        and row[3] == "system_original"
        and row[4] == "published"
        for row in rows
    )
