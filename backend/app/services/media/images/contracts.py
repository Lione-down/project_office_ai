from hashlib import sha256
import json
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.decks.contracts import DeckBrief, DeckSlide


ImageAction = Literal["generate", "replace", "regenerate"]
ImageKind = Literal["none", "diagram", "chart", "illustration", "photo"]
ImageRatio = Literal["1:1", "3:4", "4:3", "16:9", "9:16", "2:3", "3:2", "21:9"]
ImageSize = Literal["1K", "2K", "3K", "4K"]
CropMode = Literal["contain", "cover"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class VisualDirection(StrictModel):
    schema_version: Literal["ppt.visual-director.v1"] = "ppt.visual-director.v1"
    slide_id: UUID
    kind: ImageKind
    prompt: str = Field(max_length=4000)
    requested_size: ImageSize = "2K"
    requested_ratio: ImageRatio = "16:9"
    crop_mode: CropMode = "cover"
    alt_text: str = Field(max_length=500)

    @model_validator(mode="after")
    def prompt_matches_kind(self):
        if self.kind == "none" and self.prompt:
            raise ValueError("none visual cannot include a prompt")
        if self.kind != "none" and not self.prompt.strip():
            raise ValueError("generated visual requires a prompt")
        return self


class VisualPlan(StrictModel):
    schema_version: Literal["ppt.visual-director.v1"] = "ppt.visual-director.v1"
    slides: tuple[VisualDirection, ...]


class ImageJobCreateCommand(StrictModel):
    expected_revision: int = Field(ge=1)
    slide_id: UUID
    action: ImageAction
    prompt: str = Field(min_length=1, max_length=4000)
    alt_text: str = Field(min_length=1, max_length=500)
    model_id: UUID
    requested_size: ImageSize = "2K"
    requested_ratio: ImageRatio = "16:9"
    crop_mode: CropMode = "cover"
    confirmed: Literal[True]
    accepted_estimated_credits: int = Field(ge=0)
    supersedes_job_id: UUID | None = None
    input_asset_id: UUID | None = None
    input_asset_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def relationships_match_action(self):
        if self.action == "generate" and self.supersedes_job_id is not None:
            raise ValueError("initial generation cannot supersede a job")
        if self.action != "generate" and self.supersedes_job_id is None:
            raise ValueError("replace/regenerate requires the prior job")
        if (self.input_asset_id is None) != (self.input_asset_version is None):
            raise ValueError("image input identity and version must be paired")
        return self


class ImageAssetSummary(StrictModel):
    asset_id: UUID
    version: int
    mime_type: str
    byte_size: int
    sha256: str
    width: int
    height: int


class ImageJobSnapshot(StrictModel):
    kind: Literal["image"] = "image"
    media_job_id: UUID
    workflow_task_id: UUID
    draft_revision_id: UUID
    slide_id: UUID
    action: ImageAction
    status: str
    progress: int = Field(ge=0, le=100)
    model_snapshot: dict
    capability_snapshot: dict
    pricing_snapshot: dict
    prompt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    requested_size: ImageSize
    requested_ratio: ImageRatio
    crop_mode: CropMode
    alt_text: str
    actual_width: int | None
    actual_height: int | None
    output_asset: ImageAssetSummary | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    replayed: bool = False


def image_request_fingerprint(
    draft_id: UUID,
    command: ImageJobCreateCommand,
) -> str:
    canonical = json.dumps(
        {
            "draft_id": str(draft_id),
            "command": command.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_media_idempotency_key(key: str) -> None:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", key) is None:
        raise ValueError("idempotency_key_invalid")


def plan_deck_visuals(deck: DeckBrief) -> VisualPlan:
    return VisualPlan(
        slides=tuple(
            _plan_slide(slide, index=index, slide_count=len(deck.slides), deck=deck)
            for index, slide in enumerate(deck.slides)
        )
    )


def _plan_slide(
    slide: DeckSlide,
    *,
    index: int,
    slide_count: int,
    deck: DeckBrief,
) -> VisualDirection:
    suggestion = slide.visual_suggestion.strip()
    combined = f"{slide.title} {slide.purpose} {suggestion}"
    if index == 0 or index == slide_count - 1 and not suggestion:
        kind: ImageKind = "none"
    elif re.search(r"图表|趋势|数据|指标|占比|对比", combined):
        kind = "chart"
    elif re.search(r"流程|架构|关系|路径|步骤", combined):
        kind = "diagram"
    elif re.search(r"照片|摄影|人物|场景|产品", combined):
        kind = "photo"
    else:
        kind = "illustration"
    if kind == "none":
        prompt = ""
    else:
        prompt = (
            f"为《{deck.topic}》演示文稿制作一张{kind}视觉素材。"
            f"页面主题：{slide.title}；页面目标：{slide.purpose}；"
            f"视觉要求：{suggestion or deck.style}。"
            "专业、克制、无 Logo、无水印、无虚构数字、适合 16:9 PPT 版面。"
        )[:4000]
    return VisualDirection(
        slide_id=slide.slide_id,
        kind=kind,
        prompt=prompt,
        alt_text=(f"{slide.title}的{kind}视觉素材" if kind != "none" else ""),
    )
