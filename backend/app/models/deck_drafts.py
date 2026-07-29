from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class DeckDraft(Base):
    __tablename__ = "deck_drafts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "draft_group_id",
            name="uq_deck_drafts_owner_identity",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_deck_drafts_user_idempotency",
        ),
        UniqueConstraint(
            "user_id",
            "source_message_id",
            name="uq_deck_drafts_user_source_message",
        ),
        {"comment": "Owner-scoped Deck Draft稳定Identity"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Deck Draft ID"
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_deck_drafts_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_deck_drafts_project"),
        index=True,
        comment="所属项目ID",
    )
    thread_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_threads.id", name="fk_deck_drafts_thread"),
        index=True,
        comment="来源Chat会话ID",
    )
    source_message_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_messages.id", name="fk_deck_drafts_source_message"),
        index=True,
        comment="成功assistant来源消息ID",
    )
    draft_group_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, default=new_uuid7, comment="稳定Draft Identity"
    )
    latest_revision: Mapped[int] = mapped_column(
        Integer, default=1, comment="最新不可变Revision"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="draft", index=True, comment="Draft生命周期状态"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), comment="创建请求幂等键")
    request_fingerprint: Mapped[str] = mapped_column(
        String(64), comment="创建请求Fingerprint"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="删除时间（UTC）"
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
