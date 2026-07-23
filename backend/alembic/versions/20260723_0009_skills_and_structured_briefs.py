"""Add immutable Skills, Structured Briefs, and Provider call metadata.

Revision ID: 20260723_0009
Revises: 20260723_0008
Create Date: 2026-07-23 23:00:00
"""

from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20260723_0009"
down_revision = "20260723_0008"
branch_labels = None
depends_on = None


_BRIEF_FIELDS = [
    "module",
    "goal",
    "audience",
    "language",
    "domain",
    "tone",
    "source_asset_versions",
    "term_library_versions",
    "selected_skills",
    "selected_model",
    "output_plan",
    "facts",
    "inferences",
    "unresolved_items",
    "must_include",
    "must_exclude",
    "citation_policy",
]
_COMMON_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source_asset_versions",
        "term_library_versions",
        "selected_model",
        "user_requirements",
    ],
    "properties": {
        "source_asset_versions": {"type": "array", "minItems": 1, "maxItems": 20},
        "term_library_versions": {"type": "array"},
        "selected_model": {"type": "object"},
        "user_requirements": {"type": "object"},
    },
}
_BRIEF_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "office-ai://schemas/structured-brief.v1",
    "type": "object",
    "additionalProperties": False,
    "required": _BRIEF_FIELDS,
    "$defs": {
        "content_item": {
            "type": "object",
            "additionalProperties": False,
            "required": ["content", "source", "evidence_ids"],
            "properties": {
                "content": {"type": "string", "minLength": 1},
                "source": {
                    "enum": [
                        "user",
                        "file",
                        "calculation",
                        "agnes_inference",
                        "system_default",
                    ]
                },
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^e-[a-f0-9]{64}$"},
                },
            },
        }
    },
    "properties": {
        "module": {"enum": ["ppt", "excel", "combined"]},
        "goal": {"type": "string", "minLength": 1},
        "audience": {"type": "string", "minLength": 1},
        "language": {"const": "zh-CN"},
        "domain": {"const": "sales"},
        "tone": {"const": "professional"},
        "source_asset_versions": {"type": "array", "minItems": 1, "maxItems": 20},
        "term_library_versions": {"type": "array", "maxItems": 20},
        "selected_skills": {"type": "array", "minItems": 1, "maxItems": 2},
        "selected_model": {"type": "object"},
        "output_plan": {"type": "object"},
        "facts": {"type": "array", "items": {"$ref": "#/$defs/content_item"}},
        "inferences": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "unresolved_items": {"type": "array"},
        "must_include": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "must_exclude": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "citation_policy": {"type": "object"},
    },
}
_COMMON_CAPABILITIES = {
    "text_generation": True,
    "structured_output": True,
    "image_input": False,
    "max_context_tokens": 262_144,
}


def _skill_seed_payloads() -> tuple[dict, dict]:
    shared = {
        "version": "1.0.0",
        "kind": "user_workflow",
        "output_schema": _BRIEF_OUTPUT_SCHEMA,
        "capability_requirements": _COMMON_CAPABILITIES,
        "status": "published",
    }
    workflow = {
        "steps": [
            "select_evidence",
            "generate_structured_brief",
            "validate_and_repair_once",
            "persist_revision",
        ]
    }
    return (
        {
            **shared,
            "skill_code": "ppt.sales-business-review.v1",
            "display_name": "销售经营汇报",
            "description": "从销售材料生成证据约束的经营汇报 Structured Brief。",
            "output_kind": "pptx",
            "input_schema": {
                **_COMMON_INPUT_SCHEMA,
                "x-supported-inputs": [
                    "xlsx",
                    "xlsm",
                    "pdf",
                    "docx",
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                    "txt",
                    "md",
                ],
            },
            "workflow": {**workflow, "output": "pptx"},
        },
        {
            **shared,
            "skill_code": "excel.sales-analysis-dashboard.v1",
            "display_name": "销售数据分析与经营看板",
            "description": "从销售材料生成证据约束的分析看板 Structured Brief。",
            "output_kind": "xlsx",
            "input_schema": {
                **_COMMON_INPUT_SCHEMA,
                "x-supported-inputs": [
                    "xlsx",
                    "xlsm",
                    "csv",
                    "pdf",
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                    "txt",
                    "md",
                ],
            },
            "workflow": {**workflow, "output": "xlsx"},
        },
    )


def _skill_checksum(payload: dict) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _uuid_literal(value: str):
    return sa.literal_column(f"X'{UUID(value).hex}'")


def upgrade() -> None:
    skills = op.create_table(
        "skills",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="Skill版本行ID"),
        sa.Column(
            "skill_code", sa.String(128), nullable=False, comment="Skill稳定代码"
        ),
        sa.Column("version", sa.String(32), nullable=False, comment="Skill SemVer版本"),
        sa.Column("kind", sa.String(32), nullable=False, comment="Skill类型"),
        sa.Column(
            "display_name", sa.String(128), nullable=False, comment="Skill显示名称"
        ),
        sa.Column("description", sa.Text(), nullable=False, comment="Skill说明"),
        sa.Column("output_kind", sa.String(16), nullable=False, comment="输出文件类型"),
        sa.Column("input_schema", sa.JSON(), nullable=False, comment="输入JSON Schema"),
        sa.Column(
            "output_schema", sa.JSON(), nullable=False, comment="输出JSON Schema"
        ),
        sa.Column("workflow", sa.JSON(), nullable=False, comment="固定工作流"),
        sa.Column(
            "capability_requirements",
            sa.JSON(),
            nullable=False,
            comment="模型能力要求",
        ),
        sa.Column("status", sa.String(20), nullable=False, comment="发布状态"),
        sa.Column("checksum", sa.String(64), nullable=False, comment="版本内容SHA-256"),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="发布时间（UTC）"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_code", "version", name="uq_skills_code_version"),
        comment="不可变Skill版本表",
    )
    published_at = datetime(2026, 7, 23, 23, 0, 0)
    skill_ids = (
        "019f4000-0000-7000-8000-000000000101",
        "019f4000-0000-7000-8000-000000000102",
    )
    for skill_id, skill in zip(skill_ids, _skill_seed_payloads(), strict=True):
        op.execute(
            skills.insert().values(
                **{
                    "id": _uuid_literal(skill_id),
                    "skill_code": skill["skill_code"],
                    "version": skill["version"],
                    "kind": skill["kind"],
                    "display_name": skill["display_name"],
                    "description": skill["description"],
                    "output_kind": skill["output_kind"],
                    "input_schema": op.inline_literal(
                        json.dumps(
                            skill["input_schema"],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    "output_schema": op.inline_literal(
                        json.dumps(
                            skill["output_schema"],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    "workflow": op.inline_literal(
                        json.dumps(
                            skill["workflow"],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    "capability_requirements": op.inline_literal(
                        json.dumps(
                            skill["capability_requirements"],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    "status": skill["status"],
                    "checksum": _skill_checksum(skill),
                    "created_at": published_at,
                }
            )
        )

    op.create_table(
        "briefs",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="Brief修订行ID"),
        sa.Column(
            "brief_group_id", sa.BINARY(16), nullable=False, comment="Brief稳定组ID"
        ),
        sa.Column("revision", sa.Integer(), nullable=False, comment="不可变修订号"),
        sa.Column("user_id", sa.BINARY(16), nullable=False, comment="所属用户ID"),
        sa.Column("project_id", sa.BINARY(16), nullable=False, comment="所属项目ID"),
        sa.Column(
            "selected_model_id", sa.BINARY(16), nullable=False, comment="选择的模型ID"
        ),
        sa.Column("source_snapshot", sa.JSON(), nullable=False, comment="输入版本快照"),
        sa.Column("content", sa.JSON(), nullable=False, comment="Structured Brief内容"),
        sa.Column(
            "content_checksum",
            sa.String(64),
            nullable=False,
            comment="Brief内容SHA-256",
        ),
        sa.Column("status", sa.String(20), nullable=False, comment="Brief修订状态"),
        sa.Column(
            "confirmed_at",
            _utc_datetime(),
            nullable=True,
            comment="用户确认时间（UTC）",
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="修订创建时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_briefs_project"
        ),
        sa.ForeignKeyConstraint(
            ["selected_model_id"],
            ["ai_models.id"],
            name="fk_briefs_selected_model",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_briefs_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brief_group_id", "revision", name="uq_briefs_group_revision"
        ),
        comment="Structured Brief不可变修订表",
    )
    op.create_index("ix_briefs_brief_group_id", "briefs", ["brief_group_id"])
    op.create_index("ix_briefs_user_id", "briefs", ["user_id"])
    op.create_index("ix_briefs_project_id", "briefs", ["project_id"])
    op.create_index("ix_briefs_selected_model_id", "briefs", ["selected_model_id"])

    op.create_table(
        "provider_calls",
        sa.Column("id", sa.BINARY(16), nullable=False, comment="Provider调用ID"),
        sa.Column(
            "brief_group_id", sa.BINARY(16), nullable=False, comment="关联Brief稳定组ID"
        ),
        sa.Column(
            "brief_revision_id",
            sa.BINARY(16),
            nullable=True,
            comment="成功后关联的Brief修订行ID",
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, comment="调用尝试序号"),
        sa.Column("provider_id", sa.BINARY(16), nullable=False, comment="Provider ID"),
        sa.Column("model_id", sa.BINARY(16), nullable=False, comment="模型ID"),
        sa.Column(
            "credential_id", sa.BINARY(16), nullable=False, comment="Credential ID"
        ),
        sa.Column(
            "provider_request_id",
            sa.String(255),
            nullable=True,
            comment="Provider Request ID",
        ),
        sa.Column("status", sa.String(32), nullable=False, comment="调用状态"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, comment="输入Token数"),
        sa.Column(
            "completion_tokens", sa.Integer(), nullable=False, comment="输出Token数"
        ),
        sa.Column("total_tokens", sa.Integer(), nullable=False, comment="总Token数"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, comment="调用耗时毫秒"),
        sa.Column(
            "cost_amount",
            sa.Numeric(12, 6),
            nullable=True,
            comment="Provider费用（可空）",
        ),
        sa.Column(
            "error_category", sa.String(64), nullable=True, comment="脱敏错误分类"
        ),
        sa.Column(
            "is_redacted", sa.Boolean(), nullable=False, comment="是否已按安全策略脱敏"
        ),
        sa.Column(
            "created_at", _utc_datetime(), nullable=False, comment="调用时间（UTC）"
        ),
        sa.ForeignKeyConstraint(
            ["brief_revision_id"],
            ["briefs.id"],
            name="fk_provider_calls_brief_revision",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["provider_credentials.id"],
            name="fk_provider_calls_credential",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["ai_models.id"], name="fk_provider_calls_model"
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_providers.id"],
            name="fk_provider_calls_provider",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "brief_group_id",
            "attempt",
            name="uq_provider_calls_brief_attempt",
        ),
        comment="Provider调用脱敏元数据表",
    )
    op.create_index(
        "ix_provider_calls_brief_group_id", "provider_calls", ["brief_group_id"]
    )
    op.create_index(
        "ix_provider_calls_brief_revision_id",
        "provider_calls",
        ["brief_revision_id"],
    )
    op.create_index("ix_provider_calls_provider_id", "provider_calls", ["provider_id"])
    op.create_index("ix_provider_calls_model_id", "provider_calls", ["model_id"])
    op.create_index(
        "ix_provider_calls_credential_id", "provider_calls", ["credential_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_provider_calls_credential_id", table_name="provider_calls")
    op.drop_index("ix_provider_calls_model_id", table_name="provider_calls")
    op.drop_index("ix_provider_calls_provider_id", table_name="provider_calls")
    op.drop_index("ix_provider_calls_brief_revision_id", table_name="provider_calls")
    op.drop_index("ix_provider_calls_brief_group_id", table_name="provider_calls")
    op.drop_table("provider_calls")
    op.drop_index("ix_briefs_selected_model_id", table_name="briefs")
    op.drop_index("ix_briefs_project_id", table_name="briefs")
    op.drop_index("ix_briefs_user_id", table_name="briefs")
    op.drop_index("ix_briefs_brief_group_id", table_name="briefs")
    op.drop_table("briefs")
    op.drop_table("skills")
