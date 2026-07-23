"""Add durable generation tasks, Outbox, and credit task linkage.

Revision ID: 20260723_0011
Revises: 20260723_0010
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260723_0011"
down_revision: str | None = "20260723_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "generation_tasks",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="生成任务ID"),
        sa.Column("user_id", sa.BINARY(16), nullable=False, comment="所属用户ID"),
        sa.Column("project_id", sa.BINARY(16), nullable=False, comment="所属项目ID"),
        sa.Column(
            "brief_id", sa.BINARY(16), nullable=False, comment="确认的Brief修订行ID"
        ),
        sa.Column("model_id", sa.BINARY(16), nullable=False, comment="锁定模型ID"),
        sa.Column(
            "credential_id", sa.BINARY(16), nullable=False, comment="锁定Credential ID"
        ),
        sa.Column(
            "idempotency_key",
            sa.String(128),
            nullable=False,
            comment="用户请求幂等键",
        ),
        sa.Column(
            "combination_group_id",
            sa.BINARY(16),
            nullable=True,
            comment="组合任务稳定组ID",
        ),
        sa.Column("parent_task_id", sa.BINARY(16), nullable=True, comment="父任务ID"),
        sa.Column("status", sa.String(32), nullable=False, comment="任务状态"),
        sa.Column("progress", sa.Integer(), nullable=False, comment="任务进度百分比"),
        sa.Column(
            "skill_snapshot", sa.JSON(), nullable=False, comment="Skill不可变快照"
        ),
        sa.Column(
            "model_snapshot", sa.JSON(), nullable=False, comment="模型配置不可变快照"
        ),
        sa.Column(
            "estimated_credits", sa.Integer(), nullable=False, comment="预留积分"
        ),
        sa.Column(
            "settled_credits", sa.Integer(), nullable=False, comment="已结算成功积分"
        ),
        sa.Column(
            "retry_count", sa.Integer(), nullable=False, comment="任务级重试次数"
        ),
        sa.Column(
            "dispatch_sequence", sa.Integer(), nullable=False, comment="Outbox投递序号"
        ),
        sa.Column(
            "error_category", sa.String(64), nullable=True, comment="脱敏错误分类"
        ),
        sa.Column("error_message", sa.Text(), nullable=True, comment="脱敏错误说明"),
        sa.Column(
            "cancel_requested_at",
            _utc_datetime(),
            nullable=True,
            comment="取消请求时间（UTC）",
        ),
        sa.Column(
            "timeout_at",
            _utc_datetime(),
            nullable=False,
            comment="完整任务超时时间（UTC）",
        ),
        sa.Column(
            "last_enqueued_at",
            _utc_datetime(),
            nullable=False,
            comment="最近生成Outbox时间（UTC）",
        ),
        sa.Column(
            "started_at", _utc_datetime(), nullable=True, comment="首次开始时间（UTC）"
        ),
        sa.Column(
            "completed_at",
            _utc_datetime(),
            nullable=True,
            comment="终态完成时间（UTC）",
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["brief_id"], ["briefs.id"], name="fk_generation_tasks_brief"
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["provider_credentials.id"],
            name="fk_generation_tasks_credential",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["ai_models.id"], name="fk_generation_tasks_model"
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"],
            ["generation_tasks.id"],
            name="fk_generation_tasks_parent",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_generation_tasks_project"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_generation_tasks_user"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_generation_tasks_user_idempotency",
        ),
        comment="持久生成任务表",
    )
    for name, columns in (
        ("ix_generation_tasks_user_id", ["user_id"]),
        ("ix_generation_tasks_project_id", ["project_id"]),
        ("ix_generation_tasks_brief_id", ["brief_id"]),
        ("ix_generation_tasks_credential_id", ["credential_id"]),
        ("ix_generation_tasks_combination_group_id", ["combination_group_id"]),
        ("ix_generation_tasks_status", ["status"]),
    ):
        op.create_index(name, "generation_tasks", columns)

    op.create_table(
        "generation_task_steps",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="任务阶段ID"),
        sa.Column("task_id", sa.BINARY(16), nullable=False, comment="生成任务ID"),
        sa.Column("step_key", sa.String(128), nullable=False, comment="稳定阶段键"),
        sa.Column("output_kind", sa.String(16), nullable=False, comment="子输出类型"),
        sa.Column("status", sa.String(32), nullable=False, comment="阶段状态"),
        sa.Column("attempt", sa.Integer(), nullable=False, comment="已执行次数"),
        sa.Column(
            "estimated_credits", sa.Integer(), nullable=False, comment="子输出预计积分"
        ),
        sa.Column(
            "checkpoint", sa.JSON(), nullable=False, comment="安全恢复Checkpoint"
        ),
        sa.Column(
            "provider_request_id",
            sa.String(255),
            nullable=True,
            comment="Provider Request ID",
        ),
        sa.Column(
            "token_estimate", sa.Integer(), nullable=False, comment="限流Token预算"
        ),
        sa.Column(
            "error_category", sa.String(64), nullable=True, comment="脱敏错误分类"
        ),
        sa.Column("error_message", sa.Text(), nullable=True, comment="脱敏错误说明"),
        sa.Column(
            "started_at", _utc_datetime(), nullable=True, comment="开始时间（UTC）"
        ),
        sa.Column(
            "completed_at", _utc_datetime(), nullable=True, comment="完成时间（UTC）"
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["generation_tasks.id"], name="fk_generation_steps_task"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id", "step_key", name="uq_generation_task_steps_task_key"
        ),
        comment="生成任务阶段Checkpoint表",
    )
    op.create_index(
        "ix_generation_task_steps_task_id", "generation_task_steps", ["task_id"]
    )
    op.create_index(
        "ix_generation_task_steps_status", "generation_task_steps", ["status"]
    )

    op.create_table(
        "generation_task_inputs",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="任务输入ID"),
        sa.Column("task_id", sa.BINARY(16), nullable=False, comment="生成任务ID"),
        sa.Column("input_type", sa.String(32), nullable=False, comment="输入快照类型"),
        sa.Column(
            "reference_key", sa.String(255), nullable=False, comment="稳定引用键"
        ),
        sa.Column("snapshot", sa.JSON(), nullable=False, comment="不可变版本快照"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["generation_tasks.id"], name="fk_generation_inputs_task"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "input_type",
            "reference_key",
            name="uq_generation_task_inputs_reference",
        ),
        comment="生成任务不可变输入快照表",
    )
    op.create_index(
        "ix_generation_task_inputs_task_id", "generation_task_inputs", ["task_id"]
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="Outbox事件ID"),
        sa.Column("event_type", sa.String(64), nullable=False, comment="事件类型"),
        sa.Column("aggregate_type", sa.String(32), nullable=False, comment="聚合类型"),
        sa.Column("aggregate_id", sa.BINARY(16), nullable=False, comment="聚合ID"),
        sa.Column(
            "deduplication_key",
            sa.String(255),
            nullable=False,
            comment="事件幂等键",
        ),
        sa.Column("payload", sa.JSON(), nullable=False, comment="最小脱敏事件Payload"),
        sa.Column("status", sa.String(24), nullable=False, comment="投递状态"),
        sa.Column("retry_count", sa.Integer(), nullable=False, comment="投递重试次数"),
        sa.Column(
            "next_attempt_at",
            _utc_datetime(),
            nullable=False,
            comment="下次投递时间（UTC）",
        ),
        sa.Column(
            "lease_started_at",
            _utc_datetime(),
            nullable=True,
            comment="投递租约开始时间（UTC）",
        ),
        sa.Column(
            "published_at",
            _utc_datetime(),
            nullable=True,
            comment="确认投递时间（UTC）",
        ),
        sa.Column(
            "last_error_code",
            sa.String(64),
            nullable=True,
            comment="最近脱敏错误分类",
        ),
        sa.Column(
            "last_error_message", sa.Text(), nullable=True, comment="最近脱敏错误说明"
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deduplication_key", name="uq_outbox_events_deduplication_key"
        ),
        comment="MySQL Outbox可审计事件表",
    )
    op.create_index("ix_outbox_events_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index(
        "ix_outbox_events_next_attempt_at", "outbox_events", ["next_attempt_at"]
    )

    with op.batch_alter_table("credit_ledger") as batch:
        batch.create_foreign_key(
            "fk_credit_ledger_task", "generation_tasks", ["task_id"], ["id"]
        )
    with op.batch_alter_table("provider_calls") as batch:
        batch.alter_column(
            "brief_group_id",
            existing_type=sa.BINARY(16),
            nullable=True,
            existing_nullable=False,
        )
        batch.add_column(
            sa.Column("task_id", sa.BINARY(16), nullable=True, comment="关联生成任务ID")
        )
        batch.add_column(
            sa.Column(
                "task_step_id", sa.BINARY(16), nullable=True, comment="关联生成阶段ID"
            )
        )
        batch.create_foreign_key(
            "fk_provider_calls_task", "generation_tasks", ["task_id"], ["id"]
        )
        batch.create_unique_constraint(
            "uq_provider_calls_task_step_attempt",
            ["task_step_id", "attempt"],
        )
        batch.create_foreign_key(
            "fk_provider_calls_task_step",
            "generation_task_steps",
            ["task_step_id"],
            ["id"],
        )
        batch.create_index("ix_provider_calls_task_id", ["task_id"])
        batch.create_index("ix_provider_calls_task_step_id", ["task_step_id"])


def downgrade() -> None:
    with op.batch_alter_table("provider_calls") as batch:
        batch.drop_index("ix_provider_calls_task_step_id")
        batch.drop_index("ix_provider_calls_task_id")
        batch.drop_constraint("uq_provider_calls_task_step_attempt", type_="unique")
        batch.drop_constraint("fk_provider_calls_task_step", type_="foreignkey")
        batch.drop_constraint("fk_provider_calls_task", type_="foreignkey")
        batch.drop_column("task_step_id")
        batch.drop_column("task_id")
        batch.alter_column(
            "brief_group_id",
            existing_type=sa.BINARY(16),
            nullable=False,
            existing_nullable=True,
        )
    with op.batch_alter_table("credit_ledger") as batch:
        batch.drop_constraint("fk_credit_ledger_task", type_="foreignkey")
    op.drop_index("ix_outbox_events_next_attempt_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate_id", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index(
        "ix_generation_task_inputs_task_id", table_name="generation_task_inputs"
    )
    op.drop_table("generation_task_inputs")
    op.drop_index("ix_generation_task_steps_status", table_name="generation_task_steps")
    op.drop_index(
        "ix_generation_task_steps_task_id", table_name="generation_task_steps"
    )
    op.drop_table("generation_task_steps")
    for name in (
        "ix_generation_tasks_status",
        "ix_generation_tasks_combination_group_id",
        "ix_generation_tasks_credential_id",
        "ix_generation_tasks_brief_id",
        "ix_generation_tasks_project_id",
        "ix_generation_tasks_user_id",
    ):
        op.drop_index(name, table_name="generation_tasks")
    op.drop_table("generation_tasks")
