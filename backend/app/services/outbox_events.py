from app.models.base import utc_now
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent


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
