from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=128)


class ProjectUpdateRequest(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_archived: bool | None = None

    @field_validator("name", "is_archived", mode="before")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("字段不能为 null")
        return value


class ProjectResponse(StrictModel):
    project_id: UUID
    name: str
    is_default: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class AssetResponse(StrictModel):
    asset_id: UUID
    project_id: UUID
    original_filename: str
    file_category: str
    mime_type: str
    byte_size: int
    sha256: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
