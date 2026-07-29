from hashlib import sha256
import json
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.skills.catalog import KNOWLEDGE_EDUCATION_SKILL_CODE, PPT_SKILL_CODE


DeckSourceMode = Literal["inspiration", "materials", "mixed"]
DeckSkillCode = Literal[
    "ppt.sales-business-review.v1",
    "ppt.knowledge-education.v1",
]


class DeckOperationError(RuntimeError):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class DeckProvenance(StrictModel):
    kind: Literal["user_input", "agnes_inference", "source_evidence"]
    evidence_ids: tuple[str, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def evidence_matches_kind(self):
        if self.kind == "source_evidence" and not self.evidence_ids:
            raise ValueError("source evidence requires evidence IDs")
        if self.kind != "source_evidence" and self.evidence_ids:
            raise ValueError("unverified content cannot claim source evidence")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence IDs must be unique")
        return self


class DeckSlide(StrictModel):
    slide_id: UUID
    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=500)
    body: tuple[str, ...] = Field(min_length=1, max_length=12)
    speaker_notes: str = Field(default="", max_length=4000)
    visual_suggestion: str = Field(default="", max_length=1000)
    provenance: tuple[DeckProvenance, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def body_is_bounded(self):
        if any(not item.strip() or len(item) > 500 for item in self.body):
            raise ValueError("slide body items must be non-empty and bounded")
        return self


class DeckBrief(StrictModel):
    schema_version: Literal["deck-brief.v1"]
    topic: str = Field(min_length=1, max_length=500)
    audience: str = Field(min_length=1, max_length=500)
    language: Literal["zh-CN"]
    style: str = Field(min_length=1, max_length=500)
    source_mode: DeckSourceMode
    skill_code: DeckSkillCode
    slides: tuple[DeckSlide, ...] = Field(min_length=3, max_length=40)

    @model_validator(mode="after")
    def slide_identities_are_unique(self):
        slide_ids = [slide.slide_id for slide in self.slides]
        if len(set(slide_ids)) != len(slide_ids):
            raise ValueError("slide identities must be unique")
        has_evidence = any(
            provenance.kind == "source_evidence"
            for slide in self.slides
            for provenance in slide.provenance
        )
        if self.source_mode == "inspiration" and has_evidence:
            raise ValueError("inspiration mode cannot claim source evidence")
        return self


class DeckCreateCommand(StrictModel):
    project_id: UUID
    model_id: UUID
    topic: str = Field(min_length=1, max_length=500)
    audience: str = Field(min_length=1, max_length=500)
    slide_count: int = Field(ge=3, le=40)
    language: Literal["zh-CN"]
    style: str = Field(min_length=1, max_length=500)
    source_mode: DeckSourceMode
    skill_code: DeckSkillCode
    asset_ids: tuple[UUID, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def source_assets_match_mode(self):
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("asset IDs must be unique")
        if self.source_mode in {"materials", "mixed"} and not self.asset_ids:
            raise ValueError("materials and mixed modes require assets")
        if self.source_mode == "inspiration" and self.asset_ids:
            raise ValueError("inspiration mode does not accept assets")
        return self


class DeckUpdateCommand(StrictModel):
    expected_revision: int = Field(ge=1)
    content: DeckBrief


class DeckConfirmCommand(StrictModel):
    expected_revision: int = Field(ge=1)
    high_risk_confirmed: bool = False


class DeckGenerationCommand(StrictModel):
    expected_revision: int = Field(ge=1)
    accepted_estimated_credits: int = Field(ge=0)


class DeckDraftSnapshot(StrictModel):
    draft_id: UUID
    thread_id: UUID
    source_message_id: UUID
    revision_id: UUID
    revision: int
    status: str
    content: DeckBrief
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    preflight_snapshot: dict | None
    generation_task_id: UUID | None
    confirmed_at: datetime | None
    replayed: bool = False


def deck_content_checksum(deck: DeckBrief) -> str:
    canonical = json.dumps(
        deck.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def deck_request_fingerprint(message_id: UUID, command: DeckCreateCommand) -> str:
    canonical = json.dumps(
        {
            "message_id": str(message_id),
            "command": command.model_dump(mode="json"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def validate_deck_idempotency_key(key: str) -> None:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", key) is None:
        raise DeckOperationError(
            "idempotency_key_invalid",
            "Idempotency-Key 无效",
            422,
        )


DECK_SKILL_CODES = frozenset({PPT_SKILL_CODE, KNOWLEDGE_EDUCATION_SKILL_CODE})
