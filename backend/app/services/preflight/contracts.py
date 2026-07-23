from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.briefs.contracts import StructuredBrief


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TemplateVersion(StrictModel):
    template_code: str = Field(
        pattern=r"^(ppt|excel)\.[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*\.v1$"
    )
    version: Literal["1.0.0"]


class ConflictResolution(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    action: Literal["assign_unit", "confirm_numeric", "choose_source", "choose_scope"]
    value: str | None = Field(default=None, min_length=1, max_length=128)
    selected_evidence_id: str | None = Field(default=None, pattern=r"^e-[a-f0-9]{64}$")

    @model_validator(mode="after")
    def action_has_required_value(self):
        expected_actions = {
            "unit_unknown": "assign_unit",
            "numeric_low_confidence": "confirm_numeric",
            "source_conflict": "choose_source",
            "metric_scope_conflict": "choose_scope",
        }
        if expected_actions.get(self.code) != self.action:
            raise ValueError("resolution action does not match blocker type")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("resolution evidence IDs must be unique")
        if self.action == "choose_source":
            if (
                self.selected_evidence_id not in self.evidence_ids
                or self.value is not None
            ):
                raise ValueError("source resolution must choose known evidence")
        elif self.action in {"assign_unit", "choose_scope"}:
            if self.value is None or self.selected_evidence_id is not None:
                raise ValueError("unit and scope resolutions require a value")
        elif self.value is not None or self.selected_evidence_id is not None:
            raise ValueError("numeric confirmation cannot override evidence")
        return self


class OutputTitleUpdate(StrictModel):
    kind: Literal["pptx", "xlsx"]
    title: str = Field(min_length=1, max_length=255)


class BriefRevisionCommand(StrictModel):
    expected_revision: int = Field(ge=1)
    goal: str | None = Field(default=None, min_length=1, max_length=2048)
    audience: str | None = Field(default=None, min_length=1, max_length=512)
    must_include: tuple[str, ...] | None = Field(default=None, max_length=100)
    must_exclude: tuple[str, ...] | None = Field(default=None, max_length=100)
    output_titles: tuple[OutputTitleUpdate, ...] = Field(default=(), max_length=2)
    visible_citations: bool | None = None
    template_versions: tuple[TemplateVersion, ...] | None = Field(
        default=None, max_length=2
    )
    resolutions: tuple[ConflictResolution, ...] | None = Field(
        default=None, max_length=100
    )

    @model_validator(mode="after")
    def edited_references_are_unique(self):
        if len({item.kind for item in self.output_titles}) != len(self.output_titles):
            raise ValueError("output title kinds must be unique")
        if self.template_versions is not None and len(
            {(item.template_code, item.version) for item in self.template_versions}
        ) != len(self.template_versions):
            raise ValueError("template versions must be unique")
        if self.resolutions is not None and len(
            {(item.code, item.evidence_ids) for item in self.resolutions}
        ) != len(self.resolutions):
            raise ValueError("resolutions must be unique")
        return self


class PreflightCommand(StrictModel):
    brief_id: UUID
    one_click: bool = False
    accepted_estimated_credits: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def one_click_requires_credit_acceptance(self):
        if self.one_click and self.accepted_estimated_credits is None:
            raise ValueError("one-click preflight requires estimated credit acceptance")
        if not self.one_click and self.accepted_estimated_credits is not None:
            raise ValueError("credit acceptance is only valid in one-click mode")
        return self


class BriefSnapshot(StrictModel):
    brief_id: UUID
    brief_group_id: UUID
    revision: int
    status: Literal["draft", "preflight", "needs_resolution", "queued"]
    content: StructuredBrief
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_snapshot: dict
    estimated_credits: int | None
    confirmed_at: datetime | None


class ConflictFinding(StrictModel):
    code: str
    level: Literal["auto_merge", "needs_confirmation", "blocking", "incompatible"]
    message: str
    evidence_ids: tuple[str, ...] = ()


class PlannedOutputSnapshot(StrictModel):
    skill_code: str
    kind: Literal["pptx", "xlsx"]
    title: str
    template_code: str
    template_version: str
    estimated_credits: int


class PreflightSnapshot(StrictModel):
    brief_id: UUID
    brief_group_id: UUID
    revision: int
    status: Literal["preflight", "needs_resolution", "queued"]
    conflicts: tuple[ConflictFinding, ...]
    outputs: tuple[PlannedOutputSnapshot, ...]
    credit_multiplier: Decimal | None = Field(default=None, gt=0)
    estimated_credits: int
    has_blockers: bool
    confirmed_at: datetime | None = None
