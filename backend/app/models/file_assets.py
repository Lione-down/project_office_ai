from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class FileAsset(Base):
    __tablename__ = "file_assets"
    __table_args__ = (
        UniqueConstraint(
            "storage_provider",
            "storage_key",
            name="uq_file_assets_storage_location",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_file_assets_user_idempotency",
        ),
        {"comment": "文件资产表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="资产ID（UUIDv7二进制）",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_file_assets_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_file_assets_project"),
        index=True,
        comment="所属项目ID",
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), comment="清理后的原始文件名"
    )
    file_category: Mapped[str] = mapped_column(String(32), comment="文件分类")
    mime_type: Mapped[str] = mapped_column(String(128), comment="初检MIME类型")
    byte_size: Mapped[int] = mapped_column(BigInteger, comment="文件字节数")
    sha256: Mapped[str] = mapped_column(String(64), index=True, comment="SHA-256摘要")
    storage_provider: Mapped[str] = mapped_column(String(32), comment="存储Provider")
    storage_key: Mapped[str] = mapped_column(String(768), comment="存储定位键")
    processing_status: Mapped[str] = mapped_column(
        String(32), index=True, comment="资产处理状态"
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="用户上传幂等键"
    )
    parent_asset_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("file_assets.id", name="fk_file_assets_parent"),
        nullable=True,
        comment="父版本资产ID",
    )
    generated_task_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(), nullable=True, comment="生成任务ID"
    )
    manifest_key: Mapped[str | None] = mapped_column(
        String(768), nullable=True, comment="Evidence Manifest存储键"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="软删除时间（UTC）"
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
