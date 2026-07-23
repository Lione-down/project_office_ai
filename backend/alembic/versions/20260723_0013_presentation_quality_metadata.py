"""Add versioned presentation quality metadata to file assets.

Revision ID: 20260723_0013
Revises: 20260723_0012
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.models.base import utc_datetime_type


revision: str = "20260723_0013"
down_revision: str | None = "20260723_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("file_assets") as batch:
        batch.add_column(
            sa.Column(
                "quality_status",
                sa.String(32),
                nullable=True,
                comment="质量门禁状态",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_report_key",
                sa.String(768),
                nullable=True,
                comment="版本化质量报告存储键",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_report_sha256",
                sa.String(64),
                nullable=True,
                comment="质量报告SHA-256摘要",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_report_schema_version",
                sa.String(64),
                nullable=True,
                comment="质量报告Schema版本",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_engine_version",
                sa.String(64),
                nullable=True,
                comment="质量引擎版本",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_preview_keys",
                sa.JSON(),
                nullable=True,
                comment="PDF与逐页预览存储键",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_validated_key",
                sa.String(768),
                nullable=True,
                comment="通过质量门禁的下载文件键",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_validated_sha256",
                sa.String(64),
                nullable=True,
                comment="通过质量门禁文件SHA-256摘要",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_validated_byte_size",
                sa.BigInteger(),
                nullable=True,
                comment="通过质量门禁文件字节数",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_repair_attempt_count",
                sa.Integer(),
                nullable=True,
                comment="确定性自动修复次数",
            )
        )
        batch.add_column(
            sa.Column(
                "quality_checked_at",
                utc_datetime_type(),
                nullable=True,
                comment="质量门禁完成时间（UTC）",
            )
        )
        batch.create_index(
            "ix_file_assets_quality_status",
            ["quality_status"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("file_assets") as batch:
        batch.drop_index("ix_file_assets_quality_status")
        for column_name in (
            "quality_checked_at",
            "quality_repair_attempt_count",
            "quality_validated_byte_size",
            "quality_validated_sha256",
            "quality_validated_key",
            "quality_preview_keys",
            "quality_engine_version",
            "quality_report_schema_version",
            "quality_report_sha256",
            "quality_report_key",
            "quality_status",
        ):
            batch.drop_column(column_name)
