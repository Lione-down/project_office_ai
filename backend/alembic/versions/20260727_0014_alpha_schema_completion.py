"""Complete the frozen Alpha schema with templates and system settings.

Revision ID: 20260727_0014
Revises: 20260723_0013
Create Date: 2026-07-27 03:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260727_0014"
down_revision = "20260723_0013"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column(
            "id",
            sa.BINARY(16),
            nullable=False,
            comment="模板版本ID（UUIDv7二进制）",
        ),
        sa.Column(
            "owner_user_id",
            sa.BINARY(16),
            nullable=True,
            comment="未来用户模板所有者；系统模板为空",
        ),
        sa.Column(
            "preview_asset_id",
            sa.BINARY(16),
            nullable=True,
            comment="可选预览资产ID",
        ),
        sa.Column(
            "template_code",
            sa.String(128),
            nullable=False,
            comment="跨版本稳定模板代码",
        ),
        sa.Column("template_type", sa.String(32), nullable=False, comment="模板类型"),
        sa.Column("source", sa.String(32), nullable=False, comment="模板来源"),
        sa.Column(
            "display_name", sa.String(128), nullable=False, comment="模板显示名称"
        ),
        sa.Column("category", sa.String(64), nullable=False, comment="模板分类"),
        sa.Column(
            "style_keywords", sa.JSON(), nullable=False, comment="样式关键词列表"
        ),
        sa.Column("design_config", sa.JSON(), nullable=False, comment="非敏感设计配置"),
        sa.Column("version", sa.Integer(), nullable=False, comment="模板版本"),
        sa.Column("status", sa.String(20), nullable=False, comment="模板状态"),
        sa.Column("sort_order", sa.Integer(), nullable=False, comment="展示排序序号"),
        sa.Column("usage_count", sa.Integer(), nullable=False, comment="累计使用次数"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_templates_owner"
        ),
        sa.ForeignKeyConstraint(
            ["preview_asset_id"],
            ["file_assets.id"],
            name="fk_templates_preview_asset",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "template_code",
            "version",
            name="uq_templates_source_code_version",
        ),
        comment="版本化模板注册表",
    )
    op.create_index("ix_templates_category", "templates", ["category"])
    op.create_index("ix_templates_owner_user_id", "templates", ["owner_user_id"])
    op.create_index("ix_templates_preview_asset_id", "templates", ["preview_asset_id"])
    op.create_index("ix_templates_status", "templates", ["status"])
    op.create_index("ix_templates_template_type", "templates", ["template_type"])

    op.create_table(
        "system_settings",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="配置ID（UUIDv7二进制）"
        ),
        sa.Column(
            "setting_key",
            sa.String(128),
            nullable=False,
            comment="稳定配置键；禁止存放Secret",
        ),
        sa.Column(
            "setting_value",
            sa.JSON(),
            nullable=True,
            comment="非敏感JSON配置值",
        ),
        sa.Column("value_type", sa.String(32), nullable=False, comment="配置值类型"),
        sa.Column(
            "description", sa.String(500), nullable=False, comment="配置用途说明"
        ),
        sa.Column(
            "updated_by_user_id",
            sa.BINARY(16),
            nullable=True,
            comment="最后更新管理员ID",
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_system_settings_updater",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("setting_key", name="uq_system_settings_key"),
        comment="非敏感平台配置表",
    )
    op.create_index(
        "ix_system_settings_updated_by_user_id",
        "system_settings",
        ["updated_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_system_settings_updated_by_user_id",
        table_name="system_settings",
    )
    op.drop_table("system_settings")
    op.drop_index("ix_templates_template_type", table_name="templates")
    op.drop_index("ix_templates_status", table_name="templates")
    op.drop_index("ix_templates_preview_asset_id", table_name="templates")
    op.drop_index("ix_templates_owner_user_id", table_name="templates")
    op.drop_index("ix_templates_category", table_name="templates")
    op.drop_table("templates")
