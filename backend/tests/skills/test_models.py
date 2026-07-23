from sqlalchemy import inspect

from app.models.briefs import Brief
from app.models.provider_calls import ProviderCall
from app.models.skills import Skill


def test_skill_model_has_versioned_immutable_contract_columns() -> None:
    columns = {column.name for column in inspect(Skill).columns}
    uniques = {
        constraint.name
        for constraint in Skill.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert {
        "id",
        "skill_code",
        "version",
        "kind",
        "display_name",
        "description",
        "output_kind",
        "input_schema",
        "output_schema",
        "workflow",
        "capability_requirements",
        "status",
        "checksum",
        "created_at",
    } == columns
    assert "uq_skills_code_version" in uniques


def test_brief_model_has_immutable_revision_and_owner_snapshot_columns() -> None:
    columns = {column.name for column in inspect(Brief).columns}
    uniques = {
        constraint.name
        for constraint in Brief.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert {
        "id",
        "brief_group_id",
        "revision",
        "user_id",
        "project_id",
        "selected_model_id",
        "source_snapshot",
        "content",
        "content_checksum",
        "preflight_snapshot",
        "estimated_credits",
        "status",
        "confirmed_at",
        "created_at",
    } == columns
    assert "uq_briefs_group_revision" in uniques


def test_provider_call_model_records_only_redacted_metadata() -> None:
    columns = {column.name for column in inspect(ProviderCall).columns}

    assert {
        "id",
        "brief_group_id",
        "brief_revision_id",
        "attempt",
        "provider_id",
        "model_id",
        "credential_id",
        "provider_request_id",
        "status",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
        "cost_amount",
        "error_category",
        "is_redacted",
        "created_at",
    } == columns
    assert (
        not {
            "api_key",
            "prompt",
            "request_body",
            "response_body",
            "file_content",
            "local_path",
        }
        & columns
    )
