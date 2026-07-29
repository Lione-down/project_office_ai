from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.decks.contracts import (
    DeckBrief,
    DeckCreateCommand,
    deck_content_checksum,
)


PROJECT_ID = UUID("019fad00-0000-7000-8000-000000000001")
MODEL_ID = UUID("019fad00-0000-7000-8000-000000000002")
ASSET_ID = UUID("019fad00-0000-7000-8000-000000000003")


def valid_deck_payload() -> dict:
    return {
        "schema_version": "deck-brief.v1",
        "topic": "用通俗方式解释生成式 AI",
        "audience": "没有技术背景的业务团队",
        "language": "zh-CN",
        "style": "清晰、克制、适合培训",
        "source_mode": "inspiration",
        "skill_code": "ppt.knowledge-education.v1",
        "slides": [
            {
                "slide_id": "019fad00-0000-7000-8000-000000000101",
                "title": "生成式 AI 是什么",
                "purpose": "建立共同语言",
                "body": ["从模式中生成新内容", "输出需要人工核验"],
                "speaker_notes": "先解释能力边界。",
                "visual_suggestion": "概念关系图",
                "provenance": [
                    {
                        "kind": "agnes_inference",
                        "evidence_ids": [],
                    }
                ],
            },
            {
                "slide_id": "019fad00-0000-7000-8000-000000000102",
                "title": "适合与不适合的任务",
                "purpose": "建立使用边界",
                "body": ["适合辅助整理", "不应替代专业判断"],
                "speaker_notes": "给出正反例。",
                "visual_suggestion": "双栏对比",
                "provenance": [
                    {
                        "kind": "user_input",
                        "evidence_ids": [],
                    }
                ],
            },
            {
                "slide_id": "019fad00-0000-7000-8000-000000000103",
                "title": "下一步",
                "purpose": "形成行动建议",
                "body": ["从低风险场景开始", "建立复核流程"],
                "speaker_notes": "以行动清单结束。",
                "visual_suggestion": "三步路线图",
                "provenance": [
                    {
                        "kind": "agnes_inference",
                        "evidence_ids": [],
                    }
                ],
            },
        ],
    }


def test_deck_brief_is_strict_versioned_and_checksum_is_canonical() -> None:
    payload = valid_deck_payload()

    deck = DeckBrief.model_validate(payload)

    assert deck.schema_version == "deck-brief.v1"
    assert deck_content_checksum(deck) == deck_content_checksum(
        DeckBrief.model_validate(deepcopy(payload))
    )
    with pytest.raises(ValidationError):
        DeckBrief.model_validate({**payload, "unapproved_field": True})


def test_deck_brief_rejects_duplicate_slide_identity_and_more_than_40_slides() -> None:
    payload = valid_deck_payload()
    payload["slides"][1]["slide_id"] = payload["slides"][0]["slide_id"]
    with pytest.raises(ValidationError, match="slide identities must be unique"):
        DeckBrief.model_validate(payload)

    payload = valid_deck_payload()
    payload["slides"] = [
        {
            **deepcopy(payload["slides"][0]),
            "slide_id": f"019fad00-0000-7000-8000-{index:012d}",
        }
        for index in range(41)
    ]
    with pytest.raises(ValidationError):
        DeckBrief.model_validate(payload)


def test_deck_brief_keeps_file_evidence_separate_from_unverified_content() -> None:
    payload = valid_deck_payload()
    payload["source_mode"] = "mixed"
    payload["slides"][0]["provenance"] = [
        {
            "kind": "source_evidence",
            "evidence_ids": [f"e-{'a' * 64}"],
        },
        {"kind": "agnes_inference", "evidence_ids": []},
    ]
    deck = DeckBrief.model_validate(payload)

    assert [item.kind for item in deck.slides[0].provenance] == [
        "source_evidence",
        "agnes_inference",
    ]

    payload["slides"][0]["provenance"][0]["evidence_ids"] = []
    with pytest.raises(ValidationError, match="source evidence requires evidence IDs"):
        DeckBrief.model_validate(payload)


def test_deck_create_command_requires_explicit_skill_and_source_assets_by_mode() -> (
    None
):
    base = {
        "project_id": PROJECT_ID,
        "model_id": MODEL_ID,
        "topic": "季度经营复盘",
        "audience": "经营管理团队",
        "slide_count": 8,
        "language": "zh-CN",
        "style": "专业",
        "source_mode": "materials",
        "skill_code": "ppt.sales-business-review.v1",
        "asset_ids": [ASSET_ID],
    }
    command = DeckCreateCommand.model_validate(base)
    assert command.asset_ids == (ASSET_ID,)

    with pytest.raises(
        ValidationError, match="materials and mixed modes require assets"
    ):
        DeckCreateCommand.model_validate({**base, "asset_ids": []})
    with pytest.raises(
        ValidationError, match="inspiration mode does not accept assets"
    ):
        DeckCreateCommand.model_validate(
            {**base, "source_mode": "inspiration", "asset_ids": [ASSET_ID]}
        )
    with pytest.raises(ValidationError):
        DeckCreateCommand.model_validate({**base, "skill_code": "unknown.skill.v1"})
