from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class TermItem(Base):
    __tablename__ = "term_items"
    __table_args__ = (
        UniqueConstraint(
            "term_library_version_id",
            "item_id",
            name="uq_term_items_snapshot_item",
        ),
        UniqueConstraint(
            "term_library_version_id",
            "canonical_term",
            name="uq_term_items_snapshot_canonical",
        ),
        {"comment": "术语库版本条目表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="术语条目版本行ID",
    )
    item_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, comment="术语条目稳定ID"
    )
    term_library_version_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey(
            "term_libraries.id",
            name="fk_term_items_library_version",
        ),
        index=True,
        comment="所属术语库版本行ID",
    )
    canonical_term: Mapped[str] = mapped_column(String(255), comment="标准术语")
    aliases: Mapped[list[str]] = mapped_column(JSON, comment="去重别名列表")
    unit: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="标准单位代码"
    )
    definition: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, comment="术语定义"
    )
    metric_scope: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="指标口径说明"
    )
    priority: Mapped[int] = mapped_column(Integer, comment="解析优先级")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="条目版本创建时间（UTC）"
    )
