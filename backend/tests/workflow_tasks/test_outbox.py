from datetime import timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.models.base import utc_now
from app.models.outbox_events import OutboxEvent
from app.models.workflow_tasks import WorkflowTask
from app.services.outbox import (
    RedisGenerationPublisher,
    WorkflowTaskRecoveryService,
)
from app.services.workflow_worker import WorkflowTaskWorkerService
from app.workers.workflow.consumer import (
    RedisWorkflowQueue,
    WorkflowQueueConsumer,
)
from tests.workflow_tasks.test_service import command
from tests.workflow_tasks.test_worker import (
    BRIEF_GROUP_ID,
    ControlledBriefGenerator,
)


class RedisRecorder:
    def __init__(self, messages=()) -> None:
        self.enqueued = []
        self.messages = list(messages)

    async def enqueue_generation(self, queue_key, payload):
        self.enqueued.append((queue_key, payload))

    async def dequeue_generation(self, queue_key, timeout_seconds):
        assert queue_key == "office_ai:workflow:queue"
        assert timeout_seconds == 2
        return self.messages.pop(0) if self.messages else None


async def test_outbox_publisher_routes_brief_and_file_generation_separately() -> None:
    redis = RedisRecorder()
    publisher = RedisGenerationPublisher(redis)

    await publisher.publish("event-1", "brief.generate", {"workflow_task_id": "one"})
    await publisher.publish("event-2", "generation.queued", {"task_id": "two"})

    assert [item[0] for item in redis.enqueued] == [
        "office_ai:workflow:queue",
        "office_ai:generation:queue",
    ]


async def test_workflow_queue_consumer_is_safe_under_repeated_delivery(
    workflow_harness,
) -> None:
    created = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-consumer-001",
    )
    message = {
        "event_type": "brief.generate",
        "payload": {"workflow_task_id": str(created.task_id)},
    }
    redis = RedisRecorder([message, message])
    generator = ControlledBriefGenerator(
        [SimpleNamespace(brief_group_id=BRIEF_GROUP_ID)]
    )
    consumer = WorkflowQueueConsumer(
        RedisWorkflowQueue(redis),
        WorkflowTaskWorkerService(
            workflow_harness.session_factory,
            generator,
        ),
    )

    first = await consumer.consume_once()
    second = await consumer.consume_once()

    assert first.status == "awaiting_confirmation"
    assert second.status == "awaiting_confirmation"
    assert len(generator.calls) == 1


async def test_stale_workflow_recovery_requeues_safe_work_and_marks_running_uncertain(
    workflow_harness,
) -> None:
    queued = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-recovery-queued",
    )
    running = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-recovery-running",
    )
    stale_at = utc_now() - timedelta(minutes=60)
    async with workflow_harness.session_factory() as session, session.begin():
        queued_task = await session.get(WorkflowTask, queued.task_id)
        queued_task.last_enqueued_at = stale_at
        running_task = await session.get(WorkflowTask, running.task_id)
        running_task.stage = "brief_generating"
        running_task.status = "running"
        running_task.started_at = stale_at

    result = await WorkflowTaskRecoveryService(
        workflow_harness.session_factory,
        stale_after=timedelta(minutes=30),
    ).recover()

    async with workflow_harness.session_factory() as session:
        queued_task = await session.get(WorkflowTask, queued.task_id)
        running_task = await session.get(WorkflowTask, running.task_id)
        events = list(
            await session.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.aggregate_id == queued.task_id,
                )
            )
        )
    assert result.requeued_tasks == 1
    assert result.uncertain_tasks == 1
    assert queued_task.dispatch_sequence == 2
    assert len(events) == 2
    assert running_task.status == "provider_uncertain"
    assert running_task.failure_code == "provider_result_unknown"
    assert running_task.failure_reason == "Provider 结果未知，未自动重试"
