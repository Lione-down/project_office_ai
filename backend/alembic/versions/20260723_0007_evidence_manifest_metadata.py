"""Add Evidence Manifest metadata and bounded OCR retry state.

Revision ID: 20260723_0007
Revises: 20260723_0006
Create Date: 2026-07-23 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260723_0007"
down_revision = "20260723_0006"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.add_column(
        "file_assets",
        sa.Column(
            "manifest_status",
            sa.String(32),
            nullable=True,
            comment="Evidence Manifest状态",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "manifest_sha256",
            sa.String(64),
            nullable=True,
            comment="Evidence Manifest SHA-256摘要",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "manifest_schema_version",
            sa.String(32),
            nullable=True,
            comment="Evidence Manifest Schema版本",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "evidence_engine_version",
            sa.String(32),
            nullable=True,
            comment="证据生成引擎版本",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "evidence_warning_count",
            sa.Integer(),
            nullable=True,
            comment="Evidence Manifest告警数量",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "evidence_blocker_count",
            sa.Integer(),
            nullable=True,
            comment="Evidence Manifest阻断数量",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "evidence_generated_at",
            _utc_datetime(),
            nullable=True,
            comment="证据生成完成时间（UTC）",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processing_retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="处理重试次数",
        ),
    )
    op.add_column(
        "file_assets",
        sa.Column(
            "processing_retry_after",
            _utc_datetime(),
            nullable=True,
            comment="下次允许重试时间（UTC）",
        ),
    )


def downgrade() -> None:
    op.drop_column("file_assets", "processing_retry_after")
    op.drop_column("file_assets", "processing_retry_count")
    op.drop_column("file_assets", "evidence_generated_at")
    op.drop_column("file_assets", "evidence_blocker_count")
    op.drop_column("file_assets", "evidence_warning_count")
    op.drop_column("file_assets", "evidence_engine_version")
    op.drop_column("file_assets", "manifest_schema_version")
    op.drop_column("file_assets", "manifest_sha256")
    op.drop_column("file_assets", "manifest_status")
