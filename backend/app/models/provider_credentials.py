from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "key_fingerprint",
            name="uq_provider_credentials_provider_fingerprint",
        ),
        {"comment": "Provider Credential表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="Credential ID（UUIDv7二进制）",
    )
    provider_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_providers.id", name="fk_provider_credentials_provider"),
        index=True,
        comment="Provider ID",
    )
    name: Mapped[str] = mapped_column(String(128), comment="Credential名称")
    encrypted_key: Mapped[str] = mapped_column(Text, comment="应用层加密API Key")
    key_fingerprint: Mapped[str] = mapped_column(
        String(64), comment="API Key不可逆Fingerprint"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="Credential状态"
    )
    rpm_limit: Mapped[int] = mapped_column(Integer, comment="每分钟请求上限")
    tpm_limit: Mapped[int] = mapped_column(Integer, comment="每分钟Token上限")
    max_concurrency: Mapped[int] = mapped_column(Integer, comment="最大并发数")
    last_test_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="最近测试状态"
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="最近测试时间（UTC）"
    )
    rotation_source: Mapped[str] = mapped_column(String(64), comment="密钥轮换来源")
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_provider_credentials_creator"),
        nullable=True,
        comment="创建管理员ID",
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
