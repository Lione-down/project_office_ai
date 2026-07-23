from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String, UniqueConstraint
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
        UuidBinary(),
        ForeignKey("generation_tasks.id", name="fk_file_assets_generated_task"),
        nullable=True,
        comment="生成任务ID",
    )
    manifest_key: Mapped[str | None] = mapped_column(
        String(768), nullable=True, comment="Evidence Manifest存储键"
    )
    manifest_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Evidence Manifest状态"
    )
    manifest_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="Evidence Manifest SHA-256摘要"
    )
    manifest_schema_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Evidence Manifest Schema版本"
    )
    evidence_engine_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="证据生成引擎版本"
    )
    evidence_warning_count: Mapped[int | None] = mapped_column(
        nullable=True, comment="Evidence Manifest告警数量"
    )
    evidence_blocker_count: Mapped[int | None] = mapped_column(
        nullable=True, comment="Evidence Manifest阻断数量"
    )
    evidence_generated_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="证据生成完成时间（UTC）"
    )
    processing_retry_count: Mapped[int] = mapped_column(
        default=0, comment="处理重试次数"
    )
    processing_retry_after: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="下次允许重试时间（UTC）"
    )
    parsed_storage_key: Mapped[str | None] = mapped_column(
        String(768), nullable=True, comment="解析结果存储键"
    )
    parser_name: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="安全解析器名称"
    )
    parser_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="安全解析器版本"
    )
    processing_warnings: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=list, comment="解析告警代码列表"
    )
    processing_error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="处理错误代码"
    )
    processing_error_message: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="脱敏处理错误"
    )
    quality_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True, comment="质量门禁状态"
    )
    quality_report_key: Mapped[str | None] = mapped_column(
        String(768), nullable=True, comment="版本化质量报告存储键"
    )
    quality_report_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="质量报告SHA-256摘要"
    )
    quality_report_schema_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="质量报告Schema版本"
    )
    quality_engine_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="质量引擎版本"
    )
    quality_preview_keys: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=list, comment="PDF与逐页预览存储键"
    )
    quality_validated_key: Mapped[str | None] = mapped_column(
        String(768), nullable=True, comment="通过质量门禁的下载文件键"
    )
    quality_validated_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="通过质量门禁文件SHA-256摘要"
    )
    quality_validated_byte_size: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="通过质量门禁文件字节数"
    )
    quality_repair_attempt_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="确定性自动修复次数"
    )
    quality_checked_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="质量门禁完成时间（UTC）"
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="处理开始时间（UTC）"
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="处理完成时间（UTC）"
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
