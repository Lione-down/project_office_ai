from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone_country_code", "phone_number", name="uq_users_phone"),
        {"comment": "用户账号表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="用户ID（UUIDv7二进制）",
    )
    phone_country_code: Mapped[str] = mapped_column(
        String(8), default="+86", comment="手机国家码"
    )
    phone_number: Mapped[str] = mapped_column(String(32), comment="用户手机号")
    role: Mapped[str] = mapped_column(String(20), default="user", comment="用户角色")
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="用户状态"
    )
    password_hash: Mapped[str] = mapped_column(String(255), comment="Argon2id密码哈希")
    credit_balance: Mapped[int] = mapped_column(
        Integer, default=0, comment="积分余额缓存"
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否强制修改密码"
    )
    invite_code_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("invite_codes.id", name="fk_users_invite_code"),
        nullable=True,
        comment="注册来源邀请码ID",
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
