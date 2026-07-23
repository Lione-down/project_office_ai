import asyncio
from contextlib import suppress
from datetime import timedelta

from sqlalchemy import select

from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent
from app.models.base import utc_now
from app.services.outbox import OutboxDispatcher, OutboxRuntime, TaskRecoveryService
from app.workers.generation.consumer import GenerationQueueConsumer
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
    StepExecutionResult,
)
from tests.generation.conftest import BRIEF_ID


class RecordingPublisher:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.fail_first = fail_first
        self.events = []

    async def publish(self, event_id, event_type, payload) -> None:
        self.events.append((event_id, event_type, payload))
        if self.fail_first and len(self.events) == 1:
            raise RuntimeError("redis unavailable")


class FakeQueue:
    def __init__(self, events):
        self.events = list(events)

    async def dequeue(self):
        if not self.events:
            return None
        return self.events.pop(0)


class AllowAllCredentialLimiter:
    async def acquire(self, **_kwargs) -> bool:
        return True


async def test_dispatcher_retries_publish_and_keeps_event_auditable(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "outbox-retry"
    )
    publisher = RecordingPublisher(fail_first=True)
    dispatcher = OutboxDispatcher(generation_harness.session_factory, publisher)

    assert await dispatcher.dispatch_once() == 0
    async with generation_harness.session_factory() as session, session.begin():
        event = await session.scalar(select(OutboxEvent))
        assert event.status == "pending"
        assert event.retry_count == 1
        event.next_attempt_at = utc_now()
    assert await dispatcher.dispatch_once() == 1

    async with generation_harness.session_factory() as session:
        event = await session.scalar(select(OutboxEvent))
    assert event.status == "published"
    assert event.aggregate_id == created.task_id
    assert len(publisher.events) == 2
    assert publisher.events[0][0] == publisher.events[1][0]


async def test_redis_loss_recovery_creates_new_deduplicated_event(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "redis-loss"
    )
    publisher = RecordingPublisher()
    dispatcher = OutboxDispatcher(generation_harness.session_factory, publisher)
    assert await dispatcher.dispatch_once() == 1
    async with generation_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, created.task_id, with_for_update=True)
        task.last_enqueued_at = utc_now() - timedelta(minutes=10)

    recovery = TaskRecoveryService(
        generation_harness.session_factory,
        stale_after=timedelta(minutes=5),
    )
    first = await recovery.recover()
    second = await recovery.recover()

    async with generation_harness.session_factory() as session:
        events = list(
            await session.scalars(select(OutboxEvent).order_by(OutboxEvent.created_at))
        )
    assert first.requeued_tasks == 1
    assert second.requeued_tasks == 0
    assert len(events) == 2
    assert events[1].event_type == "generation.recover"
    assert events[0].deduplication_key != events[1].deduplication_key


async def test_stale_provider_checkpoint_becomes_uncertain_without_release(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "stale-provider"
    )
    async with generation_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, created.task_id, with_for_update=True)
        task.status = "running"
        task.started_at = utc_now() - timedelta(minutes=10)
        step = await session.scalar(
            select(GenerationTaskStep).where(
                GenerationTaskStep.task_id == created.task_id
            )
        )
        step.status = "running"
        step.started_at = task.started_at
        step.checkpoint = {"provider_call_started": True}

    result = await TaskRecoveryService(
        generation_harness.session_factory,
        stale_after=timedelta(minutes=5),
    ).recover()

    async with generation_harness.session_factory() as session:
        task = await session.get(GenerationTask, created.task_id)
    assert result.uncertain_tasks == 1
    assert task.status == "provider_uncertain"


async def test_python_queue_consumer_deduplicates_repeated_delivery(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "queue-consumer"
    )
    message = {"payload": {"task_id": str(created.task_id)}}
    executor = ControlledStepExecutor([StepExecutionResult.succeeded()])
    consumer = GenerationQueueConsumer(
        FakeQueue([message, message]),
        GenerationWorkerService(
            generation_harness.session_factory, AllowAllCredentialLimiter()
        ),
        executor,
    )

    first = await consumer.consume_once()
    second = await consumer.consume_once()

    assert first.status == "succeeded"
    assert second.status == "succeeded"
    assert len(executor.calls) == 1


async def test_stale_safe_checkpoint_resets_step_before_requeue(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "stale-safe-checkpoint"
    )
    async with generation_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, created.task_id, with_for_update=True)
        task.status = "running"
        task.started_at = utc_now() - timedelta(minutes=10)
        step = await session.scalar(
            select(GenerationTaskStep).where(
                GenerationTaskStep.task_id == created.task_id
            )
        )
        step.status = "running"
        step.started_at = task.started_at
        step.checkpoint = {"provider_call_started": False, "local_stage": "prepare"}

    result = await TaskRecoveryService(
        generation_harness.session_factory,
        stale_after=timedelta(minutes=5),
    ).recover()

    async with generation_harness.session_factory() as session:
        task = await session.get(GenerationTask, created.task_id)
        step = await session.scalar(
            select(GenerationTaskStep).where(
                GenerationTaskStep.task_id == created.task_id
            )
        )
    assert result.requeued_tasks == 1
    assert task.status == "queued"
    assert step.status == "pending"
    assert step.checkpoint["recovered_from_stale_lease"] is True


async def test_outbox_runtime_runs_dispatch_and_recovery_loops() -> None:
    called = asyncio.Event()

    class Dispatcher:
        async def dispatch_once(self):
            return 0

    class Recovery:
        def __init__(self):
            self.calls = 0

        async def recover(self):
            self.calls += 1
            called.set()

    recovery = Recovery()
    task = asyncio.create_task(
        OutboxRuntime(
            Dispatcher(),
            recovery,
            poll_seconds=0.01,
            recovery_interval_seconds=60,
        ).run()
    )
    await asyncio.wait_for(called.wait(), timeout=1)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert recovery.calls == 1
