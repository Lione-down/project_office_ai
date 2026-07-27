"""Add durable asynchronous workflow tasks.

Revision ID: 20260727_0015
Revises: 20260727_0014
Create Date: 2026-07-27 18:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260727_0015"
down_revision = "20260727_0014"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "workflow_tasks",
        sa.Column(
            "id",
            sa.BINARY(16),
            nullable=False,
            comment="工作流任务ID（UUIDv7二进制）",
        ),
        sa.Column(
            "user_id",
            sa.BINARY(16),
            nullable=False,
            comment="所属用户ID",
        ),
        sa.Column(
            "project_id",
            sa.BINARY(16),
            nullable=False,
            comment="所属项目ID",
        ),
        sa.Column(
            "brief_group_id",
            sa.BINARY(16),
            nullable=True,
            comment="成功生成后的Brief稳定组ID",
        ),
        sa.Column(
            "generation_task_id",
            sa.BINARY(16),
            nullable=True,
            comment="确认后关联的文件生成任务ID",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(128),
            nullable=False,
            comment="同用户创建幂等键",
        ),
        sa.Column(
            "title",
            sa.String(500),
            nullable=False,
            comment="用户可见任务标题",
        ),
        sa.Column(
            "request_snapshot",
            sa.JSON(),
            nullable=False,
            comment="异步Brief生成所需结构化请求快照",
        ),
        sa.Column(
            "output_kinds",
            sa.JSON(),
            nullable=False,
            comment="计划输出类型",
        ),
        sa.Column(
            "stage",
            sa.String(32),
            nullable=False,
            comment="当前工作流阶段",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            comment="当前任务状态",
        ),
        sa.Column("progress", sa.Integer(), nullable=False, comment="0到100持久进度"),
        sa.Column(
            "note",
            sa.String(500),
            nullable=True,
            comment="可安全展示的系统备注",
        ),
        sa.Column(
            "failure_code",
            sa.String(100),
            nullable=True,
            comment="稳定失败码",
        ),
        sa.Column(
            "failure_reason",
            sa.String(500),
            nullable=True,
            comment="可安全展示的失败原因",
        ),
        sa.Column(
            "dispatch_sequence",
            sa.Integer(),
            nullable=False,
            comment="队列投递序号",
        ),
        sa.Column(
            "last_enqueued_at",
            _utc_datetime(),
            nullable=False,
            comment="最近入队时间（UTC）",
        ),
        sa.Column(
            "started_at",
            _utc_datetime(),
            nullable=True,
            comment="开始执行时间（UTC）",
        ),
        sa.Column(
            "completed_at",
            _utc_datetime(),
            nullable=True,
            comment="终态时间（UTC）",
        ),
        sa.Column(
            "created_at",
            _utc_datetime(),
            nullable=False,
            comment="创建时间（UTC）",
        ),
        sa.Column(
            "updated_at",
            _utc_datetime(),
            nullable=False,
            comment="更新时间（UTC）",
        ),
        sa.ForeignKeyConstraint(
            ["generation_task_id"],
            ["generation_tasks.id"],
            name="fk_workflow_tasks_generation_task",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_workflow_tasks_project",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_workflow_tasks_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brief_group_id",
            name="uq_workflow_tasks_brief_group",
        ),
        sa.UniqueConstraint(
            "generation_task_id",
            name="uq_workflow_tasks_generation_task",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_workflow_tasks_user_idempotency",
        ),
        comment="用户端异步工作流任务",
    )
    op.create_index(
        "ix_workflow_tasks_brief_group_id",
        "workflow_tasks",
        ["brief_group_id"],
    )
    op.create_index(
        "ix_workflow_tasks_generation_task_id",
        "workflow_tasks",
        ["generation_task_id"],
    )
    op.create_index(
        "ix_workflow_tasks_project_id",
        "workflow_tasks",
        ["project_id"],
    )
    op.create_index(
        "ix_workflow_tasks_user_id",
        "workflow_tasks",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_tasks_user_id",
        table_name="workflow_tasks",
    )
    op.drop_index(
        "ix_workflow_tasks_project_id",
        table_name="workflow_tasks",
    )
    op.drop_index(
        "ix_workflow_tasks_generation_task_id",
        table_name="workflow_tasks",
    )
    op.drop_index(
        "ix_workflow_tasks_brief_group_id",
        table_name="workflow_tasks",
    )
    op.drop_table("workflow_tasks")
