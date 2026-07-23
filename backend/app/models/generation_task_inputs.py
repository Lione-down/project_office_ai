from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class GenerationTaskInput(Base):
    __tablename__ = "generation_task_inputs"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "input_type",
            "reference_key",
            name="uq_generation_task_inputs_reference",
        ),
        {"comment": "生成任务不可变输入快照表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="任务输入ID"
    )
    task_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_generation_inputs_task"),
        index=True,
        comment="生成任务ID",
    )
    input_type: Mapped[str] = mapped_column(String(32), comment="输入快照类型")
    reference_key: Mapped[str] = mapped_column(String(255), comment="稳定引用键")
    snapshot: Mapped[dict] = mapped_column(JSON, comment="不可变版本快照")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
