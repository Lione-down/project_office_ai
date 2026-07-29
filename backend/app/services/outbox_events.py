from datetime import timedelta

from app.models.base import utc_now
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent
from app.models.workflow_tasks import WorkflowTask
from app.models.media_jobs import MediaJob


def build_generation_outbox_event(task: GenerationTask, event_type: str) -> OutboxEvent:
    return OutboxEvent(
        event_type=event_type,
        aggregate_type="generation_task",
        aggregate_id=task.id,
        deduplication_key=f"generation:{task.id}:dispatch:{task.dispatch_sequence}",
        payload={
            "task_id": str(task.id),
            "dispatch_sequence": task.dispatch_sequence,
        },
        status="pending",
        retry_count=0,
        next_attempt_at=utc_now(),
    )


def build_workflow_outbox_event(task: WorkflowTask) -> OutboxEvent:
    return OutboxEvent(
        event_type="brief.generate",
        aggregate_type="workflow_task",
        aggregate_id=task.id,
        deduplication_key=f"workflow:{task.id}:dispatch:{task.dispatch_sequence}",
        payload={
            "workflow_task_id": str(task.id),
            "dispatch_sequence": task.dispatch_sequence,
        },
        status="pending",
        retry_count=0,
        next_attempt_at=utc_now(),
    )


def build_image_outbox_event(job: MediaJob) -> OutboxEvent:
    return OutboxEvent(
        event_type="image.generate",
        aggregate_type="media_job",
        aggregate_id=job.id,
        deduplication_key=f"media:{job.id}:dispatch:1",
        payload={"media_job_id": str(job.id)},
        status="pending",
        retry_count=0,
        next_attempt_at=utc_now(),
    )


def build_video_outbox_event(
    job: MediaJob,
    *,
    event_type: str,
    dispatch_sequence: int,
    delay_seconds: int = 0,
) -> OutboxEvent:
    if event_type not in {"video.generate", "video.poll"}:
        raise ValueError("video outbox event type is invalid")
    return OutboxEvent(
        event_type=event_type,
        aggregate_type="media_job",
        aggregate_id=job.id,
        deduplication_key=f"media:{job.id}:video:{dispatch_sequence}",
        payload={"media_job_id": str(job.id)},
        status="pending",
        retry_count=0,
        next_attempt_at=utc_now() + timedelta(seconds=max(0, delay_seconds)),
    )
