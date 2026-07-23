from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TermLibraryCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    project_id: UUID | None = None


class TermLibraryUpdateRequest(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)


class TermItemCreateRequest(StrictModel):
    canonical_term: str = Field(min_length=1, max_length=255)
    aliases: tuple[str, ...] = Field(default=(), max_length=100)
    unit: str | None = Field(default=None, max_length=32)
    definition: str | None = Field(default=None, max_length=2048)
    metric_scope: str | None = Field(default=None, max_length=1024)
    priority: int = Field(default=0, ge=-1000, le=1000)


class TermItemUpdateRequest(StrictModel):
    canonical_term: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: tuple[str, ...] | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=32)
    definition: str | None = Field(default=None, max_length=2048)
    metric_scope: str | None = Field(default=None, max_length=1024)
    priority: int | None = Field(default=None, ge=-1000, le=1000)


class TermItemResponse(StrictModel):
    item_id: UUID
    canonical_term: str
    aliases: tuple[str, ...]
    unit: str | None
    definition: str | None
    metric_scope: str | None
    priority: int


class TermLibraryResponse(StrictModel):
    library_id: UUID
    project_id: UUID | None
    name: str
    description: str | None
    status: str
    version: int
    created_at: datetime
    items: tuple[TermItemResponse, ...]
