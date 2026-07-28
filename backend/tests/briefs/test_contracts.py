import pytest
from pydantic import ValidationError

from app.services.briefs.contracts import (
    BRIEF_TOP_LEVEL_FIELDS,
    StructuredBrief,
)
from tests.briefs.helpers import valid_brief_payload


def test_structured_brief_has_exactly_the_seventeen_approved_top_level_fields() -> None:
    brief = StructuredBrief.model_validate(valid_brief_payload())

    assert tuple(StructuredBrief.model_fields) == BRIEF_TOP_LEVEL_FIELDS
    assert set(brief.model_dump(mode="json")) == set(BRIEF_TOP_LEVEL_FIELDS)
    assert len(BRIEF_TOP_LEVEL_FIELDS) == 17


def test_structured_brief_rejects_unknown_top_level_fields() -> None:
    payload = valid_brief_payload()
    payload["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        StructuredBrief.model_validate(payload)


def test_structured_brief_requires_ai_inference_provenance_for_inferences() -> None:
    payload = valid_brief_payload()
    payload["inferences"][0]["source"] = "file"

    with pytest.raises(ValidationError):
        StructuredBrief.model_validate(payload)


def test_structured_brief_requires_evidence_for_file_facts_and_inferences() -> None:
    payload = valid_brief_payload()
    payload["facts"][0]["evidence_ids"] = []

    with pytest.raises(ValidationError):
        StructuredBrief.model_validate(payload)

    payload = valid_brief_payload()
    payload["inferences"][0]["evidence_ids"] = []

    with pytest.raises(ValidationError):
        StructuredBrief.model_validate(payload)


def test_structured_brief_requires_at_least_one_evidence_backed_fact() -> None:
    payload = valid_brief_payload()
    payload["facts"] = []

    with pytest.raises(ValidationError):
        StructuredBrief.model_validate(payload)

    schema = StructuredBrief.model_json_schema()
    assert schema["properties"]["facts"]["minItems"] == 1


def test_structured_brief_bounds_provider_authored_summary_items() -> None:
    schema = StructuredBrief.model_json_schema()

    assert schema["properties"]["facts"]["maxItems"] == 8
    assert schema["properties"]["inferences"]["maxItems"] == 4
    assert schema["properties"]["unresolved_items"]["maxItems"] == 4
    assert (
        schema["$defs"]["BriefContentItem"]["properties"]["evidence_ids"]["maxItems"]
        == 8
    )
    assert (
        schema["$defs"]["OutputDeliverable"]["properties"]["evidence_ids"]["maxItems"]
        == 8
    )
    assert (
        schema["$defs"]["BriefUnresolvedItem"]["properties"]["evidence_ids"]["maxItems"]
        == 8
    )
    assert (
        schema["$defs"]["BriefContentItem"]["properties"]["content"]["maxLength"] == 512
    )
    assert (
        schema["$defs"]["BriefUnresolvedItem"]["properties"]["content"]["maxLength"]
        == 512
    )
    assert (
        "never enumerate every evidence item"
        in schema["properties"]["facts"]["description"]
    )
    assert (
        "semantic ambiguities directly cited by the summary"
        in schema["properties"]["unresolved_items"]["description"]
    )
