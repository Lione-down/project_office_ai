from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class DeckDraftInput(Base):
    __tablename__ = "deck_draft_inputs"
    __table_args__ = (
        UniqueConstraint(
            "revision_id",
            "input_kind",
            "source_asset_id",
            "source_message_id",
            name="uq_deck_draft_inputs_revision_source",
        ),
        {"comment": "Deck Revision冻结来源"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Deck Input ID"
    )
    revision_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("deck_draft_revisions.id", name="fk_deck_inputs_revision"),
        index=True,
        comment="所属Deck Revision ID",
    )
    input_kind: Mapped[str] = mapped_column(String(32), comment="message或asset")
    source_asset_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("file_assets.id", name="fk_deck_inputs_asset"),
        nullable=True,
        index=True,
        comment="冻结资产ID",
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_messages.id", name="fk_deck_inputs_message"),
        nullable=True,
        index=True,
        comment="冻结消息ID",
    )
    source_version: Mapped[str] = mapped_column(String(80), comment="来源版本")
    source_checksum: Mapped[str] = mapped_column(
        String(64), comment="来源内容或文件SHA-256"
    )
    evidence_snapshot: Mapped[dict] = mapped_column(
        JSON, default=dict, comment="Evidence与术语冻结摘要"
    )
    provenance_kind: Mapped[str] = mapped_column(
        String(32), comment="user_input、agnes_inference或source_evidence"
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
