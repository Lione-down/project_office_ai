"""Add the certified presentation template catalog.

Revision ID: 20260729_0018
Revises: 20260729_0017
Create Date: 2026-07-29 16:45:00
"""

from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260729_0018"
down_revision = "20260729_0017"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _uuid():
    return sa.BINARY(16)


def _uuid_literal(value: str):
    return sa.literal_column(f"X'{UUID(value).hex}'")


def _payload(
    *,
    code: str,
    name: str,
    category: str,
    description: str,
    style_keywords: list[str],
    use_cases: list[str],
    colors: list[str],
    compatible_skills: list[str],
    renderer: dict[str, str],
) -> dict:
    preview_root = f"/template-previews/{code}"
    return {
        "schema_version": "presentation-template-catalog.v1",
        "template_code": code,
        "version": "1.0.0",
        "name": name,
        "category": category,
        "description": description,
        "style_keywords": style_keywords,
        "use_cases": use_cases,
        "colors": colors,
        "fonts": ["Microsoft YaHei"],
        "layouts": ["title", "content", "section", "closing"],
        "compatible_skills": compatible_skills,
        "cover_url": f"{preview_root}/cover.svg",
        "representative_urls": [f"{preview_root}/representative.svg"],
        "source": {
            "kind": "system_original",
            "license": "Office AI Original",
            "attribution": "Office AI Design System",
        },
        "renderer": renderer,
    }


def _checksum(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _templates() -> list[tuple[str, dict]]:
    return [
        (
            "019fad00-0000-7000-8000-000000000301",
            _payload(
                code="ppt.executive-blue.v1",
                name="高管钢蓝",
                category="management",
                description="克制留白与清晰层级兼顾的管理层沟通模板。",
                style_keywords=["克制", "专业", "清晰"],
                use_cases=["管理层汇报", "知识培训", "方案沟通"],
                colors=["#F5F8FC", "#123B6D", "#2F6FB0", "#29A3A3"],
                compatible_skills=[
                    "ppt.sales-business-review.v1",
                    "ppt.knowledge-education.v1",
                ],
                renderer={
                    "background": "F5F8FC",
                    "surface": "FFFFFF",
                    "primary": "123B6D",
                    "secondary": "2F6FB0",
                    "accent": "29A3A3",
                    "text": "172033",
                    "muted": "64748B",
                },
            ),
        ),
        (
            "019fad00-0000-7000-8000-000000000302",
            _payload(
                code="ppt.operating-review.v1",
                name="经营复盘",
                category="operating-review",
                description="围绕目标、差距、原因与行动项组织经营复盘。",
                style_keywords=["复盘", "行动", "稳健"],
                use_cases=["销售经营汇报", "季度复盘", "行动计划"],
                colors=["#FBF9F6", "#8B1E1E", "#B33A3A", "#C89B3C"],
                compatible_skills=["ppt.sales-business-review.v1"],
                renderer={
                    "background": "FBF9F6",
                    "surface": "FFFFFF",
                    "primary": "8B1E1E",
                    "secondary": "B33A3A",
                    "accent": "C89B3C",
                    "text": "2B211F",
                    "muted": "7D6C68",
                },
            ),
        ),
        (
            "019fad00-0000-7000-8000-000000000303",
            _payload(
                code="ppt.data-story.v1",
                name="数据叙事",
                category="data-story",
                description="用指标层级、对比关系和结论强调构建数据故事。",
                style_keywords=["数据", "叙事", "洞察"],
                use_cases=["指标分析", "趋势解读", "研究分享"],
                colors=["#F8F6FC", "#3D2C68", "#7357A8", "#DD6B7B"],
                compatible_skills=[
                    "ppt.sales-business-review.v1",
                    "ppt.knowledge-education.v1",
                ],
                renderer={
                    "background": "F8F6FC",
                    "surface": "FFFFFF",
                    "primary": "3D2C68",
                    "secondary": "7357A8",
                    "accent": "DD6B7B",
                    "text": "251F32",
                    "muted": "746B84",
                },
            ),
        ),
    ]


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column(
            "checksum",
            sa.String(64),
            nullable=True,
            comment="模板目录合同SHA-256",
        ),
    )
    template_table = sa.table(
        "templates",
        sa.column("id", _uuid()),
        sa.column("owner_user_id", _uuid()),
        sa.column("preview_asset_id", _uuid()),
        sa.column("template_code", sa.String()),
        sa.column("template_type", sa.String()),
        sa.column("source", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("style_keywords", sa.JSON()),
        sa.column("design_config", sa.JSON()),
        sa.column("version", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("usage_count", sa.Integer()),
        sa.column("checksum", sa.String()),
        sa.column("created_at", _utc_datetime()),
        sa.column("updated_at", _utc_datetime()),
    )
    created_at = datetime(2026, 7, 29, 16, 45, 0)
    for sort_order, (template_id, payload) in enumerate(_templates(), start=1):
        op.execute(
            template_table.insert().values(
                id=_uuid_literal(template_id),
                owner_user_id=None,
                preview_asset_id=None,
                template_code=payload["template_code"],
                template_type="pptx",
                source="system_original",
                display_name=payload["name"],
                category=payload["category"],
                style_keywords=op.inline_literal(
                    json.dumps(
                        payload["style_keywords"],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                ),
                design_config=op.inline_literal(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                ),
                version=1,
                status="published",
                sort_order=sort_order,
                usage_count=0,
                checksum=_checksum(payload),
                created_at=created_at,
                updated_at=created_at,
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM templates WHERE id IN (:first_id, :second_id, :third_id)"
        ).bindparams(
            first_id=UUID("019fad00-0000-7000-8000-000000000301").bytes,
            second_id=UUID("019fad00-0000-7000-8000-000000000302").bytes,
            third_id=UUID("019fad00-0000-7000-8000-000000000303").bytes,
        )
    )
    op.drop_column("templates", "checksum")
