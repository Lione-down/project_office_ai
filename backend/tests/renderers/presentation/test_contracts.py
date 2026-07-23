from pathlib import Path
import json

import pytest

from app.services.renderers.presentation.contracts import (
    PresentationContractError,
    PresentationPlan,
)


ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = ROOT / "ppt-renderer" / "src" / "presentation-plan.v1.schema.json"


def valid_plan() -> dict:
    return {
        "schema_version": "presentation-plan.v1",
        "renderer_version": "ppt-renderer.v1",
        "template": {"code": "ppt.executive-blue.v1", "version": "1.0.0"},
        "locale": "zh-CN",
        "metadata": {
            "title": "销售经营汇报",
            "subject": "synthetic contract",
            "author": "Office AI",
            "company": "Office AI",
            "revision": "1",
        },
        "evidence_ids": ["ev-1"],
        "images": {},
        "data_sources": {},
        "slides": [
            {
                "layout": "title",
                "title": "销售经营汇报",
                "speaker_notes": ["开场"],
                "elements": [],
            },
            {
                "layout": "content",
                "title": "核心结果",
                "speaker_notes": ["说明来源"],
                "elements": [
                    {
                        "type": "text",
                        "text": "销售额增长",
                        "evidence_ids": ["ev-1"],
                        "x": 1,
                        "y": 1.5,
                        "w": 5,
                        "h": 1,
                    }
                ],
            },
            {
                "layout": "closing",
                "title": "下一步",
                "speaker_notes": ["收尾"],
                "elements": [],
            },
        ],
    }


def test_python_contract_accepts_only_the_node_schema_version() -> None:
    plan = PresentationPlan.model_validate(valid_plan())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert SCHEMA_PATH.is_file()
    assert schema["$id"] == "presentation-plan.v1"
    assert schema["properties"]["renderer_version"]["const"] == "ppt-renderer.v1"
    assert set(schema["$defs"]["template"]["properties"]["code"]["enum"]) == {
        "ppt.executive-blue.v1",
        "ppt.operating-review.v1",
        "ppt.data-story.v1",
    }
    assert plan.schema_version == "presentation-plan.v1"
    assert plan.renderer_version == "ppt-renderer.v1"


def test_python_contract_rejects_free_text_unknown_versions_and_evidence() -> None:
    with pytest.raises(PresentationContractError):
        PresentationPlan.validate_for_renderer("create a deck")

    unknown = valid_plan()
    unknown["renderer_version"] = "ppt-renderer.v2"
    with pytest.raises(PresentationContractError):
        PresentationPlan.validate_for_renderer(unknown)

    missing_evidence = valid_plan()
    missing_evidence["slides"][1]["elements"][0]["evidence_ids"] = ["missing"]
    with pytest.raises(PresentationContractError):
        PresentationPlan.validate_for_renderer(missing_evidence)


def test_python_contract_rejects_non_deterministic_number_precision() -> None:
    plan = valid_plan()
    plan["slides"][1]["elements"][0]["x"] = 0.0000001

    with pytest.raises(PresentationContractError):
        PresentationPlan.validate_for_renderer(plan)
