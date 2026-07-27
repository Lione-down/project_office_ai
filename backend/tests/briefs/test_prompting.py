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
