from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.briefs.contracts import (
    BriefGenerationCommand,
    StructuredBrief,
    TermLibraryVersion,
)
from app.services.preflight.contracts import (
    BriefRevisionCommand,
    PreflightCommand,
)
from app.skills.catalog import SkillDefinition


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BriefGenerationRequest(StrictRequest):
    project_id: UUID
    asset_ids: tuple[UUID, ...] = Field(min_length=1, max_length=20)
    term_library_versions: tuple[TermLibraryVersion, ...] = Field(max_length=20)
    skill_codes: tuple[str, ...] = Field(min_length=1, max_length=2)
    model_id: UUID
    goal: str = Field(min_length=1, max_length=2048)
    audience: str = Field(min_length=1, max_length=512)
    must_include: tuple[str, ...] = Field(max_length=100)
    must_exclude: tuple[str, ...] = Field(max_length=100)

    def to_command(self) -> BriefGenerationCommand:
        return BriefGenerationCommand.model_validate(self.model_dump())


class BriefRevisionResponse(BaseModel):
    brief_id: UUID
    brief_group_id: UUID
    revision: int
    status: str
    content: StructuredBrief
    content_checksum: str


class BriefConfirmationRequest(StrictRequest):
    accepted_estimated_credits: int = Field(ge=0)


BriefRevisionRequest = BriefRevisionCommand
PreflightRequest = PreflightCommand


class SkillResponse(BaseModel):
    skill_code: str
    version: str
    kind: str
    display_name: str
    description: str
    output_kind: str
    input_schema: dict
    output_schema: dict
    workflow: dict
    capability_requirements: dict
    status: str

    @classmethod
    def from_definition(cls, skill: SkillDefinition) -> "SkillResponse":
        return cls(
            skill_code=skill.skill_code,
            version=skill.version,
            kind=skill.kind,
            display_name=skill.display_name,
            description=skill.description,
            output_kind=skill.output_kind,
            input_schema=skill.input_schema,
            output_schema=skill.output_schema,
            workflow=skill.workflow,
            capability_requirements=skill.capability_requirements,
            status=skill.status,
        )
