from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.decks.contracts import DeckBrief
from app.services.media.images.contracts import (
    ImageJobCreateCommand,
    VisualDirection,
    plan_deck_visuals,
)


SLIDE_ID = UUID("019fad40-0000-7000-8000-000000000001")
MODEL_ID = UUID("019fad40-0000-7000-8000-000000000002")
JOB_ID = UUID("019fad40-0000-7000-8000-000000000003")


def deck() -> DeckBrief:
    return DeckBrief.model_validate(
        {
            "schema_version": "deck-brief.v1",
            "topic": "季度经营复盘",
            "audience": "管理层",
            "language": "zh-CN",
            "style": "专业",
            "source_mode": "inspiration",
            "skill_code": "ppt.sales-business-review.v1",
            "slides": [
                {
                    "slide_id": f"019fad40-0000-7000-8000-{index:012d}",
                    "title": title,
                    "purpose": "说明本页目标",
                    "body": ["展示季度趋势与关键行动"],
                    "speaker_notes": "",
                    "visual_suggestion": suggestion,
                    "provenance": [{"kind": "agnes_inference", "evidence_ids": []}],
                }
                for index, (title, suggestion) in enumerate(
                    (
                        ("封面", "保持留白"),
                        ("趋势分析", "使用数据图表"),
                        ("行动建议", "团队协作插画"),
                    ),
                    start=10,
                )
            ],
        }
    )


def test_visual_director_returns_bounded_structured_per_slide_plan() -> None:
    planned = plan_deck_visuals(deck())

    assert planned.schema_version == "ppt.visual-director.v1"
    assert [item.kind for item in planned.slides] == [
        "none",
        "chart",
        "illustration",
    ]
    assert all(
        isinstance(item, VisualDirection)
        and len(item.prompt) <= 4000
        and item.slide_id == planned.slides[index].slide_id
        for index, item in enumerate(planned.slides)
    )


def test_image_job_requires_explicit_confirmation_and_new_history_identity() -> None:
    command = ImageJobCreateCommand(
        expected_revision=1,
        slide_id=SLIDE_ID,
        action="regenerate",
        prompt="Synthetic illustration",
        alt_text="季度趋势抽象插画",
        model_id=MODEL_ID,
        requested_size="2K",
        requested_ratio="16:9",
        crop_mode="cover",
        confirmed=True,
        accepted_estimated_credits=0,
        supersedes_job_id=JOB_ID,
    )
    assert command.confirmed is True
    assert command.supersedes_job_id == JOB_ID

    with pytest.raises(ValidationError):
        command.model_copy(update={"supersedes_job_id": None}).__class__.model_validate(
            command.model_dump(exclude={"supersedes_job_id"})
        )
    with pytest.raises(ValidationError):
        ImageJobCreateCommand.model_validate(
            {
                **command.model_dump(mode="json"),
                "action": "generate",
                "supersedes_job_id": str(JOB_ID),
            }
        )
