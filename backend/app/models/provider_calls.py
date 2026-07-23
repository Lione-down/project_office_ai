from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class ProviderCall(Base):
    __tablename__ = "provider_calls"
    __table_args__ = (
        UniqueConstraint(
            "brief_group_id",
            "attempt",
            name="uq_provider_calls_brief_attempt",
        ),
        {"comment": "Provider调用脱敏元数据表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Provider调用ID"
    )
    brief_group_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, comment="关联Brief稳定组ID"
    )
    brief_revision_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("briefs.id", name="fk_provider_calls_brief_revision"),
        nullable=True,
        index=True,
        comment="成功后关联的Brief修订行ID",
    )
    attempt: Mapped[int] = mapped_column(Integer, comment="调用尝试序号")
    provider_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_providers.id", name="fk_provider_calls_provider"),
        index=True,
        comment="Provider ID",
    )
    model_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_models.id", name="fk_provider_calls_model"),
        index=True,
        comment="模型ID",
    )
    credential_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("provider_credentials.id", name="fk_provider_calls_credential"),
        index=True,
        comment="Credential ID",
    )
    provider_request_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Provider Request ID"
    )
    status: Mapped[str] = mapped_column(String(32), comment="调用状态")
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, default=0, comment="输入Token数"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, comment="输出Token数"
    )
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, comment="总Token数")
    latency_ms: Mapped[int] = mapped_column(Integer, comment="调用耗时毫秒")
    cost_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True, comment="Provider费用（可空）"
    )
    error_category: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="脱敏错误分类"
    )
    is_redacted: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否已按安全策略脱敏"
    )
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="调用时间（UTC）"
    )
