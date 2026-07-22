from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[UUID] = mapped_column(UuidBinary(), primary_key=True, default=new_uuid7)
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(), ForeignKey("users.id"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(utc_datetime_type())
    revoked_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(utc_datetime_type(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, onupdate=utc_now
    )
