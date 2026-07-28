"""Add durable owner-scoped chat streaming.

Revision ID: 20260729_0016
Revises: 20260727_0015
Create Date: 2026-07-29 02:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260729_0016"
down_revision = "20260727_0015"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _uuid():
    return sa.BINARY(16)


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", _uuid(), nullable=False, comment="Chat会话ID"),
        sa.Column("thread_id", _uuid(), nullable=False, comment="稳定会话Identity"),
        sa.Column("user_id", _uuid(), nullable=False, comment="所属用户ID"),
        sa.Column("title", sa.String(200), nullable=False, comment="用户可见会话标题"),
        sa.Column(
            "default_model_id",
            _uuid(),
            nullable=False,
            comment="后续Run默认模型ID",
        ),
        sa.Column("mode", sa.String(16), nullable=False, comment="会话模式chat或ppt"),
        sa.Column("status", sa.String(24), nullable=False, comment="会话状态"),
        sa.Column(
            "idempotency_key",
            sa.String(128),
            nullable=False,
            comment="创建会话幂等键",
        ),
        sa.Column(
            "request_fingerprint",
            sa.String(64),
            nullable=False,
            comment="创建请求Fingerprint",
        ),
        sa.Column(
            "last_activity_at",
            _utc_datetime(),
            nullable=False,
            comment="最近活动时间（UTC）",
        ),
        sa.Column(
            "retention_expires_at",
            _utc_datetime(),
            nullable=False,
            comment="活动正文默认保留到期时间（UTC）",
        ),
        sa.Column(
            "deleted_at",
            _utc_datetime(),
            nullable=True,
            comment="软删除时间（UTC）",
        ),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["default_model_id"],
            ["ai_models.id"],
            name="fk_chat_threads_default_model",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_chat_threads_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "thread_id",
            name="uq_chat_threads_owner_identity",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_chat_threads_user_idempotency",
        ),
        comment="Owner-scoped Chat会话",
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"])
    op.create_index(
        "ix_chat_threads_default_model_id",
        "chat_threads",
        ["default_model_id"],
    )
    op.create_index(
        "ix_chat_threads_last_activity_at",
        "chat_threads",
        ["last_activity_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", _uuid(), nullable=False, comment="Chat消息ID"),
        sa.Column("thread_id", _uuid(), nullable=False, comment="所属会话ID"),
        sa.Column(
            "sequence", sa.Integer(), nullable=False, comment="会话内单调消息序号"
        ),
        sa.Column("role", sa.String(16), nullable=False, comment="user或assistant"),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="用户明确保存的Markdown正文",
        ),
        sa.Column("content_format", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, comment="消息状态"),
        sa.Column("parent_message_id", _uuid(), nullable=True),
        sa.Column("supersedes_message_id", _uuid(), nullable=True),
        sa.Column("branch_root_id", _uuid(), nullable=False),
        sa.Column("run_id", _uuid(), nullable=True, comment="关联Chat Run ID"),
        sa.Column("provenance_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.Column("finalized_at", _utc_datetime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_message_id"],
            ["chat_messages.id"],
            name="fk_chat_messages_parent",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_message_id"],
            ["chat_messages.id"],
            name="fk_chat_messages_superseded",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_messages_thread",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "thread_id",
            "sequence",
            name="uq_chat_messages_thread_sequence",
        ),
        comment="Owner-scoped Chat消息正文",
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
    op.create_index(
        "ix_chat_messages_parent_message_id",
        "chat_messages",
        ["parent_message_id"],
    )
    op.create_index(
        "ix_chat_messages_branch_root_id",
        "chat_messages",
        ["branch_root_id"],
    )
    op.create_index("ix_chat_messages_run_id", "chat_messages", ["run_id"])

    op.create_table(
        "chat_runs",
        sa.Column("id", _uuid(), nullable=False, comment="Chat Run ID"),
        sa.Column("user_id", _uuid(), nullable=False),
        sa.Column("thread_id", _uuid(), nullable=False),
        sa.Column("user_message_id", _uuid(), nullable=False),
        sa.Column("assistant_message_id", _uuid(), nullable=False),
        sa.Column("model_id", _uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_event_sequence", sa.Integer(), nullable=False),
        sa.Column("last_content_sequence", sa.Integer(), nullable=False),
        sa.Column("provider_snapshot", sa.JSON(), nullable=False),
        sa.Column("capability_snapshot", sa.JSON(), nullable=False),
        sa.Column("pricing_snapshot", sa.JSON(), nullable=False),
        sa.Column("thinking_enabled", sa.Boolean(), nullable=False),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("finish_reason", sa.String(64), nullable=True),
        sa.Column("cancel_requested_at", _utc_datetime(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_reason", sa.String(300), nullable=True),
        sa.Column("started_at", _utc_datetime(), nullable=True),
        sa.Column("completed_at", _utc_datetime(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["chat_messages.id"],
            name="fk_chat_runs_assistant_message",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["ai_models.id"],
            name="fk_chat_runs_model",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_runs_thread",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_chat_runs_user",
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"],
            ["chat_messages.id"],
            name="fk_chat_runs_user_message",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assistant_message_id",
            name="uq_chat_runs_assistant_message",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_chat_runs_user_idempotency",
        ),
        comment="Agnes Chat Run权威状态",
    )
    op.create_index("ix_chat_runs_user_id", "chat_runs", ["user_id"])
    op.create_index("ix_chat_runs_thread_id", "chat_runs", ["thread_id"])
    op.create_index("ix_chat_runs_model_id", "chat_runs", ["model_id"])

    chat_run_column = sa.Column(
        "chat_run_id",
        _uuid(),
        nullable=True,
        comment="关联Chat Run ID",
    )
    if op.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("provider_calls", recreate="always") as batch:
            batch.add_column(chat_run_column)
            batch.create_index(
                "ix_provider_calls_chat_run_id",
                ["chat_run_id"],
            )
            batch.create_unique_constraint(
                "uq_provider_calls_chat_run_attempt",
                ["chat_run_id", "attempt"],
            )
    else:
        op.add_column("provider_calls", chat_run_column)
        op.create_index(
            "ix_provider_calls_chat_run_id",
            "provider_calls",
            ["chat_run_id"],
        )
        op.create_unique_constraint(
            "uq_provider_calls_chat_run_attempt",
            "provider_calls",
            ["chat_run_id", "attempt"],
        )
        op.create_foreign_key(
            "fk_chat_messages_run",
            "chat_messages",
            "chat_runs",
            ["run_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_provider_calls_chat_run",
            "provider_calls",
            "chat_runs",
            ["chat_run_id"],
            ["id"],
        )


def downgrade() -> None:
    if op.get_context().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_provider_calls_chat_run",
            "provider_calls",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_chat_messages_run",
            "chat_messages",
            type_="foreignkey",
        )
        op.drop_constraint(
            "uq_provider_calls_chat_run_attempt",
            "provider_calls",
            type_="unique",
        )
        op.drop_index("ix_provider_calls_chat_run_id", table_name="provider_calls")
        op.drop_column("provider_calls", "chat_run_id")
    else:
        with op.batch_alter_table("provider_calls", recreate="always") as batch:
            batch.drop_constraint(
                "uq_provider_calls_chat_run_attempt",
                type_="unique",
            )
            batch.drop_index("ix_provider_calls_chat_run_id")
            batch.drop_column("chat_run_id")
    op.drop_index("ix_chat_runs_model_id", table_name="chat_runs")
    op.drop_index("ix_chat_runs_thread_id", table_name="chat_runs")
    op.drop_index("ix_chat_runs_user_id", table_name="chat_runs")
    op.drop_table("chat_runs")
    op.drop_index("ix_chat_messages_run_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_branch_root_id", table_name="chat_messages")
    op.drop_index(
        "ix_chat_messages_parent_message_id",
        table_name="chat_messages",
    )
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_last_activity_at", table_name="chat_threads")
    op.drop_index("ix_chat_threads_default_model_id", table_name="chat_threads")
    op.drop_index("ix_chat_threads_user_id", table_name="chat_threads")
    op.drop_table("chat_threads")
