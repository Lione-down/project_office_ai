import json

import pytest

from app.services.briefs.validation import (
    BriefValidationError,
    ExpectedBriefSnapshot,
    resolve_brief_evidence_references,
    validate_brief_response,
)
from tests.briefs.helpers import (
    ASSET_ID,
    ASSET_VERSION,
    CREDENTIAL_ID,
    EVIDENCE_ID,
    MODEL_ID,
    PROVIDER_ID,
    valid_brief_payload,
)


def expected_snapshot() -> ExpectedBriefSnapshot:
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
        evidence_ids=frozenset({EVIDENCE_ID}),
    )


def test_validated_brief_response_matches_all_authoritative_snapshots() -> None:
    brief = validate_brief_response(
        json.dumps(valid_brief_payload(), ensure_ascii=False),
        expected_snapshot(),
    )

    assert brief.module == "ppt"
    assert brief.facts[0].evidence_ids == (EVIDENCE_ID,)


def test_validated_brief_response_rejects_fabricated_evidence_id() -> None:
    payload = valid_brief_payload()
    payload["facts"][0]["evidence_ids"] = [f"e-{'f' * 64}"]

    with pytest.raises(BriefValidationError) as error:
        validate_brief_response(
            json.dumps(payload, ensure_ascii=False), expected_snapshot()
        )

    assert error.value.error_code == "brief_evidence_invalid"


def test_validated_brief_response_rejects_model_selected_snapshot_drift() -> None:
    payload = valid_brief_payload()
    payload["selected_model"]["model_code"] = "silent-fallback-model"

    with pytest.raises(BriefValidationError) as error:
        validate_brief_response(
            json.dumps(payload, ensure_ascii=False), expected_snapshot()
        )

    assert error.value.error_code == "brief_snapshot_mismatch"


def test_validated_brief_response_rejects_user_constraint_drift() -> None:
    payload = valid_brief_payload()
    payload["goal"] = "模型自行改写的目标"

    with pytest.raises(BriefValidationError) as error:
        validate_brief_response(
            json.dumps(payload, ensure_ascii=False), expected_snapshot()
        )

    assert error.value.error_code == "brief_snapshot_mismatch"


def test_validated_brief_response_rejects_output_kind_drift() -> None:
    payload = valid_brief_payload()
    payload["output_plan"]["deliverables"][0]["kind"] = "xlsx"

    with pytest.raises(BriefValidationError) as error:
        validate_brief_response(
            json.dumps(payload, ensure_ascii=False), expected_snapshot()
        )

    assert error.value.error_code == "brief_snapshot_mismatch"


def test_brief_evidence_references_resolve_to_immutable_ids() -> None:
    payload = valid_brief_payload()
    payload["facts"][0]["evidence_ids"] = ["r0"]
    payload["inferences"][0]["evidence_ids"] = ["r0"]

    resolved = resolve_brief_evidence_references(
        json.dumps(payload, ensure_ascii=False),
        {"r0": EVIDENCE_ID},
    )
    brief = validate_brief_response(resolved, expected_snapshot())

    assert brief.facts[0].evidence_ids == (EVIDENCE_ID,)
    assert brief.inferences[0].evidence_ids == (EVIDENCE_ID,)


def test_brief_evidence_references_reject_unknown_alias() -> None:
    payload = valid_brief_payload()
    payload["facts"][0]["evidence_ids"] = ["r-not-in-context"]

    with pytest.raises(BriefValidationError) as error:
        resolve_brief_evidence_references(
            json.dumps(payload, ensure_ascii=False),
            {"r0": EVIDENCE_ID},
        )

    assert error.value.error_code == "brief_evidence_invalid"


def test_brief_evidence_references_reject_unexposed_raw_id() -> None:
    payload = valid_brief_payload()

    with pytest.raises(BriefValidationError) as error:
        resolve_brief_evidence_references(
            json.dumps(payload, ensure_ascii=False),
            {"r0": EVIDENCE_ID},
        )

    assert error.value.error_code == "brief_evidence_invalid"
