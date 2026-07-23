import json

import pytest

from app.services.briefs.context import (
    BriefContextError,
    build_evidence_context,
)
from tests.briefs.helpers import inferred_evidence, source_evidence


def test_evidence_context_serializes_only_bounded_traceable_fields() -> None:
    context = build_evidence_context(
        (source_evidence(),),
        context_window=4096,
        max_output_tokens=512,
        fixed_prompt_reserve=256,
    )
    payload = json.loads(context.serialized)

    assert payload == [
        {
            "asset_id": str(source_evidence().asset_id),
            "asset_version": source_evidence().asset_version,
            "evidence_id": source_evidence().evidence_id,
            "evidence_type": "source_fact",
            "location": {
                "cell": "B2",
                "kind": "excel_cell",
                "sheet": "销售",
            },
            "normalized_value": "12000",
            "raw_value": "销售额为 12000 CNY",
            "unit": "CNY",
            "currency": "CNY",
        }
    ]
    assert context.evidence_ids == (source_evidence().evidence_id,)
    assert context.estimated_tokens <= context.available_tokens
    assert "local_path" not in context.serialized
    assert "parser_name" not in context.serialized


def test_evidence_context_rejects_required_evidence_over_budget() -> None:
    with pytest.raises(BriefContextError) as error:
        build_evidence_context(
            (source_evidence(raw_value="销售" * 500),),
            context_window=300,
            max_output_tokens=128,
            fixed_prompt_reserve=128,
        )

    assert error.value.error_code == "context_budget_exceeded"


def test_evidence_context_rejects_prior_ai_inference_as_source_context() -> None:
    with pytest.raises(BriefContextError) as error:
        build_evidence_context(
            (inferred_evidence(),),
            context_window=4096,
            max_output_tokens=512,
            fixed_prompt_reserve=256,
        )

    assert error.value.error_code == "evidence_type_invalid"
