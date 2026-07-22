"""Add encrypted provider credential and model registry.

Revision ID: 20260722_0004
Revises: 20260722_0003
Create Date: 2026-07-22 15:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260722_0004"
down_revision = "20260722_0003"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="Provider ID（UUIDv7二进制）"
        ),
        sa.Column("vendor", sa.String(64), nullable=False, comment="Provider厂家代码"),
        sa.Column(
            "display_name", sa.String(128), nullable=False, comment="Provider显示名称"
        ),
        sa.Column(
            "protocol", sa.String(64), nullable=False, comment="Provider协议类型"
        ),
        sa.Column(
            "base_url", sa.String(512), nullable=False, comment="Provider API基础URL"
        ),
        sa.Column("status", sa.String(20), nullable=False, comment="Provider状态"),
        sa.Column(
            "default_timeout_seconds",
            sa.Integer(),
            nullable=False,
            comment="默认请求超时秒数",
        ),
        sa.Column("config", sa.JSON(), nullable=False, comment="非敏感配置"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="AI Provider配置表",
    )
    op.create_table(
        "provider_credentials",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="Credential ID（UUIDv7二进制）"
        ),
        sa.Column("provider_id", sa.BINARY(16), nullable=False, comment="Provider ID"),
        sa.Column("name", sa.String(128), nullable=False, comment="Credential名称"),
        sa.Column(
            "encrypted_key", sa.Text(), nullable=False, comment="应用层加密API Key"
        ),
        sa.Column(
            "key_fingerprint",
            sa.String(64),
            nullable=False,
            comment="API Key不可逆Fingerprint",
        ),
        sa.Column("status", sa.String(20), nullable=False, comment="Credential状态"),
        sa.Column("rpm_limit", sa.Integer(), nullable=False, comment="每分钟请求上限"),
        sa.Column("tpm_limit", sa.Integer(), nullable=False, comment="每分钟Token上限"),
        sa.Column(
            "max_concurrency", sa.Integer(), nullable=False, comment="最大并发数"
        ),
        sa.Column(
            "last_test_status", sa.String(32), nullable=True, comment="最近测试状态"
        ),
        sa.Column(
            "last_tested_at",
            _utc_datetime(),
            nullable=True,
            comment="最近测试时间（UTC）",
        ),
        sa.Column(
            "rotation_source", sa.String(64), nullable=False, comment="密钥轮换来源"
        ),
        sa.Column(
            "created_by_user_id", sa.BINARY(16), nullable=True, comment="创建管理员ID"
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_provider_credentials_creator"
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_provider_credentials_provider",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "key_fingerprint",
            name="uq_provider_credentials_provider_fingerprint",
        ),
        comment="Provider Credential表",
    )
    op.create_index(
        "ix_provider_credentials_provider_id",
        "provider_credentials",
        ["provider_id"],
    )
    op.create_table(
        "ai_models",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="模型ID（UUIDv7二进制）"
        ),
        sa.Column("provider_id", sa.BINARY(16), nullable=False, comment="Provider ID"),
        sa.Column(
            "credential_id", sa.BINARY(16), nullable=False, comment="Credential ID"
        ),
        sa.Column(
            "model_code", sa.String(128), nullable=False, comment="Provider模型代码"
        ),
        sa.Column(
            "display_name", sa.String(128), nullable=False, comment="模型显示名称"
        ),
        sa.Column("capabilities", sa.JSON(), nullable=False, comment="模型能力"),
        sa.Column(
            "context_window", sa.Integer(), nullable=False, comment="Context窗口Token数"
        ),
        sa.Column(
            "max_output_tokens", sa.Integer(), nullable=False, comment="最大输出Token数"
        ),
        sa.Column("user_visible", sa.Boolean(), nullable=False, comment="是否用户可见"),
        sa.Column(
            "is_recommended", sa.Boolean(), nullable=False, comment="是否推荐模型"
        ),
        sa.Column(
            "credit_multiplier", sa.Numeric(8, 4), nullable=False, comment="积分倍率"
        ),
        sa.Column(
            "allowed_skills", sa.JSON(), nullable=False, comment="允许的Skill代码"
        ),
        sa.Column("status", sa.String(20), nullable=False, comment="模型状态"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["provider_credentials.id"],
            name="fk_ai_models_credential",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["ai_providers.id"], name="fk_ai_models_provider"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "model_code",
            "credential_id",
            name="uq_ai_models_provider_code_credential",
        ),
        comment="AI模型注册表",
    )
    op.create_index("ix_ai_models_credential_id", "ai_models", ["credential_id"])
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    op.create_table(
        "audit_logs",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="审计日志ID（UUIDv7二进制）"
        ),
        sa.Column(
            "actor_user_id", sa.BINARY(16), nullable=True, comment="操作人用户ID"
        ),
        sa.Column("action", sa.String(128), nullable=False, comment="操作动作"),
        sa.Column("target_type", sa.String(64), nullable=False, comment="目标类型"),
        sa.Column("target_id", sa.BINARY(16), nullable=True, comment="目标ID"),
        sa.Column("ip_address", sa.String(64), nullable=True, comment="操作IP"),
        sa.Column(
            "user_agent", sa.String(255), nullable=True, comment="User-Agent摘要"
        ),
        sa.Column("reason", sa.String(500), nullable=False, comment="操作原因"),
        sa.Column("result", sa.String(32), nullable=False, comment="操作结果"),
        sa.Column("context", sa.JSON(), nullable=False, comment="脱敏上下文"),
        sa.Column("trace_id", sa.String(64), nullable=False, comment="Trace ID"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_audit_logs_actor"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="管理员敏感操作审计日志表",
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_trace_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_ai_models_provider_id", table_name="ai_models")
    op.drop_index("ix_ai_models_credential_id", table_name="ai_models")
    op.drop_table("ai_models")
    op.drop_index(
        "ix_provider_credentials_provider_id", table_name="provider_credentials"
    )
    op.drop_table("provider_credentials")
    op.drop_table("ai_providers")
