from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


BRIEF_TOP_LEVEL_FIELDS = (
    "module",
    "goal",
    "audience",
    "language",
    "domain",
    "tone",
    "source_asset_versions",
    "term_library_versions",
    "selected_skills",
    "selected_model",
    "output_plan",
    "facts",
    "inferences",
    "unresolved_items",
    "must_include",
    "must_exclude",
    "citation_policy",
)
ContentSource = Literal[
    "user", "file", "calculation", "agnes_inference", "system_default"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class BriefGenerationCommand(StrictModel):
    project_id: UUID
    asset_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    term_library_versions: tuple["TermLibraryVersion", ...] = Field(max_length=20)
    skill_codes: tuple[str, ...] = Field(min_length=1, max_length=2)
    model_id: UUID
    goal: str = Field(min_length=1, max_length=2048)
    audience: str = Field(min_length=1, max_length=512)
    must_include: tuple[str, ...] = Field(max_length=100)
    must_exclude: tuple[str, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def command_references_are_unique(self):
        if (
            len(set(self.asset_ids)) != len(self.asset_ids)
            or len(set(self.skill_codes)) != len(self.skill_codes)
            or len(
                {(item.library_id, item.version) for item in self.term_library_versions}
            )
            != len(self.term_library_versions)
        ):
            raise ValueError("brief generation references must be unique")
        return self


class SourceAssetVersion(StrictModel):
    asset_id: UUID
    asset_version: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class TermLibraryVersion(StrictModel):
    library_id: UUID
    version: int = Field(ge=1)


class SelectedSkill(StrictModel):
    skill_code: str = Field(
        pattern=(
            r"^(ppt\.(sales-business-review|knowledge-education)"
            r"|excel\.sales-analysis-dashboard)\.v1$"
        )
    )
    version: Literal["1.0.0"]


class SelectedModel(StrictModel):
    model_id: UUID
    provider_id: UUID
    credential_id: UUID
    model_code: str = Field(min_length=1, max_length=128)


class BriefContentItem(StrictModel):
    content: str = Field(min_length=1, max_length=512)
    source: ContentSource
    evidence_ids: tuple[str, ...] = Field(
        max_length=8,
        description=(
            "Use the smallest representative evidence set needed to support this item."
        ),
    )


class BriefFact(BriefContentItem):
    source: Literal["user", "file", "calculation", "system_default"]

    @model_validator(mode="after")
    def source_facts_require_matching_evidence(self):
        if self.source in {"file", "calculation"} and not self.evidence_ids:
            raise ValueError("file and calculation facts require evidence")
        if self.source in {"user", "system_default"} and self.evidence_ids:
            raise ValueError("user and system defaults cannot claim file evidence")
        return self


class BriefInference(BriefContentItem):
    source: Literal["agnes_inference"]

    @model_validator(mode="after")
    def inference_requires_evidence(self):
        if not self.evidence_ids:
            raise ValueError("AI inference requires evidence")
        return self


class OutputDeliverable(StrictModel):
    kind: Literal["pptx", "xlsx"]
    title: str = Field(min_length=1, max_length=255)
    source: ContentSource
    evidence_ids: tuple[str, ...] = Field(max_length=8)


class OutputPlan(StrictModel):
    deliverables: tuple[OutputDeliverable, ...] = Field(min_length=1, max_length=2)


class BriefUnresolvedItem(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    content: str = Field(min_length=1, max_length=512)
    source: ContentSource
    evidence_ids: tuple[str, ...] = Field(max_length=8)
    blocking: bool


class CitationPolicy(StrictModel):
    internal_tracking: Literal[True]
    visible_citations: bool


class StructuredBrief(StrictModel):
    module: Literal["ppt", "excel", "combined"]
    goal: str = Field(min_length=1, max_length=2048)
    audience: str = Field(min_length=1, max_length=512)
    language: Literal["zh-CN"]
    domain: Literal["sales", "general"]
    tone: Literal["professional"]
    source_asset_versions: tuple[SourceAssetVersion, ...] = Field(max_length=20)
    term_library_versions: tuple[TermLibraryVersion, ...] = Field(max_length=20)
    selected_skills: tuple[SelectedSkill, ...] = Field(min_length=1, max_length=2)
    selected_model: SelectedModel
    output_plan: OutputPlan
    facts: tuple[BriefFact, ...] = Field(
        min_length=1,
        max_length=8,
        description=(
            "Concise summary only: select the strongest facts and never enumerate every "
            "evidence item or source blocker."
        ),
    )
    inferences: tuple[BriefInference, ...] = Field(
        max_length=4,
        description=(
            "Concise summary only: include only decision-relevant supported inferences."
        ),
    )
    unresolved_items: tuple[BriefUnresolvedItem, ...] = Field(
        max_length=4,
        description=(
            "List only semantic ambiguities directly cited by the summary. Never copy "
            "source numeric_unit_unknown or unit_unknown blockers; Preflight handles them."
        ),
    )
    must_include: tuple[BriefContentItem, ...] = Field(max_length=100)
    must_exclude: tuple[BriefContentItem, ...] = Field(max_length=100)
    citation_policy: CitationPolicy

    @model_validator(mode="after")
    def references_are_unique(self):
        asset_refs = [
            (item.asset_id, item.asset_version) for item in self.source_asset_versions
        ]
        term_refs = [
            (item.library_id, item.version) for item in self.term_library_versions
        ]
        skill_refs = [(item.skill_code, item.version) for item in self.selected_skills]
        if (
            len(set(asset_refs)) != len(asset_refs)
            or len(set(term_refs)) != len(term_refs)
            or len(set(skill_refs)) != len(skill_refs)
        ):
            raise ValueError("brief version references must be unique")
        return self


class BriefRevisionSnapshot(StrictModel):
    brief_id: UUID
    brief_group_id: UUID
    revision: int = Field(ge=1)
    status: Literal["draft"]
    content: StructuredBrief
    content_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
