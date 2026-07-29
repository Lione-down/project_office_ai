from pathlib import Path

from sqlalchemy import UniqueConstraint

from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.media_job_inputs import MediaJobInput
from app.models.media_jobs import MediaJob
from app.models.provider_calls import ProviderCall
from app.models.workflow_tasks import WorkflowTask


def constraint_names(model) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_image_media_models_preserve_idempotent_immutable_relationships() -> None:
    assert "uq_media_jobs_user_idempotency" in constraint_names(MediaJob)
    assert "uq_media_job_inputs_job_source" in constraint_names(MediaJobInput)
    assert "uq_file_assets_media_job_role_version" in constraint_names(FileAsset)
    assert "uq_provider_calls_media_job_attempt" in constraint_names(ProviderCall)
    assert "generated_media_job_id" in FileAsset.__table__.c
    assert "media_job_id" in ProviderCall.__table__.c
    assert "media_job_id" in CreditLedger.__table__.c
    assert {"resource_kind", "resource_id"}.issubset(WorkflowTask.__table__.c.keys())


def test_p5_006_migration_is_additive_and_revises_template_catalog() -> None:
    path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "20260729_0019_image_media_assets.py"
    )
    source = path.read_text(encoding="utf-8")

    assert 'down_revision = "20260729_0018"' in source
    assert '"media_jobs"' in source
    assert '"media_job_inputs"' in source
    assert 'op.batch_alter_table("file_assets")' in source
    assert 'op.batch_alter_table("provider_calls")' in source
    assert 'op.batch_alter_table("workflow_tasks")' in source
    assert 'op.batch_alter_table("credit_ledger")' in source
