from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "thread_id",
            name="uq_chat_threads_owner_identity",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_chat_threads_user_idempotency",
        ),
        {"comment": "Owner-scoped Chat会话"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="Chat会话ID",
    )
    thread_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        default=new_uuid7,
        comment="稳定会话Identity",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_chat_threads_user"),
        index=True,
        comment="所属用户ID",
    )
    title: Mapped[str] = mapped_column(String(200), comment="用户可见会话标题")
    default_model_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_models.id", name="fk_chat_threads_default_model"),
        index=True,
        comment="后续Run默认模型ID",
    )
    mode: Mapped[str] = mapped_column(
        String(16),
        default="chat",
        comment="会话模式chat或ppt",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        default="active",
        comment="会话状态",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        comment="创建会话幂等键",
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64),
        comment="创建请求Fingerprint",
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        index=True,
        comment="最近活动时间（UTC）",
    )
    retention_expires_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        comment="活动正文默认保留到期时间（UTC）",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
        comment="软删除时间（UTC）",
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        comment="创建时间（UTC）",
    )
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        onupdate=utc_now,
        comment="更新时间（UTC）",
    )
