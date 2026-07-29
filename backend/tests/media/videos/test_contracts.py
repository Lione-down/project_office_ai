from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.media.videos.contracts import VideoJobCreateCommand


SLIDE_ID = UUID("019fad70-0000-7000-8000-000000000001")
MODEL_ID = UUID("019fad70-0000-7000-8000-000000000002")
JOB_ID = UUID("019fad70-0000-7000-8000-000000000003")


def command_payload() -> dict:
    return {
        "expected_revision": 1,
        "slide_id": str(SLIDE_ID),
        "action": "generate",
        "mode": "text-to-video",
        "prompt": "Synthetic geometric shapes moving over a neutral background",
        "negative_prompt": "logos, watermarks",
        "model_id": str(MODEL_ID),
        "width": 1152,
        "height": 768,
        "num_frames": 81,
        "frame_rate": 24,
        "confirmed": True,
        "accepted_estimated_credits": 0,
        "embed_requested": False,
    }


def test_video_job_requires_explicit_page_confirmation_and_text_only_mode() -> None:
    command = VideoJobCreateCommand.model_validate(command_payload())

    assert command.confirmed is True
    assert command.mode == "text-to-video"
    assert command.embed_requested is False
    assert command.slide_id == SLIDE_ID

    for invalid in (
        {"confirmed": False},
        {"mode": "image-to-video", "input_url": "https://example.com/input.png"},
        {"embed_requested": True},
        {"num_frames": 80},
        {"num_frames": 449},
        {"frame_rate": 61},
    ):
        with pytest.raises(ValidationError):
            VideoJobCreateCommand.model_validate({**command_payload(), **invalid})


def test_video_regeneration_requires_prior_job_and_never_overwrites_history() -> None:
    payload = {
        **command_payload(),
        "action": "regenerate",
        "supersedes_job_id": str(JOB_ID),
    }
    command = VideoJobCreateCommand.model_validate(payload)
    assert command.supersedes_job_id == JOB_ID

    with pytest.raises(ValidationError):
        VideoJobCreateCommand.model_validate(
            {**command_payload(), "action": "regenerate"}
        )
    with pytest.raises(ValidationError):
        VideoJobCreateCommand.model_validate(
            {**command_payload(), "supersedes_job_id": str(JOB_ID)}
        )
