from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "template_code",
            "version",
            name="uq_templates_source_code_version",
        ),
        {"comment": "版本化模板注册表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="模板版本ID（UUIDv7二进制）",
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_templates_owner"),
        nullable=True,
        index=True,
        comment="未来用户模板所有者；系统模板为空",
    )
    preview_asset_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("file_assets.id", name="fk_templates_preview_asset"),
        nullable=True,
        index=True,
        comment="可选预览资产ID",
    )
    template_code: Mapped[str] = mapped_column(
        String(128), comment="跨版本稳定模板代码"
    )
    template_type: Mapped[str] = mapped_column(
        String(32), index=True, comment="模板类型"
    )
    source: Mapped[str] = mapped_column(
        String(32), default="system", comment="模板来源"
    )
    display_name: Mapped[str] = mapped_column(String(128), comment="模板显示名称")
    category: Mapped[str] = mapped_column(String(64), index=True, comment="模板分类")
    style_keywords: Mapped[list] = mapped_column(
        JSON, default=list, comment="样式关键词列表"
    )
    design_config: Mapped[dict] = mapped_column(
        JSON, default=dict, comment="非敏感设计配置"
    )
    version: Mapped[int] = mapped_column(Integer, comment="模板版本")
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True, comment="模板状态"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="展示排序序号")
    usage_count: Mapped[int] = mapped_column(Integer, default=0, comment="累计使用次数")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="创建时间（UTC）"
    )
    updated_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(),
        default=utc_now,
        onupdate=utc_now,
        comment="更新时间（UTC）",
    )
