from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class AiProvider(Base):
    __tablename__ = "ai_providers"
    __table_args__ = {"comment": "AI Provider配置表"}

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="Provider ID（UUIDv7二进制）",
    )
    vendor: Mapped[str] = mapped_column(String(64), comment="Provider厂家代码")
    display_name: Mapped[str] = mapped_column(String(128), comment="Provider显示名称")
    protocol: Mapped[str] = mapped_column(String(64), comment="Provider协议类型")
    base_url: Mapped[str] = mapped_column(String(512), comment="Provider API基础URL")
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="Provider状态"
    )
    default_timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=120, comment="默认请求超时秒数"
    )
    config: Mapped[dict] = mapped_column(JSON, default=dict, comment="非敏感配置")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        onupdate=utc_now,
        comment="更新时间（UTC）",
    )
