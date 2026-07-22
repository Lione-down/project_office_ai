from datetime import UTC, datetime
import secrets
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects.mysql import BINARY, DATETIME
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


def new_uuid7() -> UUID:
    timestamp_ms = int(datetime.now(UTC).timestamp() * 1000)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        (timestamp_ms << 80) | (0x7 << 76) | (random_a << 64) | (0b10 << 62) | random_b
    )
    return UUID(int=value)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def utc_datetime_type():
    return DateTime().with_variant(DATETIME(fsp=6), "mysql")


class UuidBinary(TypeDecorator[UUID]):
    impl = BINARY(16)
    cache_ok = True

    def process_bind_param(self, value: UUID | str | None, dialect) -> bytes | None:
        if value is None:
            return None
        return (value if isinstance(value, UUID) else UUID(str(value))).bytes

    def process_result_value(self, value: bytes | None, dialect) -> UUID | None:
        return UUID(bytes=value) if value is not None else None


class Base(DeclarativeBase):
    def __init__(self, **kwargs: object) -> None:
        if hasattr(type(self), "id") and "id" not in kwargs:
            kwargs["id"] = new_uuid7()
        for field_name, value in kwargs.items():
            if not hasattr(type(self), field_name):
                raise TypeError(
                    f"{field_name!r} is not a mapped field on {type(self).__name__}"
                )
            setattr(self, field_name, value)
