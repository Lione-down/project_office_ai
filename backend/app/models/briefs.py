from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class Brief(Base):
    __tablename__ = "briefs"
    __table_args__ = (
        UniqueConstraint("brief_group_id", "revision", name="uq_briefs_group_revision"),
        {"comment": "Structured Brief不可变修订表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Brief修订行ID"
    )
    brief_group_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, comment="Brief稳定组ID"
    )
    revision: Mapped[int] = mapped_column(Integer, comment="不可变修订号")
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_briefs_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_briefs_project"),
        index=True,
        comment="所属项目ID",
    )
    selected_model_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_models.id", name="fk_briefs_selected_model"),
        index=True,
        comment="选择的模型ID",
    )
    source_snapshot: Mapped[dict] = mapped_column(JSON, comment="输入版本快照")
    content: Mapped[dict] = mapped_column(JSON, comment="Structured Brief内容")
    content_checksum: Mapped[str] = mapped_column(
        String(64), comment="Brief内容SHA-256"
    )
    status: Mapped[str] = mapped_column(String(20), comment="Brief修订状态")
    confirmed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="用户确认时间（UTC）"
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="修订创建时间（UTC）"
    )
