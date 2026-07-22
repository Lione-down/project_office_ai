from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_user_sessions_refresh_hash"),
        {"comment": "用户会话表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="会话ID（UUIDv7二进制）",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_sessions_user"),
        index=True,
        comment="用户ID",
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(64), index=True, comment="刷新令牌哈希"
    )
    device_info: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="设备信息摘要"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="IP地址"
    )
    expires_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), comment="过期时间（UTC）"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="撤销时间（UTC）"
    )
    revocation_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="撤销原因"
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        onupdate=utc_now,
        comment="更新时间（UTC）",
    )
