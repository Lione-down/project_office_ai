"""Add immutable personal terminology library snapshots.

Revision ID: 20260723_0008
Revises: 20260723_0007
Create Date: 2026-07-23 21:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260723_0008"
down_revision = "20260723_0007"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "term_libraries",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="术语库版本行ID"),
        sa.Column("library_id", sa.BINARY(16), nullable=False, comment="术语库稳定ID"),
        sa.Column("user_id", sa.BINARY(16), nullable=False, comment="所属用户ID"),
        sa.Column(
            "project_id", sa.BINARY(16), nullable=True, comment="可选项目覆盖范围"
        ),
        sa.Column(
            "previous_version_id",
            sa.BINARY(16),
            nullable=True,
            comment="前一不可变版本行ID",
        ),
        sa.Column("name", sa.String(128), nullable=False, comment="术语库名称"),
        sa.Column("description", sa.String(1024), nullable=True, comment="术语库说明"),
        sa.Column("status", sa.String(20), nullable=False, comment="术语库版本状态"),
        sa.Column("version", sa.Integer(), nullable=False, comment="术语库版本号"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="版本创建时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["previous_version_id"],
            ["term_libraries.id"],
            name="fk_term_libraries_previous_version",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_term_libraries_project"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_term_libraries_user"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "library_id",
            "version",
            name="uq_term_libraries_library_version",
        ),
        comment="个人术语库不可变版本表",
    )
    op.create_index("ix_term_libraries_library_id", "term_libraries", ["library_id"])
    op.create_index("ix_term_libraries_user_id", "term_libraries", ["user_id"])
    op.create_index("ix_term_libraries_project_id", "term_libraries", ["project_id"])
    op.create_table(
        "term_items",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="术语条目版本行ID"),
        sa.Column("item_id", sa.BINARY(16), nullable=False, comment="术语条目稳定ID"),
        sa.Column(
            "term_library_version_id",
            sa.BINARY(16),
            nullable=False,
            comment="所属术语库版本行ID",
        ),
        sa.Column("canonical_term", sa.String(255), nullable=False, comment="标准术语"),
        sa.Column("aliases", sa.JSON(), nullable=False, comment="去重别名列表"),
        sa.Column("unit", sa.String(32), nullable=True, comment="标准单位代码"),
        sa.Column("definition", sa.String(2048), nullable=True, comment="术语定义"),
        sa.Column(
            "metric_scope", sa.String(1024), nullable=True, comment="指标口径说明"
        ),
        sa.Column("priority", sa.Integer(), nullable=False, comment="解析优先级"),
        sa.Column(
            "created_at",
            _utc_datetime(),
            nullable=False,
            comment="条目版本创建时间（UTC）",
        ),
        sa.ForeignKeyConstraint(
            ["term_library_version_id"],
            ["term_libraries.id"],
            name="fk_term_items_library_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "term_library_version_id",
            "canonical_term",
            name="uq_term_items_snapshot_canonical",
        ),
        sa.UniqueConstraint(
            "term_library_version_id",
            "item_id",
            name="uq_term_items_snapshot_item",
        ),
        comment="术语库版本条目表",
    )
    op.create_index("ix_term_items_item_id", "term_items", ["item_id"])
    op.create_index(
        "ix_term_items_term_library_version_id",
        "term_items",
        ["term_library_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_term_items_term_library_version_id", table_name="term_items")
    op.drop_index("ix_term_items_item_id", table_name="term_items")
    op.drop_table("term_items")
    op.drop_index("ix_term_libraries_project_id", table_name="term_libraries")
    op.drop_index("ix_term_libraries_user_id", table_name="term_libraries")
    op.drop_index("ix_term_libraries_library_id", table_name="term_libraries")
    op.drop_table("term_libraries")
