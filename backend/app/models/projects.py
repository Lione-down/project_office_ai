from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Computed, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint(
            "active_default_owner_id", name="uq_projects_active_default_owner"
        ),
        {"comment": "用户项目表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="项目ID（UUIDv7二进制）",
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_projects_user"),
        index=True,
        comment="所属用户ID",
    )
    name: Mapped[str] = mapped_column(String(128), comment="项目名称")
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否默认项目"
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已归档"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        utc_datetime_type(), nullable=True, comment="软删除时间（UTC）"
    )
    active_default_owner_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        Computed(
            "CASE WHEN is_default = 1 AND deleted_at IS NULL THEN user_id ELSE NULL END"
        ),
        nullable=True,
        comment="活动默认项目用户唯一键",
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
