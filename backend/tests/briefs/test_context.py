import json

import pytest

from app.services.evidence.contracts import EvidenceItem, ExcelCellLocation
from app.services.briefs.context import (
    BriefContextError,
    build_evidence_context,
)
from tests.briefs.helpers import (
    ASSET_ID,
    ASSET_VERSION,
    inferred_evidence,
    source_evidence,
)


def test_evidence_context_serializes_only_bounded_traceable_fields() -> None:
    context = build_evidence_context(
        (source_evidence(),),
        context_window=4096,
        max_output_tokens=512,
        fixed_prompt_reserve=256,
    )
    payload = json.loads(context.serialized)

    assert payload == {
        "schema_version": "brief-evidence-context.v2",
        "reference_policy": (
            "Use only evidence_ref values in Structured Brief evidence_ids."
        ),
        "assets": [
            {
                "asset_ref": "a0",
                "asset_id": str(source_evidence().asset_id),
                "asset_version": source_evidence().asset_version,
            }
        ],
        "groups": [
            {
                "asset_ref": "a0",
                "location_kind": "excel_cell",
                "evidence_type": "source_fact",
                "sheet": "销售",
                "item_fields": [
                    "evidence_ref",
                    "cell",
                    "raw_value",
                    "normalized_value",
                    "unit",
                    "currency",
                ],
                "items": [["r0", "B2", "销售额为 12000 CNY", "12000", "CNY", "CNY"]],
            }
        ],
    }
    assert context.evidence_ids == (source_evidence().evidence_id,)
    assert context.reference_map == (("r0", source_evidence().evidence_id),)
    assert context.estimated_tokens <= context.available_tokens
    assert source_evidence().evidence_id not in context.serialized
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


def test_evidence_context_compacts_complete_golden_scale_workbook() -> None:
    evidence = tuple(
        EvidenceItem(
            evidence_id=f"e-{index:064x}",
            evidence_type="source_fact",
            asset_id=ASSET_ID,
            asset_version=ASSET_VERSION,
            location=ExcelCellLocation(
                kind="excel_cell",
                sheet=f"Sheet{index % 31 + 1}",
                cell=f"A{index + 1}",
            ),
            raw_value=str(index),
            normalized_value=str(index),
            value_kind="number",
            unit=None,
            currency=None,
            parser_name="xlsx-safe",
            parser_version="1.0.0",
        )
        for index in range(10_465)
    )

    context = build_evidence_context(
        evidence,
        context_window=262_144,
        max_output_tokens=8_192,
        fixed_prompt_reserve=2_048,
    )
    payload = json.loads(context.serialized)

    assert len(context.evidence_ids) == 10_465
    assert len(context.reference_map) == 10_465
    assert context.estimated_tokens <= context.available_tokens
    assert payload["schema_version"] == "brief-evidence-context.v2"
    assert payload["assets"] == [
        {
            "asset_ref": "a0",
            "asset_id": str(ASSET_ID),
            "asset_version": ASSET_VERSION,
        }
    ]
    assert len(payload["groups"]) == 31
    assert evidence[0].evidence_id not in context.serialized
    assert context.reference_map[0] == ("r0", f"e-{0:064x}")
