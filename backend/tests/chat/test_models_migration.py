from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.chat_messages import ChatMessage
from app.models.chat_runs import ChatRun
from app.models.chat_threads import ChatThread
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_chat_models_expose_frozen_owner_history_and_run_contract() -> None:
    assert {
        "user_id",
        "title",
        "default_model_id",
        "mode",
        "status",
        "last_activity_at",
        "retention_expires_at",
        "deleted_at",
    } <= {column.key for column in ChatThread.__table__.columns}
    assert {
        "thread_id",
        "sequence",
        "role",
        "content",
        "status",
        "parent_message_id",
        "supersedes_message_id",
        "branch_root_id",
        "run_id",
    } <= {column.key for column in ChatMessage.__table__.columns}
    assert {
        "user_id",
        "thread_id",
        "user_message_id",
        "assistant_message_id",
        "idempotency_key",
        "request_fingerprint",
        "status",
        "last_event_sequence",
        "provider_snapshot",
        "capability_snapshot",
        "pricing_snapshot",
        "thinking_enabled",
        "cancel_requested_at",
        "error_code",
    } <= {column.key for column in ChatRun.__table__.columns}


def test_chat_migration_is_additive_head_and_upgrades_empty_database(
    monkeypatch,
    tmp_path: Path,
) -> None:
    scripts = ScriptDirectory.from_config(alembic_config())
    assert scripts.get_heads() == ["20260729_0016"]
    assert scripts.get_revision("20260729_0016").down_revision == "20260727_0015"

    database_path = tmp_path / "chat-migration.db"
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
    assert {
        "chat_threads",
        "chat_messages",
        "chat_runs",
    } <= set(inspector.get_table_names())
    assert len(set(inspector.get_table_names()) - {"alembic_version"}) == 25
    run_uniques = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("chat_runs")
    }
    assert ("user_id", "idempotency_key") in run_uniques
    assert ("assistant_message_id",) in run_uniques
    assert "chat_run_id" in {
        column["name"] for column in inspector.get_columns("provider_calls")
    }
