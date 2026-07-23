from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class TermLibrary(Base):
    __tablename__ = "term_libraries"
    __table_args__ = (
        UniqueConstraint(
            "library_id",
            "version",
            name="uq_term_libraries_library_version",
        ),
        {"comment": "个人术语库不可变版本表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        primary_key=True,
        default=new_uuid7,
        comment="术语库版本行ID",
    )
    library_id: Mapped[UUID] = mapped_column(
        UuidBinary(), index=True, comment="术语库稳定ID"
    )
    user_id: Mapped[UUID] = mapped_column(
        UuidBinary(),
        ForeignKey("users.id", name="fk_term_libraries_user"),
        index=True,
        comment="所属用户ID",
    )
    project_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("projects.id", name="fk_term_libraries_project"),
        nullable=True,
        index=True,
        comment="可选项目覆盖范围",
    )
    previous_version_id: Mapped[UUID | None] = mapped_column(
        UuidBinary(),
        ForeignKey("term_libraries.id", name="fk_term_libraries_previous_version"),
        nullable=True,
        comment="前一不可变版本行ID",
    )
    name: Mapped[str] = mapped_column(String(128), comment="术语库名称")
    description: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="术语库说明"
    )
    status: Mapped[str] = mapped_column(String(20), comment="术语库版本状态")
    version: Mapped[int] = mapped_column(Integer, comment="术语库版本号")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="版本创建时间（UTC）"
    )
