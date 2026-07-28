from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class ChatRun(Base):
    __tablename__ = "chat_runs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_chat_runs_user_idempotency",
        ),
        UniqueConstraint(
            "assistant_message_id",
            name="uq_chat_runs_assistant_message",
        ),
        {"comment": "Agnes Chat Run权威状态"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="Chat Run ID",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_chat_runs_user"),
        index=True,
        comment="所属用户ID",
    )
    thread_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_threads.id", name="fk_chat_runs_thread"),
        index=True,
        comment="所属会话ID",
    )
    user_message_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_messages.id", name="fk_chat_runs_user_message"),
        comment="触发Run的user消息ID",
    )
    assistant_message_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("chat_messages.id", name="fk_chat_runs_assistant_message"),
        comment="Run输出assistant消息ID",
    )
    model_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_models.id", name="fk_chat_runs_model"),
        index=True,
        comment="冻结模型ID",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        comment="同用户Run幂等键",
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64),
        comment="Run请求Fingerprint",
    )
    status: Mapped[str] = mapped_column(String(32), comment="Run权威状态")
    last_event_sequence: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="最近持久SSE序号",
    )
    last_content_sequence: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="最近正文Checkpoint的SSE序号",
    )
    provider_snapshot: Mapped[dict] = mapped_column(
        JSON,
        comment="Provider/Credential/Model稳定快照",
    )
    capability_snapshot: Mapped[dict] = mapped_column(
        JSON,
        comment="模型能力快照",
    )
    pricing_snapshot: Mapped[dict] = mapped_column(
        JSON,
        comment="价格积分快照",
    )
    thinking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="当前Run是否显式启用Thinking",
    )
    provider_request_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Provider Request ID",
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    finish_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
        comment="用户请求停止时间（UTC）",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="稳定错误码",
    )
    error_reason: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="可安全展示的失败原因",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        onupdate=utc_now,
    )
