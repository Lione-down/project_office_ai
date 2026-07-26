from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class SystemSetting(Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        UniqueConstraint("setting_key", name="uq_system_settings_key"),
        {"comment": "非敏感平台配置表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="配置ID（UUIDv7二进制）",
    )
    setting_key: Mapped[str] = mapped_column(
        String(128), comment="稳定配置键；禁止存放Secret"
    )
    setting_value: Mapped[dict | list | str | int | bool | None] = mapped_column(
        JSON, nullable=True, comment="非敏感JSON配置值"
    )
    value_type: Mapped[str] = mapped_column(String(32), comment="配置值类型")
    description: Mapped[str] = mapped_column(
        String(500), default="", comment="配置用途说明"
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_system_settings_updater"),
        nullable=True,
        index=True,
        comment="最后更新管理员ID",
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
