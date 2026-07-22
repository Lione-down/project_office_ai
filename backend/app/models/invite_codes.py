from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class InviteCode(Base):
    __tablename__ = "invite_codes"
    __table_args__ = (
        UniqueConstraint("code_hash", name="uq_invite_codes_code_hash"),
        {"comment": "邀请码表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="邀请码ID（UUIDv7二进制）",
    )
    code_hash: Mapped[str] = mapped_column(String(64), index=True, comment="邀请码哈希")
    code_prefix: Mapped[str] = mapped_column(
        String(12), index=True, comment="邀请码可识别前缀"
    )
    max_uses: Mapped[int] = mapped_column(Integer, comment="最大可用次数")
    used_count: Mapped[int] = mapped_column(Integer, default=0, comment="已使用次数")
    expires_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), comment="过期时间（UTC）"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="邀请码状态"
    )
    registration_credit: Mapped[int] = mapped_column(
        Integer, default=0, comment="注册赠送积分"
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_invite_codes_creator", use_alter=True),
        nullable=True,
        comment="创建管理员ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
