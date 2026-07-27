from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.workflow_tasks import WorkflowTask
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_workflow_task_model_exposes_durable_failure_contract() -> None:
    assert {
        "user_id",
        "project_id",
        "brief_group_id",
        "generation_task_id",
        "idempotency_key",
        "request_snapshot",
        "output_kinds",
        "stage",
        "status",
        "progress",
        "note",
        "failure_code",
        "failure_reason",
        "dispatch_sequence",
        "last_enqueued_at",
        "started_at",
        "completed_at",
    } <= {column.key for column in WorkflowTask.__table__.columns}


def test_workflow_task_migration_is_additive_head_and_upgrades_empty_database(
    monkeypatch,
    tmp_path: Path,
) -> None:
    scripts = ScriptDirectory.from_config(alembic_config())
    assert scripts.get_heads() == ["20260727_0015"]
    assert scripts.get_revision("20260727_0015").down_revision == "20260727_0014"

    database_path = tmp_path / "workflow-tasks.db"
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
    assert "workflow_tasks" in inspector.get_table_names()
    assert len(set(inspector.get_table_names()) - {"alembic_version"}) == 22
    uniques = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("workflow_tasks")
    }
    assert ("user_id", "idempotency_key") in uniques
    assert ("generation_task_id",) in uniques
