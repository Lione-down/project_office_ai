from datetime import datetime
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


VideoAction = Literal["generate", "replace", "regenerate"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class VideoJobCreateCommand(StrictModel):
    expected_revision: int = Field(ge=1)
    slide_id: UUID
    action: VideoAction
    mode: Literal["text-to-video"] = "text-to-video"
    prompt: str = Field(min_length=1, max_length=2000)
    negative_prompt: str | None = Field(default=None, max_length=1000)
    model_id: UUID
    width: int = Field(default=1152, ge=320, le=1920)
    height: int = Field(default=768, ge=240, le=1080)
    num_frames: int = Field(default=121, ge=1, le=441)
    frame_rate: int = Field(default=24, ge=1, le=60)
    confirmed: Literal[True]
    accepted_estimated_credits: int = Field(ge=0)
    embed_requested: Literal[False] = False
    supersedes_job_id: UUID | None = None

    @model_validator(mode="after")
    def validate_video_relationships(self):
        if (self.num_frames - 1) % 8:
            raise ValueError("num_frames must follow the 8n + 1 rule")
        if self.action == "generate" and self.supersedes_job_id is not None:
            raise ValueError("initial generation cannot supersede a job")
        if self.action != "generate" and self.supersedes_job_id is None:
            raise ValueError("replace/regenerate requires the prior job")
        return self


class VideoAssetSummary(StrictModel):
    asset_id: UUID
    version: int
    mime_type: Literal["video/mp4"]
    byte_size: int
    sha256: str
    width: int
    height: int
    duration_seconds: float
    container: Literal["mp4"]
    codec: Literal["h264"]
    download_path: str
    preview_path: str


class PosterAssetSummary(StrictModel):
    asset_id: UUID
    version: int
    mime_type: Literal["image/png"]
    byte_size: int
    sha256: str
    width: int
    height: int
    preview_path: str


class VideoJobSnapshot(StrictModel):
    kind: Literal["video"] = "video"
    media_job_id: UUID
    workflow_task_id: UUID
    draft_revision_id: UUID
    slide_id: UUID
    action: VideoAction
    mode: Literal["text-to-video"]
    status: str
    progress: int = Field(ge=0, le=100)
    provider_job_id: str | None
    model_snapshot: dict
    capability_snapshot: dict
    pricing_snapshot: dict
    prompt_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    requested_width: int
    requested_height: int
    requested_num_frames: int
    requested_frame_rate: int
    actual_width: int | None
    actual_height: int | None
    actual_duration_seconds: float | None
    output_video: VideoAssetSummary | None
    poster: PosterAssetSummary | None
    embedding_enabled: Literal[False] = False
    fallback_mode: Literal["poster_and_attachment"] = "poster_and_attachment"
    error_code: str | None
    error_message: str | None
    next_poll_after_seconds: int | None
    created_at: datetime
    updated_at: datetime
    replayed: bool = False


def video_request_fingerprint(
    draft_id: UUID,
    command: VideoJobCreateCommand,
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
