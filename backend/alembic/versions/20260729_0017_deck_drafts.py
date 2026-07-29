"""Add versioned Deck Drafts and the knowledge education Skill.

Revision ID: 20260729_0017
Revises: 20260729_0016
Create Date: 2026-07-29 15:00:00
"""

from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260729_0017"
down_revision = "20260729_0016"
branch_labels = None
depends_on = None


def _utc_datetime():
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def _uuid():
    return sa.BINARY(16)


def _uuid_literal(value: str):
    return sa.literal_column(f"X'{UUID(value).hex}'")


def _knowledge_skill() -> dict:
    return {
        "skill_code": "ppt.knowledge-education.v1",
        "version": "1.0.0",
        "kind": "user_workflow",
        "display_name": "知识科普与培训",
        "description": "把用户输入、Agnes推断和可选Evidence组织为可编辑的知识型演示。",
        "output_kind": "pptx",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "topic",
                "audience",
                "slide_count",
                "language",
                "style",
                "source_mode",
                "selected_model",
            ],
            "properties": {
                "topic": {"type": "string", "minLength": 1, "maxLength": 500},
                "audience": {"type": "string", "minLength": 1, "maxLength": 500},
                "slide_count": {"type": "integer", "minimum": 3, "maximum": 40},
                "language": {"const": "zh-CN"},
                "style": {"type": "string", "minLength": 1, "maxLength": 500},
                "source_mode": {"enum": ["inspiration", "materials", "mixed"]},
                "selected_model": {"type": "object"},
            },
        },
        "output_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "office-ai://schemas/deck-brief.v1",
            "type": "object",
            "additionalProperties": False,
            "required": [
                "schema_version",
                "topic",
                "audience",
                "language",
                "style",
                "source_mode",
                "skill_code",
                "slides",
            ],
            "properties": {
                "schema_version": {"const": "deck-brief.v1"},
                "slides": {"type": "array", "minItems": 3, "maxItems": 40},
            },
        },
        "workflow": {
            "steps": [
                "build_ppt_outline",
                "validate_and_repair_once",
                "persist_deck_revision",
                "run_deck_preflight",
                "submit_ppt_generation",
            ],
            "output": "pptx",
        },
        "capability_requirements": {
            "text_generation": True,
            "structured_output": True,
            "image_input": False,
            "max_context_tokens": 262_144,
        },
        "status": "published",
    }


def _checksum(payload: dict) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    drafts = op.create_table(
        "deck_drafts",
        sa.Column("id", _uuid(), nullable=False, comment="Deck Draft ID"),
        sa.Column("user_id", _uuid(), nullable=False, comment="所属用户ID"),
        sa.Column("project_id", _uuid(), nullable=False, comment="所属项目ID"),
        sa.Column("thread_id", _uuid(), nullable=False, comment="来源Chat会话ID"),
        sa.Column(
            "source_message_id",
            _uuid(),
            nullable=False,
            comment="成功assistant来源消息ID",
        ),
        sa.Column(
            "draft_group_id",
            _uuid(),
            nullable=False,
            comment="稳定Draft Identity",
        ),
        sa.Column(
            "latest_revision",
            sa.Integer(),
            nullable=False,
            comment="最新不可变Revision",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            comment="Draft生命周期状态",
        ),
        sa.Column(
            "idempotency_key",
            sa.String(128),
            nullable=False,
            comment="创建请求幂等键",
        ),
        sa.Column(
            "request_fingerprint",
            sa.String(64),
            nullable=False,
            comment="创建请求Fingerprint",
        ),
        sa.Column("deleted_at", _utc_datetime(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.Column("updated_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_deck_drafts_project",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["chat_messages.id"],
            name="fk_deck_drafts_source_message",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_deck_drafts_thread",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_deck_drafts_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "draft_group_id",
            name="uq_deck_drafts_owner_identity",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_deck_drafts_user_idempotency",
        ),
        sa.UniqueConstraint(
            "user_id",
            "source_message_id",
            name="uq_deck_drafts_user_source_message",
        ),
        comment="Owner-scoped Deck Draft稳定Identity",
    )
    op.create_index("ix_deck_drafts_user_id", drafts.name, ["user_id"])
    op.create_index("ix_deck_drafts_project_id", drafts.name, ["project_id"])
    op.create_index("ix_deck_drafts_thread_id", drafts.name, ["thread_id"])
    op.create_index(
        "ix_deck_drafts_source_message_id",
        drafts.name,
        ["source_message_id"],
    )
    op.create_index(
        "ix_deck_drafts_draft_group_id",
        drafts.name,
        ["draft_group_id"],
    )
    op.create_index("ix_deck_drafts_status", drafts.name, ["status"])

    revisions = op.create_table(
        "deck_draft_revisions",
        sa.Column("id", _uuid(), nullable=False, comment="Deck Revision ID"),
        sa.Column("draft_id", _uuid(), nullable=False, comment="所属Draft ID"),
        sa.Column(
            "revision", sa.Integer(), nullable=False, comment="不可变Revision序号"
        ),
        sa.Column(
            "content", sa.JSON(), nullable=False, comment="严格deck-brief.v1内容"
        ),
        sa.Column(
            "content_checksum",
            sa.String(64),
            nullable=False,
            comment="Canonical内容SHA-256",
        ),
        sa.Column("source_mode", sa.String(16), nullable=False),
        sa.Column("skill_snapshot", sa.JSON(), nullable=False),
        sa.Column("model_snapshot", sa.JSON(), nullable=False),
        sa.Column("template_snapshot", sa.JSON(), nullable=True),
        sa.Column("provenance_summary", sa.JSON(), nullable=False),
        sa.Column("preflight_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "high_risk_confirmation_required",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("high_risk_confirmed_at", _utc_datetime(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("bridge_brief_id", _uuid(), nullable=True),
        sa.Column("generation_task_id", _uuid(), nullable=True),
        sa.Column("confirmed_at", _utc_datetime(), nullable=True),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bridge_brief_id"],
            ["briefs.id"],
            name="fk_deck_revisions_bridge_brief",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["deck_drafts.id"],
            name="fk_deck_revisions_draft",
        ),
        sa.ForeignKeyConstraint(
            ["generation_task_id"],
            ["generation_tasks.id"],
            name="fk_deck_revisions_generation_task",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id",
            "revision",
            name="uq_deck_draft_revisions_draft_revision",
        ),
        comment="Deck Brief不可变Revision",
    )
    op.create_index(
        "ix_deck_draft_revisions_draft_id",
        revisions.name,
        ["draft_id"],
    )
    op.create_index(
        "ix_deck_draft_revisions_bridge_brief_id",
        revisions.name,
        ["bridge_brief_id"],
    )
    op.create_index(
        "ix_deck_draft_revisions_generation_task_id",
        revisions.name,
        ["generation_task_id"],
    )

    inputs = op.create_table(
        "deck_draft_inputs",
        sa.Column("id", _uuid(), nullable=False, comment="Deck Input ID"),
        sa.Column(
            "revision_id",
            _uuid(),
            nullable=False,
            comment="所属Deck Revision ID",
        ),
        sa.Column("input_kind", sa.String(32), nullable=False),
        sa.Column("source_asset_id", _uuid(), nullable=True),
        sa.Column("source_message_id", _uuid(), nullable=True),
        sa.Column("source_version", sa.String(80), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("provenance_kind", sa.String(32), nullable=False),
        sa.Column("created_at", _utc_datetime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["deck_draft_revisions.id"],
            name="fk_deck_inputs_revision",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["file_assets.id"],
            name="fk_deck_inputs_asset",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["chat_messages.id"],
            name="fk_deck_inputs_message",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "revision_id",
            "input_kind",
            "source_asset_id",
            "source_message_id",
            name="uq_deck_draft_inputs_revision_source",
        ),
        comment="Deck Revision冻结来源",
    )
    op.create_index(
        "ix_deck_draft_inputs_revision_id",
        inputs.name,
        ["revision_id"],
    )
    op.create_index(
        "ix_deck_draft_inputs_source_asset_id",
        inputs.name,
        ["source_asset_id"],
    )
    op.create_index(
        "ix_deck_draft_inputs_source_message_id",
        inputs.name,
        ["source_message_id"],
    )

    skill = _knowledge_skill()
    op.execute(
        sa.table(
            "skills",
            sa.column("id", _uuid()),
            sa.column("skill_code", sa.String()),
            sa.column("version", sa.String()),
            sa.column("kind", sa.String()),
            sa.column("display_name", sa.String()),
            sa.column("description", sa.Text()),
            sa.column("output_kind", sa.String()),
            sa.column("input_schema", sa.JSON()),
            sa.column("output_schema", sa.JSON()),
            sa.column("workflow", sa.JSON()),
            sa.column("capability_requirements", sa.JSON()),
            sa.column("status", sa.String()),
            sa.column("checksum", sa.String()),
            sa.column("created_at", _utc_datetime()),
        )
        .insert()
        .values(
            id=_uuid_literal("019fad00-0000-7000-8000-000000000201"),
            skill_code=skill["skill_code"],
            version=skill["version"],
            kind=skill["kind"],
            display_name=skill["display_name"],
            description=skill["description"],
            output_kind=skill["output_kind"],
            input_schema=op.inline_literal(
                json.dumps(
                    skill["input_schema"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            output_schema=op.inline_literal(
                json.dumps(
                    skill["output_schema"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            workflow=op.inline_literal(
                json.dumps(
                    skill["workflow"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            capability_requirements=op.inline_literal(
                json.dumps(
                    skill["capability_requirements"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            status=skill["status"],
            checksum=_checksum(skill),
            created_at=datetime(2026, 7, 29, 15, 0, 0),
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM skills "
            "WHERE skill_code = 'ppt.knowledge-education.v1' AND version = '1.0.0'"
        )
    )
    op.drop_index(
        "ix_deck_draft_inputs_source_message_id",
        table_name="deck_draft_inputs",
    )
    op.drop_index(
        "ix_deck_draft_inputs_source_asset_id",
        table_name="deck_draft_inputs",
    )
    op.drop_index(
        "ix_deck_draft_inputs_revision_id",
        table_name="deck_draft_inputs",
    )
    op.drop_table("deck_draft_inputs")
    op.drop_index(
        "ix_deck_draft_revisions_generation_task_id",
        table_name="deck_draft_revisions",
    )
    op.drop_index(
        "ix_deck_draft_revisions_bridge_brief_id",
        table_name="deck_draft_revisions",
    )
    op.drop_index(
        "ix_deck_draft_revisions_draft_id",
        table_name="deck_draft_revisions",
    )
    op.drop_table("deck_draft_revisions")
    op.drop_index("ix_deck_drafts_status", table_name="deck_drafts")
    op.drop_index("ix_deck_drafts_draft_group_id", table_name="deck_drafts")
    op.drop_index("ix_deck_drafts_source_message_id", table_name="deck_drafts")
    op.drop_index("ix_deck_drafts_thread_id", table_name="deck_drafts")
    op.drop_index("ix_deck_drafts_project_id", table_name="deck_drafts")
    op.drop_index("ix_deck_drafts_user_id", table_name="deck_drafts")
    op.drop_table("deck_drafts")
