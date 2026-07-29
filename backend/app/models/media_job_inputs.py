from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class MediaJobInput(Base):
    __tablename__ = "media_job_inputs"
    __table_args__ = (
        UniqueConstraint(
            "media_job_id",
            "input_kind",
            "source_asset_id",
            "sequence",
            name="uq_media_job_inputs_job_source",
        ),
        {"comment": "媒体任务不可变输入关系"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="媒体输入ID"
    )
    media_job_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("media_jobs.id", name="fk_media_job_inputs_job"),
        index=True,
        comment="媒体任务ID",
    )
    input_kind: Mapped[str] = mapped_column(String(32), comment="输入类型")
    source_asset_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("file_assets.id", name="fk_media_job_inputs_asset"),
        index=True,
        comment="Owner-scoped输入资产ID",
    )
    source_asset_version: Mapped[int] = mapped_column(Integer, comment="输入资产版本")
    source_sha256: Mapped[str] = mapped_column(String(64), comment="输入资产SHA-256")
    slide_id: Mapped[UUID] = mapped_column(UuidBinary(), comment="稳定Slide ID")
    sequence: Mapped[int] = mapped_column(Integer, comment="输入顺序")
    purpose: Mapped[str] = mapped_column(String(32), comment="输入用途")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
