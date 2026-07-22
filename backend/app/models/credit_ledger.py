from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    UuidBinary,
    new_uuid7,
    utc_datetime_type,
    utc_now,
)


class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            "entry_type",
            name="uq_credit_ledger_user_idempotency_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(UuidBinary(), primary_key=True, default=new_uuid7)
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(), ForeignKey("users.id"), index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(UuidBinary(), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(40), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    related_entry_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(), ForeignKey("credit_ledger.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(utc_datetime_type(), default=utc_now)
