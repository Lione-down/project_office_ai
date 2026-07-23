"""Add Brief Preflight snapshot and estimated credit lock.

Revision ID: 20260723_0010
Revises: 20260723_0009
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0010"
down_revision: str | None = "20260723_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "briefs",
        sa.Column(
            "preflight_snapshot",
            sa.JSON(),
            nullable=True,
            comment="不可变Preflight结果快照",
        ),
    )
    op.add_column(
        "briefs",
        sa.Column(
            "estimated_credits",
            sa.Integer(),
            nullable=True,
            comment="用户确认的预计积分",
        ),
    )


def downgrade() -> None:
    op.drop_column("briefs", "estimated_credits")
    op.drop_column("briefs", "preflight_snapshot")
