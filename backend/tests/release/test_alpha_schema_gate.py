from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models import Base
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ALPHA_TABLES = {
    "ai_models",
    "ai_providers",
    "audit_logs",
    "briefs",
    "credit_ledger",
    "file_assets",
    "generation_task_inputs",
    "generation_task_steps",
    "generation_tasks",
    "invite_codes",
    "outbox_events",
    "projects",
    "provider_calls",
    "provider_credentials",
    "skills",
    "system_settings",
    "templates",
    "term_items",
    "term_libraries",
    "user_sessions",
    "users",
}
EXPECTED_CURRENT_TABLES = EXPECTED_ALPHA_TABLES | {
    "workflow_tasks",
    "chat_threads",
    "chat_messages",
    "chat_runs",
    "deck_drafts",
    "deck_draft_revisions",
    "deck_draft_inputs",
}


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_current_metadata_preserves_alpha_tables_and_adds_post_alpha_tables() -> None:
    assert EXPECTED_ALPHA_TABLES < set(Base.metadata.tables)
    assert set(Base.metadata.tables) == EXPECTED_CURRENT_TABLES


def test_current_head_upgrades_empty_database_to_twenty_eight_tables(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "alpha-schema-gate.sqlite3"
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
    template_uniques = {
        item["name"] for item in inspector.get_unique_constraints("templates")
    }
    setting_uniques = {
        item["name"] for item in inspector.get_unique_constraints("system_settings")
    }

    assert tables == EXPECTED_CURRENT_TABLES | {"alembic_version"}
    assert "uq_templates_source_code_version" in template_uniques
    assert "uq_system_settings_key" in setting_uniques


def test_alpha_schema_remains_a_single_head_chain() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0018"]
    assert scripts.get_revision("20260729_0017").down_revision == "20260729_0016"
    assert scripts.get_revision("20260729_0016").down_revision == "20260727_0015"
    assert scripts.get_revision("20260727_0015").down_revision == "20260727_0014"
    assert scripts.get_revision("20260727_0014").down_revision == "20260723_0013"
