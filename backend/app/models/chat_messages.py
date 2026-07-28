from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "thread_id",
            "sequence",
            name="uq_chat_messages_thread_sequence",
        ),
        {"comment": "Owner-scoped Chat消息正文"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="Chat消息ID",
    )
    thread_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_threads.id", name="fk_chat_messages_thread"),
        index=True,
        comment="所属会话ID",
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        comment="会话内单调消息序号",
    )
    role: Mapped[str] = mapped_column(String(16), comment="user或assistant")
    content: Mapped[str] = mapped_column(
        Text,
        default="",
        comment="用户明确保存的Markdown正文",
    )
    content_format: Mapped[str] = mapped_column(
        String(16),
        default="markdown",
        comment="正文格式",
    )
    status: Mapped[str] = mapped_column(String(32), comment="消息状态")
    parent_message_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_messages.id", name="fk_chat_messages_parent"),
        nullable=True,
        index=True,
        comment="分支父消息ID",
    )
    supersedes_message_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_messages.id", name="fk_chat_messages_superseded"),
        nullable=True,
        comment="编辑后重发所替代的消息ID",
    )
    branch_root_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        index=True,
        comment="分支根消息ID",
    )
    run_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        nullable=True,
        index=True,
        comment="关联Chat Run ID",
    )
    provenance_summary: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        comment="不含正文的来源摘要",
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
    finalized_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
        comment="终态时间（UTC）",
    )
