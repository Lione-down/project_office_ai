from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class MediaJob(Base):
    __tablename__ = "media_jobs"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_media_jobs_user_idempotency",
        ),
        UniqueConstraint(
            "provider_id",
            "provider_job_id",
            name="uq_media_jobs_provider_job",
        ),
        {"comment": "Owner-scoped媒体生成任务"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="媒体任务ID"
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_media_jobs_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_media_jobs_project"),
        index=True,
        comment="所属项目ID",
    )
    draft_revision_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("deck_draft_revisions.id", name="fk_media_jobs_deck_revision"),
        index=True,
        comment="冻结Deck Revision ID",
    )
    slide_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, comment="稳定Slide ID"
    )
    workflow_task_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("workflow_tasks.id", name="fk_media_jobs_workflow_task"),
        unique=True,
        comment="权威Workflow Task ID",
    )
    supersedes_job_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("media_jobs.id", name="fk_media_jobs_supersedes"),
        nullable=True,
        index=True,
        comment="被替换的历史媒体任务ID",
    )
    kind: Mapped[str] = mapped_column(String(16), comment="image或video")
    mode: Mapped[str] = mapped_column(
        String(32), comment="text-to-image或image-to-image"
    )
    action: Mapped[str] = mapped_column(
        String(16), comment="generate/replace/regenerate"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), comment="用户创建幂等键")
    request_fingerprint: Mapped[str] = mapped_column(
        String(64), comment="请求Fingerprint"
    )
    prompt_content: Mapped[str] = mapped_column(
        Text, comment="用户确认的owner-scoped媒体Prompt"
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), comment="媒体Prompt SHA-256")
    alt_text: Mapped[str] = mapped_column(String(500), comment="图片替代文本")
    crop_mode: Mapped[str] = mapped_column(String(16), comment="contain或cover")
    provider_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_providers.id", name="fk_media_jobs_provider"),
        index=True,
        comment="冻结Provider ID",
    )
    credential_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("provider_credentials.id", name="fk_media_jobs_credential"),
        comment="冻结Credential ID",
    )
    model_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("ai_models.id", name="fk_media_jobs_model"),
        index=True,
        comment="冻结Model ID",
    )
    model_snapshot: Mapped[dict] = mapped_column(JSON, comment="模型身份快照")
    capability_snapshot: Mapped[dict] = mapped_column(JSON, comment="能力快照")
    pricing_snapshot: Mapped[dict] = mapped_column(JSON, comment="价格与积分快照")
    status: Mapped[str] = mapped_column(String(32), index=True, comment="媒体任务状态")
    progress: Mapped[int] = mapped_column(Integer, comment="真实持久进度")
    provider_job_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Provider opaque ID"
    )
    requested_size: Mapped[str] = mapped_column(String(16), comment="请求尺寸档位")
    requested_ratio: Mapped[str] = mapped_column(String(16), comment="请求宽高比")
    actual_width: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="解码后的实际宽度"
    )
    actual_height: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="解码后的实际高度"
    )
    output_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="实际输出SHA-256"
    )
    output_asset_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="不可变资产版本"
    )
    estimated_credits: Mapped[int] = mapped_column(Integer, comment="确认时预计积分")
    reserved_credits: Mapped[int] = mapped_column(Integer, comment="实际预留积分")
    error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="稳定错误码"
    )
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="脱敏错误说明"
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="取消请求时间（UTC）"
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="Provider提交时间（UTC）"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="终态时间（UTC）"
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
