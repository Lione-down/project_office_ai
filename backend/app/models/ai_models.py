from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class AiModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "model_code",
            "credential_id",
            name="uq_ai_models_provider_code_credential",
        ),
        {"comment": "AI模型注册表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="模型ID（UUIDv7二进制）",
    )
    provider_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_providers.id", name="fk_ai_models_provider"),
        index=True,
        comment="Provider ID",
    )
    credential_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("provider_credentials.id", name="fk_ai_models_credential"),
        index=True,
        comment="Credential ID",
    )
    model_code: Mapped[str] = mapped_column(String(128), comment="Provider模型代码")
    display_name: Mapped[str] = mapped_column(String(128), comment="模型显示名称")
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict, comment="模型能力")
    context_window: Mapped[int] = mapped_column(Integer, comment="Context窗口Token数")
    max_output_tokens: Mapped[int] = mapped_column(Integer, comment="最大输出Token数")
    user_visible: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否用户可见"
    )
    is_recommended: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否推荐模型"
    )
    credit_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("1.0000"), comment="积分倍率"
    )
    allowed_skills: Mapped[list] = mapped_column(
        JSON, default=list, comment="允许的Skill代码"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="模型状态"
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
