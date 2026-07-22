"""Add Chinese comments to authentication tables and columns.

Revision ID: 20260722_0003
Revises: 20260722_0002
Create Date: 2026-07-22 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260722_0003"
down_revision = "20260722_0002"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


TABLE_COMMENTS = {
    "users": "用户账号表",
    "user_sessions": "用户会话表",
    "invite_codes": "邀请码表",
    "credit_ledger": "积分流水表",
}

COLUMN_COMMENTS = {
    "users": (
        ("id", sa.BINARY(16), False, "用户ID（UUIDv7二进制）"),
        ("phone_country_code", sa.String(8), False, "手机国家码"),
        ("phone_number", sa.String(32), False, "用户手机号"),
        ("role", sa.String(20), False, "用户角色"),
        ("status", sa.String(20), False, "用户状态"),
        ("password_hash", sa.String(255), False, "Argon2id密码哈希"),
        ("credit_balance", sa.Integer(), False, "积分余额缓存"),
        ("must_change_password", sa.Boolean(), False, "是否强制修改密码"),
        ("invite_code_id", sa.BINARY(16), True, "注册来源邀请码ID"),
        ("created_at", _utc_datetime(), False, "创建时间（UTC）"),
        ("updated_at", _utc_datetime(), False, "更新时间（UTC）"),
    ),
    "user_sessions": (
        ("id", sa.BINARY(16), False, "会话ID（UUIDv7二进制）"),
        ("user_id", sa.BINARY(16), False, "用户ID"),
        ("refresh_token_hash", sa.String(64), False, "刷新令牌哈希"),
        ("device_info", sa.String(255), True, "设备信息摘要"),
        ("ip_address", sa.String(64), True, "IP地址"),
        ("expires_at", _utc_datetime(), False, "过期时间（UTC）"),
        ("revoked_at", _utc_datetime(), True, "撤销时间（UTC）"),
        ("revocation_reason", sa.Text(), True, "撤销原因"),
        ("created_at", _utc_datetime(), False, "创建时间（UTC）"),
        ("updated_at", _utc_datetime(), False, "更新时间（UTC）"),
    ),
    "invite_codes": (
        ("id", sa.BINARY(16), False, "邀请码ID（UUIDv7二进制）"),
        ("code_hash", sa.String(64), False, "邀请码哈希"),
        ("code_prefix", sa.String(12), False, "邀请码可识别前缀"),
        ("max_uses", sa.Integer(), False, "最大可用次数"),
        ("used_count", sa.Integer(), False, "已使用次数"),
        ("expires_at", _utc_datetime(), False, "过期时间（UTC）"),
        ("status", sa.String(20), False, "邀请码状态"),
        ("registration_credit", sa.Integer(), False, "注册赠送积分"),
        ("created_by_user_id", sa.BINARY(16), True, "创建管理员ID"),
        ("created_at", _utc_datetime(), False, "创建时间（UTC）"),
    ),
    "credit_ledger": (
        ("id", sa.BINARY(16), False, "积分流水ID（UUIDv7二进制）"),
        ("user_id", sa.BINARY(16), False, "用户ID"),
        ("task_id", sa.BINARY(16), True, "关联生成任务ID"),
        ("entry_type", sa.String(40), False, "积分流水类型"),
        ("amount", sa.Integer(), False, "积分变动数量"),
        ("balance_after", sa.Integer(), False, "变动后余额快照"),
        ("related_entry_id", sa.BINARY(16), True, "关联积分流水ID"),
        ("idempotency_key", sa.String(128), False, "幂等键"),
        ("description", sa.Text(), True, "流水说明"),
        ("created_at", _utc_datetime(), False, "创建时间（UTC）"),
    ),
}


def _set_comments(should_set: bool) -> None:
    if op.get_context().dialect.name != "mysql":
        return
    for table_name, table_comment in TABLE_COMMENTS.items():
        rendered_comment = table_comment if should_set else ""
        op.execute(f"ALTER TABLE `{table_name}` COMMENT = '{rendered_comment}'")
    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name, column_type, is_nullable, column_comment in columns:
            op.alter_column(
                table_name,
                column_name,
                existing_type=column_type,
                existing_nullable=is_nullable,
                comment=column_comment if should_set else None,
                existing_comment=None if should_set else column_comment,
            )


def upgrade() -> None:
    _set_comments(True)


def downgrade() -> None:
    _set_comments(False)
