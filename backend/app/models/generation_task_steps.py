from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class GenerationTaskStep(Base):
    __tablename__ = "generation_task_steps"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "step_key", name="uq_generation_task_steps_task_key"
        ),
        {"comment": "生成任务阶段Checkpoint表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="任务阶段ID"
    )
    task_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_generation_steps_task"),
        index=True,
        comment="生成任务ID",
    )
    step_key: Mapped[str] = mapped_column(String(128), comment="稳定阶段键")
    output_kind: Mapped[str] = mapped_column(String(16), comment="子输出类型")
    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True, comment="阶段状态"
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, comment="已执行次数")
    estimated_credits: Mapped[int] = mapped_column(Integer, comment="子输出预计积分")
    checkpoint: Mapped[dict] = mapped_column(
        JSON, default=dict, comment="安全恢复Checkpoint"
    )
    provider_request_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Provider Request ID"
    )
    token_estimate: Mapped[int] = mapped_column(
        Integer, default=0, comment="限流Token预算"
    )
    error_category: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="脱敏错误分类"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="脱敏错误说明"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="开始时间（UTC）"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="完成时间（UTC）"
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
