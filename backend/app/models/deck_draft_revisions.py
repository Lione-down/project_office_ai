from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class DeckDraftRevision(Base):
    __tablename__ = "deck_draft_revisions"
    __table_args__ = (
        UniqueConstraint(
            "draft_id",
            "revision",
            name="uq_deck_draft_revisions_draft_revision",
        ),
        {"comment": "Deck Brief不可变Revision"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Deck Revision ID"
    )
    draft_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("deck_drafts.id", name="fk_deck_revisions_draft"),
        index=True,
        comment="所属Draft ID",
    )
    revision: Mapped[int] = mapped_column(Integer, comment="不可变Revision序号")
    content: Mapped[dict] = mapped_column(JSON, comment="严格deck-brief.v1内容")
    content_checksum: Mapped[str] = mapped_column(
        String(64), comment="Canonical内容SHA-256"
    )
    source_mode: Mapped[str] = mapped_column(String(16), comment="来源模式")
    skill_snapshot: Mapped[dict] = mapped_column(JSON, comment="Skill冻结快照")
    model_snapshot: Mapped[dict] = mapped_column(JSON, comment="模型冻结快照")
    template_snapshot: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="模板冻结快照"
    )
    provenance_summary: Mapped[dict] = mapped_column(JSON, comment="不含正文的来源摘要")
    preflight_snapshot: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Deck Preflight快照"
    )
    high_risk_confirmation_required: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否需要高风险显式确认"
    )
    high_risk_confirmed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="高风险确认时间（UTC）"
    )
    status: Mapped[str] = mapped_column(String(32), comment="Revision状态")
    bridge_brief_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("briefs.id", name="fk_deck_revisions_bridge_brief"),
        nullable=True,
        index=True,
        comment="复用Preflight/Generation的Brief修订ID",
    )
    generation_task_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_deck_revisions_generation_task"),
        nullable=True,
        index=True,
        comment="权威Generation Task ID",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="大纲确认时间（UTC）"
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
