from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            "entry_type",
            name="uq_credit_ledger_user_idempotency_type",
        ),
        {"comment": "积分流水表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="积分流水ID（UUIDv7二进制）",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_credit_ledger_user"),
        index=True,
        comment="用户ID",
    )
    task_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_credit_ledger_task"),
        nullable=True,
        comment="关联生成任务ID",
    )
    media_job_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("media_jobs.id", name="fk_credit_ledger_media_job"),
        nullable=True,
        index=True,
        comment="关联媒体任务ID",
    )
    entry_type: Mapped[str] = mapped_column(
        String(40), index=True, comment="积分流水类型"
    )
    amount: Mapped[int] = mapped_column(Integer, comment="积分变动数量")
    balance_after: Mapped[int] = mapped_column(Integer, comment="变动后余额快照")
    related_entry_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("credit_ledger.id", name="fk_credit_ledger_related"),
        nullable=True,
        comment="关联积分流水ID",
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), comment="幂等键")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="流水说明"
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
