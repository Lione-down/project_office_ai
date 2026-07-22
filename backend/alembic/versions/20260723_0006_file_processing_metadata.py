"""Add safe file processing metadata.

Revision ID: 20260723_0006
Revises: 20260722_0005
Create Date: 2026-07-23 11:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260723_0006"
down_revision = "20260722_0005"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.add_column(
        "file_assets",
        sa.Column(
            "parsed_storage_key",
            sa.String(768),
            nullable=True,
            comment="解析结果存储键",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "parser_name", sa.String(64), nullable=True, comment="安全解析器名称"
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "parser_version", sa.String(32), nullable=True, comment="安全解析器版本"
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processing_warnings", sa.JSON(), nullable=True, comment="解析告警代码列表"
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processing_error_code",
            sa.String(64),
            nullable=True,
            comment="处理错误代码",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processing_error_message",
            sa.String(255),
            nullable=True,
            comment="脱敏处理错误",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processing_started_at",
            _utc_datetime(),
            nullable=True,
            comment="处理开始时间（UTC）",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processed_at",
            _utc_datetime(),
            nullable=True,
            comment="处理完成时间（UTC）",
        ),
    )


def downgrade() -> None:
    op.drop_column("file_assets", "processed_at")
    op.drop_column("file_assets", "processing_started_at")
    op.drop_column("file_assets", "processing_error_message")
    op.drop_column("file_assets", "processing_error_code")
    op.drop_column("file_assets", "processing_warnings")
    op.drop_column("file_assets", "parser_version")
    op.drop_column("file_assets", "parser_name")
    op.drop_column("file_assets", "parsed_storage_key")
