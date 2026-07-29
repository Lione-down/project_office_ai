from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.models.generation_task_inputs import GenerationTaskInput
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent
from app.models.provider_calls import ProviderCall
from app.settings.config import get_settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def test_generation_migration_is_single_additive_head() -> None:
    scripts = ScriptDirectory.from_config(alembic_config())

    assert scripts.get_heads() == ["20260729_0017"]
    assert scripts.get_revision("20260723_0011").down_revision == "20260723_0010"
    migration_source = (
        BACKEND_ROOT / "alembic/versions/20260723_0011_generation_outbox_credits.py"
    ).read_text(encoding="utf-8")
    assert migration_source.count('existing_comment="关联Brief稳定组ID"') == 2


def test_generation_models_expose_durable_contract() -> None:
    assert {
        "user_id",
        "brief_id",
        "credential_id",
        "idempotency_key",
        "status",
        "dispatch_sequence",
        "estimated_credits",
        "settled_credits",
        "timeout_at",
    } <= {column.key for column in GenerationTask.__table__.columns}
    assert {"task_id", "step_key", "status", "attempt", "checkpoint"} <= {
        column.key for column in GenerationTaskStep.__table__.columns
    }
    assert {"task_id", "input_type", "reference_key", "snapshot"} <= {
        column.key for column in GenerationTaskInput.__table__.columns
    }
    assert {
        "deduplication_key",
        "aggregate_id",
        "payload",
        "status",
        "retry_count",
        "next_attempt_at",
    } <= {column.key for column in OutboxEvent.__table__.columns}
    assert ProviderCall.__table__.c.brief_group_id.nullable is True
    assert ("task_step_id", "attempt") in {
        tuple(constraint.columns.keys())
        for constraint in ProviderCall.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }


def test_generation_migration_upgrades_empty_database(
    monkeypatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "generation.db"
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
    assert {
        "generation_tasks",
        "generation_task_steps",
        "generation_task_inputs",
        "outbox_events",
    } <= tables
    assert len(tables - {"alembic_version"}) == 28
    task_uniques = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("generation_tasks")
    }
    assert ("user_id", "idempotency_key") in task_uniques
    provider_call_uniques = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("provider_calls")
    }
    assert ("task_step_id", "attempt") in provider_call_uniques
