from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.outbox import RedisGenerationPublisher
from app.settings.config import Settings
from app.workers.workflow.consumer import WorkflowQueueConsumer


class Queue:
    def __init__(self, message):
        self.message = message

    async def dequeue(self):
        return self.message


class Worker:
    def __init__(self):
        self.job_ids = []

    async def process(self, job_id):
        self.job_ids.append(job_id)
        return "processed"


class Redis:
    def __init__(self):
        self.calls = []

    async def enqueue_generation(self, queue_key, payload):
        self.calls.append((queue_key, payload))


@pytest.mark.parametrize("event_type", ["video.generate", "video.poll"])
async def test_workflow_consumer_routes_video_events_without_resubmitting_images(
    event_type: str,
) -> None:
    job_id = UUID("019fad70-0000-7000-8000-000000000011")
    image_worker = Worker()
    video_worker = Worker()
    consumer = WorkflowQueueConsumer(
        Queue(
            {
                "event_type": event_type,
                "payload": {"media_job_id": str(job_id)},
            }
        ),
        Worker(),
        image_worker,
        video_worker,
    )

    result = await consumer.consume_once()

    assert result == "processed"
    assert image_worker.job_ids == []
    assert video_worker.job_ids == [job_id]


async def test_outbox_publisher_routes_video_events_to_workflow_queue() -> None:
    redis = Redis()
    publisher = RedisGenerationPublisher(redis)

    await publisher.publish(
        "event-video-1",
        "video.poll",
        {"media_job_id": "video-job-1"},
    )

    assert redis.calls[0][0] == "office_ai:workflow:queue"


def test_video_settings_are_bounded_and_embedding_remains_fail_closed() -> None:
    settings = Settings()
    assert settings.video_max_prompt_chars == 2000
    assert settings.video_poll_interval_seconds == 5
    assert settings.video_job_timeout_seconds == 1800
    assert settings.video_max_duration_seconds == 20
    assert settings.video_embed_enabled is False
    assert settings.video_output_hosts == ("platform-outputs.agnes-ai.space",)

    with pytest.raises(ValidationError):
        Settings(OFFICE_AI_VIDEO_EMBED_ENABLED=True)


def test_compose_and_worker_image_include_video_runtime_contract() -> None:
    root = Path(__file__).parents[4]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "backend" / "Dockerfile").read_text(encoding="utf-8")

    for variable in (
        "OFFICE_AI_VIDEO_MAX_PROMPT_CHARS",
        "OFFICE_AI_VIDEO_POLL_INTERVAL_SECONDS",
        "OFFICE_AI_VIDEO_JOB_TIMEOUT_SECONDS",
        "OFFICE_AI_VIDEO_MAX_BYTES",
        "OFFICE_AI_VIDEO_MAX_DURATION_SECONDS",
        "OFFICE_AI_VIDEO_OUTPUT_HOST_ALLOWLIST",
        "OFFICE_AI_VIDEO_EMBED_ENABLED",
    ):
        assert variable in compose
    assert "ffmpeg" in dockerfile
