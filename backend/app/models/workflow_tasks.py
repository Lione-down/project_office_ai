from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class WorkflowTask(Base):
    __tablename__ = "workflow_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_workflow_tasks_user_idempotency",
        ),
        UniqueConstraint(
            "brief_group_id",
            name="uq_workflow_tasks_brief_group",
        ),
        UniqueConstraint(
            "generation_task_id",
            name="uq_workflow_tasks_generation_task",
        ),
        {"comment": "用户端异步工作流任务"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="工作流任务ID（UUIDv7二进制）",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_workflow_tasks_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_workflow_tasks_project"),
        index=True,
        comment="所属项目ID",
    )
    brief_group_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        nullable=True,
        index=True,
        comment="成功生成后的Brief稳定组ID",
    )
    generation_task_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_workflow_tasks_generation_task"),
        nullable=True,
        index=True,
        comment="确认后关联的文件生成任务ID",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        comment="同用户创建幂等键",
    )
    title: Mapped[str] = mapped_column(String(500), comment="用户可见任务标题")
    request_snapshot: Mapped[dict] = mapped_column(
        JSON,
        comment="异步Brief生成所需结构化请求快照",
    )
    output_kinds: Mapped[list[str]] = mapped_column(
        JSON,
        comment="计划输出类型",
    )
    stage: Mapped[str] = mapped_column(String(32), comment="当前工作流阶段")
    status: Mapped[str] = mapped_column(String(32), comment="当前任务状态")
    progress: Mapped[int] = mapped_column(Integer, comment="0到100持久进度")
    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="可安全展示的系统备注",
    )
    failure_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="稳定失败码",
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="可安全展示的失败原因",
    )
    dispatch_sequence: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="队列投递序号",
    )
    last_enqueued_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        comment="最近入队时间（UTC）",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
        comment="开始执行时间（UTC）",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
        comment="终态时间（UTC）",
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
