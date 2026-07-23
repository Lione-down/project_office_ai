from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_generation_tasks_user_idempotency",
        ),
        {"comment": "持久生成任务表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="生成任务ID"
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_generation_tasks_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_generation_tasks_project"),
        index=True,
        comment="所属项目ID",
    )
    brief_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("briefs.id", name="fk_generation_tasks_brief"),
        index=True,
        comment="确认的Brief修订行ID",
    )
    model_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_models.id", name="fk_generation_tasks_model"),
        comment="锁定模型ID",
    )
    credential_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("provider_credentials.id", name="fk_generation_tasks_credential"),
        index=True,
        comment="锁定Credential ID",
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), comment="用户请求幂等键")
    combination_group_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(), nullable=True, index=True, comment="组合任务稳定组ID"
    )
    parent_task_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_generation_tasks_parent"),
        nullable=True,
        comment="父任务ID",
    )
    status: Mapped[str] = mapped_column(
        String(32), default="queued", index=True, comment="任务状态"
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="任务进度百分比")
    skill_snapshot: Mapped[list] = mapped_column(JSON, comment="Skill不可变快照")
    model_snapshot: Mapped[dict] = mapped_column(JSON, comment="模型配置不可变快照")
    estimated_credits: Mapped[int] = mapped_column(Integer, comment="预留积分")
    settled_credits: Mapped[int] = mapped_column(
        Integer, default=0, comment="已结算成功积分"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="任务级重试次数"
    )
    dispatch_sequence: Mapped[int] = mapped_column(
        Integer, default=1, comment="Outbox投递序号"
    )
    error_category: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="脱敏错误分类"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="脱敏错误说明"
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="取消请求时间（UTC）"
    )
    timeout_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), comment="完整任务超时时间（UTC）"
    )
    last_enqueued_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="最近生成Outbox时间（UTC）"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="首次开始时间（UTC）"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="终态完成时间（UTC）"
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
