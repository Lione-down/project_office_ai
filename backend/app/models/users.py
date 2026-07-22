from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("phone_country_code", "phone_number", name="uq_users_phone"),
    )

    id: Mapped[UUID] = mapped_column(UuidBinary(), primary_key=True, default=new_uuid7)
    phone_country_code: Mapped[str] = mapped_column(String(8), default="+86")
    phone_number: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(20), default="user")
    status: Mapped[str] = mapped_column(String(20), default="active")
    password_hash: Mapped[str] = mapped_column(String(255))
    credit_balance: Mapped[int] = mapped_column(Integer, default=0)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    invite_code_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(), ForeignKey("invite_codes.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(utc_datetime_type(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, onupdate=utc_now
    )
