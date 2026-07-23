from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint(
            "deduplication_key", name="uq_outbox_events_deduplication_key"
        ),
        {"comment": "MySQL Outbox可审计事件表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Outbox事件ID"
    )
    event_type: Mapped[str] = mapped_column(String(64), comment="事件类型")
    aggregate_type: Mapped[str] = mapped_column(String(32), comment="聚合类型")
    aggregate_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, comment="聚合ID"
    )
    deduplication_key: Mapped[str] = mapped_column(String(255), comment="事件幂等键")
    payload: Mapped[dict] = mapped_column(JSON, comment="最小脱敏事件Payload")
    status: Mapped[str] = mapped_column(
        String(24), default="pending", index=True, comment="投递状态"
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, comment="投递重试次数")
    next_attempt_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, index=True, comment="下次投递时间（UTC）"
    )
    lease_started_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="投递租约开始时间（UTC）"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="确认投递时间（UTC）"
    )
    last_error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="最近脱敏错误分类"
    )
    last_error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最近脱敏错误说明"
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
