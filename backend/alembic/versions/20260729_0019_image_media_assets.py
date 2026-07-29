"""Add Agnes image media jobs and immutable output relationships.

Revision ID: 20260729_0019
Revises: 20260729_0018
Create Date: 2026-07-29 17:50:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260729_0019"
down_revision = "20260729_0018"
branch_labels = None
depends_on = None


def _uuid():
    return sa.BINARY(16)


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    jobs = op.create_table(
        "media_jobs",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("project_id", _uuid(), nullable=False),
        sa.Column("draft_revision_id", _uuid(), nullable=False),
        sa.Column("slide_id", _uuid(), nullable=False),
        sa.Column("workflow_task_id", _uuid(), nullable=False),
        sa.Column("supersedes_job_id", _uuid(), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("prompt_content", sa.Text(), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("alt_text", sa.String(500), nullable=False),
        sa.Column("crop_mode", sa.String(16), nullable=False),
        sa.Column("provider_id", _uuid(), nullable=False),
        sa.Column("credential_id", _uuid(), nullable=False),
        sa.Column("model_id", _uuid(), nullable=False),
        sa.Column("model_snapshot", sa.JSON(), nullable=False),
        sa.Column("capability_snapshot", sa.JSON(), nullable=False),
        sa.Column("pricing_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("provider_job_id", sa.String(255), nullable=True),
        sa.Column("requested_size", sa.String(16), nullable=False),
        sa.Column("requested_ratio", sa.String(16), nullable=False),
        sa.Column("actual_width", sa.Integer(), nullable=True),
        sa.Column("actual_height", sa.Integer(), nullable=True),
        sa.Column("output_sha256", sa.String(64), nullable=True),
        sa.Column("output_asset_version", sa.Integer(), nullable=True),
        sa.Column("estimated_credits", sa.Integer(), nullable=False),
        sa.Column("reserved_credits", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("cancel_requested_at", _utc_datetime(), nullable=True),
        sa.Column("submitted_at", _utc_datetime(), nullable=True),
        sa.Column("completed_at", _utc_datetime(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_media_jobs_user"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_media_jobs_project"
        ),
        sa.ForeignKeyConstraint(
            ["draft_revision_id"],
            ["deck_draft_revisions.id"],
            name="fk_media_jobs_deck_revision",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_task_id"],
            ["workflow_tasks.id"],
            name="fk_media_jobs_workflow_task",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_job_id"],
            ["media_jobs.id"],
            name="fk_media_jobs_supersedes",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["ai_providers.id"], name="fk_media_jobs_provider"
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["provider_credentials.id"],
            name="fk_media_jobs_credential",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["ai_models.id"], name="fk_media_jobs_model"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_media_jobs_user_idempotency"
        ),
        sa.UniqueConstraint(
            "provider_id", "provider_job_id", name="uq_media_jobs_provider_job"
        ),
        sa.UniqueConstraint("workflow_task_id", name="uq_media_jobs_workflow_task"),
        comment="Owner-scoped媒体生成任务",
    )
    for name, columns in (
        ("ix_media_jobs_user_id", ["user_id"]),
        ("ix_media_jobs_project_id", ["project_id"]),
        ("ix_media_jobs_draft_revision_id", ["draft_revision_id"]),
        ("ix_media_jobs_slide_id", ["slide_id"]),
        ("ix_media_jobs_supersedes_job_id", ["supersedes_job_id"]),
        ("ix_media_jobs_provider_id", ["provider_id"]),
        ("ix_media_jobs_model_id", ["model_id"]),
        ("ix_media_jobs_status", ["status"]),
    ):
        op.create_index(name, jobs.name, columns)

    inputs = op.create_table(
        "media_job_inputs",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("media_job_id", _uuid(), nullable=False),
        sa.Column("input_kind", sa.String(32), nullable=False),
        sa.Column("source_asset_id", _uuid(), nullable=False),
        sa.Column("source_asset_version", sa.Integer(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("slide_id", _uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_job_id"], ["media_jobs.id"], name="fk_media_job_inputs_job"
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["file_assets.id"],
            name="fk_media_job_inputs_asset",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_job_id",
            "input_kind",
            "source_asset_id",
            "sequence",
            name="uq_media_job_inputs_job_source",
        ),
        comment="媒体任务不可变输入关系",
    )
    op.create_index("ix_media_job_inputs_media_job_id", inputs.name, ["media_job_id"])
    op.create_index(
        "ix_media_job_inputs_source_asset_id", inputs.name, ["source_asset_id"]
    )

    with op.batch_alter_table("file_assets") as batch:
        batch.add_column(sa.Column("generated_media_job_id", _uuid(), nullable=True))
        batch.add_column(sa.Column("media_role", sa.String(32), nullable=True))
        batch.add_column(
            sa.Column("asset_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("media_width", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("media_height", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("media_metadata", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_file_assets_generated_media_job",
            "media_jobs",
            ["generated_media_job_id"],
            ["id"],
        )
        batch.create_index(
            "ix_file_assets_generated_media_job_id",
            ["generated_media_job_id"],
        )
        batch.create_unique_constraint(
            "uq_file_assets_media_job_role_version",
            ["generated_media_job_id", "media_role", "asset_version"],
        )

    with op.batch_alter_table("provider_calls") as batch:
        batch.add_column(sa.Column("media_job_id", _uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_provider_calls_media_job",
            "media_jobs",
            ["media_job_id"],
            ["id"],
        )
        batch.create_index("ix_provider_calls_media_job_id", ["media_job_id"])
        batch.create_unique_constraint(
            "uq_provider_calls_media_job_attempt",
            ["media_job_id", "attempt"],
        )

    with op.batch_alter_table("workflow_tasks") as batch:
        batch.add_column(sa.Column("resource_kind", sa.String(32), nullable=True))
        batch.add_column(sa.Column("resource_id", _uuid(), nullable=True))
        batch.create_index("ix_workflow_tasks_resource_kind", ["resource_kind"])
        batch.create_index("ix_workflow_tasks_resource_id", ["resource_id"])

    with op.batch_alter_table("credit_ledger") as batch:
        batch.add_column(sa.Column("media_job_id", _uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_credit_ledger_media_job",
            "media_jobs",
            ["media_job_id"],
            ["id"],
        )
        batch.create_index("ix_credit_ledger_media_job_id", ["media_job_id"])


def downgrade() -> None:
    with op.batch_alter_table("credit_ledger") as batch:
        batch.drop_index("ix_credit_ledger_media_job_id")
        batch.drop_constraint("fk_credit_ledger_media_job", type_="foreignkey")
        batch.drop_column("media_job_id")
    with op.batch_alter_table("workflow_tasks") as batch:
        batch.drop_index("ix_workflow_tasks_resource_id")
        batch.drop_index("ix_workflow_tasks_resource_kind")
        batch.drop_column("resource_id")
        batch.drop_column("resource_kind")
    with op.batch_alter_table("provider_calls") as batch:
        batch.drop_constraint("uq_provider_calls_media_job_attempt", type_="unique")
        batch.drop_index("ix_provider_calls_media_job_id")
        batch.drop_constraint("fk_provider_calls_media_job", type_="foreignkey")
        batch.drop_column("media_job_id")
    with op.batch_alter_table("file_assets") as batch:
        batch.drop_constraint("uq_file_assets_media_job_role_version", type_="unique")
        batch.drop_index("ix_file_assets_generated_media_job_id")
        batch.drop_constraint("fk_file_assets_generated_media_job", type_="foreignkey")
        for column in (
            "media_metadata",
            "media_height",
            "media_width",
            "asset_version",
            "media_role",
            "generated_media_job_id",
        ):
            batch.drop_column(column)
    op.drop_index("ix_media_job_inputs_source_asset_id", table_name="media_job_inputs")
    op.drop_index("ix_media_job_inputs_media_job_id", table_name="media_job_inputs")
    op.drop_table("media_job_inputs")
    for index in (
        "ix_media_jobs_status",
        "ix_media_jobs_model_id",
        "ix_media_jobs_provider_id",
        "ix_media_jobs_supersedes_job_id",
        "ix_media_jobs_slide_id",
        "ix_media_jobs_draft_revision_id",
        "ix_media_jobs_project_id",
        "ix_media_jobs_user_id",
    ):
        op.drop_index(index, table_name="media_jobs")
    op.drop_table("media_jobs")
