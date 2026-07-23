"""Link immutable generated file assets to generation tasks.

Revision ID: 20260723_0012
Revises: 20260723_0011
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260723_0012"
down_revision: str | None = "20260723_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("file_assets") as batch:
        batch.create_foreign_key(
            "fk_file_assets_generated_task",
            "generation_tasks",
            ["generated_task_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("file_assets") as batch:
        batch.drop_constraint(
            "fk_file_assets_generated_task",
            type_="foreignkey",
        )
