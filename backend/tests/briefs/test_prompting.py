import json

from app.services.briefs.contracts import BriefGenerationCommand, StructuredBrief
from app.services.briefs.prompting import generation_messages, repair_messages
from app.services.briefs.validation import ExpectedBriefSnapshot
from tests.briefs.helpers import (
    ASSET_ID,
    ASSET_VERSION,
    CREDENTIAL_ID,
    MODEL_ID,
    PROJECT_ID,
    PROVIDER_ID,
)


def _command() -> BriefGenerationCommand:
    return BriefGenerationCommand(
        project_id=PROJECT_ID,
        asset_ids=(ASSET_ID,),
        term_library_versions=(),
        skill_codes=("ppt.sales-business-review.v1",),
        model_id=MODEL_ID,
        goal="形成月度销售经营复盘",
        audience="销售管理层",
        must_include=("销售额",),
        must_exclude=(),
    )


def _expected() -> ExpectedBriefSnapshot:
    return ExpectedBriefSnapshot(
        module="ppt",
        goal="形成月度销售经营复盘",
        audience="销售管理层",
        must_include=("销售额",),
        must_exclude=(),
        source_asset_versions=((ASSET_ID, ASSET_VERSION),),
        term_library_versions=(),
        selected_skills=(("ppt.sales-business-review.v1", "1.0.0"),),
        model_id=MODEL_ID,
        provider_id=PROVIDER_ID,
        credential_id=CREDENTIAL_ID,
        model_code="agnes-2.0-flash",
        evidence_ids=frozenset(),
    )


def test_generation_prompt_contains_complete_nested_structured_brief_schema() -> None:
    messages = generation_messages(_command(), _expected(), "{}", ())
    payload = json.loads(messages[1]["content"])

    schema = payload["structured_brief_schema"]
    assert set(schema["required"]) == set(StructuredBrief.model_fields)
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["OutputPlan"]["required"] == ["deliverables"]
    assert schema["$defs"]["OutputDeliverable"]["additionalProperties"] is False
    assert schema["$defs"]["BriefFact"]["required"] == [
        "content",
        "source",
        "evidence_ids",
    ]
    assert payload["output_constraints"] == {
        "facts": {"min_items": 1, "max_items": 8},
        "inferences": {"max_items": 4},
        "unresolved_items": {"max_items": 4},
        "max_content_characters_per_item": 512,
        "max_evidence_refs_per_item": 8,
        "max_serialized_characters": 16_000,
        "unit_blocker_policy": "handled_by_preflight",
    }
    assert (
        "Never enumerate evidence_context items or blockers" in messages[0]["content"]
    )


def test_repair_prompt_contains_only_bounded_validation_hints() -> None:
    messages = repair_messages(
        _command(),
        _expected(),
        "{}",
        (),
        '{"facts":[{"content":"private-value"}]}',
        (
            "facts.0.source:missing",
            "facts.0.evidence_ids:missing",
        ),
    )

    repair_payload = json.loads(messages[-1]["content"])
    assert repair_payload["validation_hints"] == [
        "facts.0.source:missing",
        "facts.0.evidence_ids:missing",
    ]
    assert "private-value" not in messages[-1]["content"]


def test_truncated_repair_regenerates_without_echoing_partial_response() -> None:
    private_partial_response = '{"facts":[{"content":"private-value"'
    messages = repair_messages(
        _command(),
        _expected(),
        "{}",
        (),
        private_partial_response,
        ("json:invalid",),
        was_truncated=True,
    )

    serialized = json.dumps(messages, ensure_ascii=False)
    repair_payload = json.loads(messages[-1]["content"])
    assert repair_payload["previous_response_status"] == "truncated"
    assert "regenerate it from scratch" in repair_payload["instruction"].lower()
    assert private_partial_response not in serialized
    assert "private-value" not in serialized
