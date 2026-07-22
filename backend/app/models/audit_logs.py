from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"comment": "管理员敏感操作审计日志表"}

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="审计日志ID（UUIDv7二进制）",
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_audit_logs_actor"),
        nullable=True,
        index=True,
        comment="操作人用户ID",
    )
    action: Mapped[str] = mapped_column(String(128), index=True, comment="操作动作")
    target_type: Mapped[str] = mapped_column(String(64), comment="目标类型")
    target_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(), nullable=True, comment="目标ID"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="操作IP"
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="User-Agent摘要"
    )
    reason: Mapped[str] = mapped_column(String(500), comment="操作原因")
    result: Mapped[str] = mapped_column(String(32), comment="操作结果")
    context: Mapped[dict] = mapped_column(JSON, default=dict, comment="脱敏上下文")
    trace_id: Mapped[str] = mapped_column(String(64), index=True, comment="Trace ID")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
