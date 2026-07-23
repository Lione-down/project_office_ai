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
