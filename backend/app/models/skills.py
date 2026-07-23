from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UuidBinary, new_uuid7, utc_datetime_type, utc_now


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("skill_code", "version", name="uq_skills_code_version"),
        {"comment": "不可变Skill版本表"},
    )

    id: Mapped[UUID] = mapped_column(
        UuidBinary(), primary_key=True, default=new_uuid7, comment="Skill版本行ID"
    )
    skill_code: Mapped[str] = mapped_column(String(128), comment="Skill稳定代码")
    version: Mapped[str] = mapped_column(String(32), comment="Skill SemVer版本")
    kind: Mapped[str] = mapped_column(String(32), comment="Skill类型")
    display_name: Mapped[str] = mapped_column(String(128), comment="Skill显示名称")
    description: Mapped[str] = mapped_column(Text, comment="Skill说明")
    output_kind: Mapped[str] = mapped_column(String(16), comment="输出文件类型")
    input_schema: Mapped[dict] = mapped_column(JSON, comment="输入JSON Schema")
    output_schema: Mapped[dict] = mapped_column(JSON, comment="输出JSON Schema")
    workflow: Mapped[dict] = mapped_column(JSON, comment="固定工作流")
    capability_requirements: Mapped[dict] = mapped_column(JSON, comment="模型能力要求")
    status: Mapped[str] = mapped_column(String(20), comment="发布状态")
    checksum: Mapped[str] = mapped_column(String(64), comment="版本内容SHA-256")
    created_at: Mapped[datetime] = mapped_column(
        utc_datetime_type(), default=utc_now, comment="发布时间（UTC）"
    )
