"""Add users, sessions, invite codes, and registration credit ledger.

Revision ID: 20260722_0002
Revises: 20260722_0001
Create Date: 2026-07-22 11:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260722_0002"
down_revision = "20260722_0001"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BINARY(16), nullable=False),
        sa.Column("phone_country_code", sa.String(8), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("credit_balance", sa.Integer(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("invite_code_id", sa.BINARY(16), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "phone_country_code", "phone_number", name="uq_users_phone"
        ),
    )
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.BINARY(16), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("code_prefix", sa.String(12), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", _utc_datetime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("registration_credit", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.BINARY(16), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name="fk_invite_codes_creator"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_invite_codes_code_hash"),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_foreign_key(
            "fk_users_invite_code", "invite_codes", ["invite_code_id"], ["id"]
        )
    op.create_index("ix_invite_codes_code_hash", "invite_codes", ["code_hash"])
    op.create_index("ix_invite_codes_code_prefix", "invite_codes", ["code_prefix"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.BINARY(16), nullable=False),
        sa.Column("user_id", sa.BINARY(16), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("expires_at", _utc_datetime(), nullable=False),
        sa.Column("revoked_at", _utc_datetime(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_user_sessions_refresh_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index(
        "ix_user_sessions_refresh_token_hash",
        "user_sessions",
        ["refresh_token_hash"],
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.BINARY(16), nullable=False),
        sa.Column("user_id", sa.BINARY(16), nullable=False),
        sa.Column("task_id", sa.BINARY(16), nullable=True),
        sa.Column("entry_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("related_entry_id", sa.BINARY(16), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["related_entry_id"],
            ["credit_ledger.id"],
            name="fk_credit_ledger_related",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_credit_ledger_user"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            "entry_type",
            name="uq_credit_ledger_user_idempotency_type",
        ),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])
    op.create_index("ix_credit_ledger_entry_type", "credit_ledger", ["entry_type"])


def downgrade() -> None:
    op.drop_index("ix_credit_ledger_entry_type", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_user_id", table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_index("ix_user_sessions_refresh_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_invite_code", type_="foreignkey")
    op.drop_index("ix_invite_codes_code_prefix", table_name="invite_codes")
    op.drop_index("ix_invite_codes_code_hash", table_name="invite_codes")
    op.drop_table("invite_codes")
    op.drop_table("users")
