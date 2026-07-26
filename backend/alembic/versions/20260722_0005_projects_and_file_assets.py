"""Add user projects and isolated file assets.

Revision ID: 20260722_0005
Revises: 20260722_0004
Create Date: 2026-07-22 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260722_0005"
down_revision = "20260722_0004"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _storage_locator(length: int):
    return sa.String(length).with_variant(
        mysql.VARCHAR(length, charset="ascii", collation="ascii_bin"),
        "mysql",
    )


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="项目ID（UUIDv7二进制）"
        ),
        sa.Column("user_id", sa.BINARY(16), nullable=False, comment="所属用户ID"),
        sa.Column("name", sa.String(128), nullable=False, comment="项目名称"),
        sa.Column("is_default", sa.Boolean(), nullable=False, comment="是否默认项目"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, comment="是否已归档"),
        sa.Column(
            "deleted_at", _utc_datetime(), nullable=True, comment="软删除时间（UTC）"
        ),
        sa.Column(
            "active_default_owner_id",
            sa.BINARY(16),
            sa.Computed(
                "CASE WHEN is_default = 1 AND deleted_at IS NULL "
                "THEN user_id ELSE NULL END"
            ),
            nullable=True,
            comment="活动默认项目用户唯一键",
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_projects_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "active_default_owner_id", name="uq_projects_active_default_owner"
        ),
        comment="用户项目表",
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_table(
        "file_assets",
        sa.Column(
            "id", sa.BINARY(16), nullable=False, comment="资产ID（UUIDv7二进制）"
        ),
        sa.Column("user_id", sa.BINARY(16), nullable=False, comment="所属用户ID"),
        sa.Column("project_id", sa.BINARY(16), nullable=False, comment="所属项目ID"),
        sa.Column(
            "original_filename",
            sa.String(255),
            nullable=False,
            comment="清理后的原始文件名",
        ),
        sa.Column("file_category", sa.String(32), nullable=False, comment="文件分类"),
        sa.Column("mime_type", sa.String(128), nullable=False, comment="初检MIME类型"),
        sa.Column("byte_size", sa.BigInteger(), nullable=False, comment="文件字节数"),
        sa.Column("sha256", sa.String(64), nullable=False, comment="SHA-256摘要"),
        sa.Column(
            "storage_provider",
            _storage_locator(32),
            nullable=False,
            comment="存储Provider",
        ),
        sa.Column(
            "storage_key",
            _storage_locator(768),
            nullable=False,
            comment="存储定位键",
        ),
        sa.Column(
            "processing_status", sa.String(32), nullable=False, comment="资产处理状态"
        ),
        sa.Column(
            "idempotency_key", sa.String(128), nullable=True, comment="用户上传幂等键"
        ),
        sa.Column(
            "parent_asset_id", sa.BINARY(16), nullable=True, comment="父版本资产ID"
        ),
        sa.Column(
            "generated_task_id", sa.BINARY(16), nullable=True, comment="生成任务ID"
        ),
        sa.Column(
            "manifest_key",
            sa.String(768),
            nullable=True,
            comment="Evidence Manifest存储键",
        ),
        sa.Column(
            "deleted_at", _utc_datetime(), nullable=True, comment="软删除时间（UTC）"
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="创建时间（UTC）"
        ),
        sa.Column(
            "updated_at", _utc_datetime(), nullable=False, comment="更新时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["parent_asset_id"], ["file_assets.id"], name="fk_file_assets_parent"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_file_assets_project"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_file_assets_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_provider",
            "storage_key",
            name="uq_file_assets_storage_location",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_file_assets_user_idempotency",
        ),
        comment="文件资产表",
    )
    op.create_index("ix_file_assets_project_id", "file_assets", ["project_id"])
    op.create_index("ix_file_assets_user_id", "file_assets", ["user_id"])
    op.create_index("ix_file_assets_sha256", "file_assets", ["sha256"])
    op.create_index(
        "ix_file_assets_processing_status", "file_assets", ["processing_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_file_assets_processing_status", table_name="file_assets")
    op.drop_index("ix_file_assets_sha256", table_name="file_assets")
    op.drop_index("ix_file_assets_user_id", table_name="file_assets")
    op.drop_index("ix_file_assets_project_id", table_name="file_assets")
    op.drop_table("file_assets")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
