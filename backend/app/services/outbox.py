import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent
from app.models.base import utc_now
from app.services.outbox_events import build_generation_outbox_event


logger = logging.getLogger(__name__)


class OutboxDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        publisher,
        *,
        retry_base_seconds: int = 5,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._retry_base_seconds = retry_base_seconds

    async def dispatch_once(self) -> int:
        async with self._session_factory() as session, session.begin():
            event = await session.scalar(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == "pending",
                    OutboxEvent.next_attempt_at <= utc_now(),
                )
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if event is None:
                return 0
            event.lease_started_at = utc_now()
            try:
                await self._publisher.publish(
                    event.id, event.event_type, dict(event.payload)
                )
            except Exception:
                event.retry_count += 1
                event.next_attempt_at = utc_now() + timedelta(
                    seconds=min(
                        300,
                        self._retry_base_seconds * (2 ** (event.retry_count - 1)),
                    )
                )
                event.last_error_code = "queue_publish_failed"
                event.last_error_message = "队列投递失败"
                event.lease_started_at = None
                return 0
            event.status = "published"
            event.published_at = utc_now()
            event.lease_started_at = None
            event.last_error_code = None
            event.last_error_message = None
            return 1


@dataclass(frozen=True)
class RecoveryResult:
    requeued_tasks: int = 0
    uncertain_tasks: int = 0


class TaskRecoveryService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        stale_after: timedelta,
    ) -> None:
        self._session_factory = session_factory
        self._stale_after = stale_after

    async def recover(self) -> RecoveryResult:
        threshold = utc_now() - self._stale_after
        requeued = 0
        uncertain = 0
        async with self._session_factory() as session, session.begin():
            tasks = list(
                await session.scalars(
                    select(GenerationTask)
                    .where(
                        or_(
                            (
                                (GenerationTask.status == "queued")
                                & (GenerationTask.last_enqueued_at <= threshold)
                            ),
                            (
                                (GenerationTask.status == "running")
                                & (GenerationTask.started_at <= threshold)
                            ),
                        )
                    )
                    .order_by(GenerationTask.created_at, GenerationTask.id)
                    .with_for_update(skip_locked=True)
                )
            )
            for task in tasks:
                if task.status == "running":
                    running_steps = list(
                        await session.scalars(
                            select(GenerationTaskStep)
                            .where(
                                GenerationTaskStep.task_id == task.id,
                                GenerationTaskStep.status == "running",
                            )
                            .with_for_update()
                        )
                    )
                    if any(
                        bool((step.checkpoint or {}).get("provider_call_started"))
                        for step in running_steps
                    ):
                        task.status = "provider_uncertain"
                        task.error_category = "provider_result_unknown"
                        task.completed_at = utc_now()
                        for step in running_steps:
                            step.status = "provider_uncertain"
                            step.error_category = "provider_result_unknown"
                            step.completed_at = utc_now()
                        uncertain += 1
                        continue
                    for step in running_steps:
                        step.status = "pending"
                        step.started_at = None
                        step.completed_at = None
                        step.provider_request_id = None
                        step.checkpoint = {
                            **dict(step.checkpoint or {}),
                            "provider_call_started": False,
                            "recovered_from_stale_lease": True,
                        }
                    task.status = "queued"
                task.dispatch_sequence += 1
                task.last_enqueued_at = utc_now()
                session.add(build_generation_outbox_event(task, "generation.recover"))
                requeued += 1
        return RecoveryResult(requeued_tasks=requeued, uncertain_tasks=uncertain)


class RedisGenerationPublisher:
    queue_key = "office_ai:generation:queue"

    def __init__(self, redis) -> None:
        self._redis = redis

    async def publish(self, event_id, event_type, payload) -> None:
        await self._redis.enqueue_generation(
            self.queue_key,
            {
                "event_id": str(event_id),
                "event_type": event_type,
                "payload": payload,
            },
        )


class OutboxRuntime:
    def __init__(
        self,
        dispatcher: OutboxDispatcher,
        recovery: TaskRecoveryService,
        *,
        poll_seconds: float = 1.0,
        recovery_interval_seconds: int = 60,
    ) -> None:
        self._dispatcher = dispatcher
        self._recovery = recovery
        self._poll_seconds = poll_seconds
        self._recovery_interval_seconds = recovery_interval_seconds

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        next_recovery_at = loop.time()
        while True:
            try:
                published = await self._dispatcher.dispatch_once()
                if loop.time() >= next_recovery_at:
                    await self._recovery.recover()
                    next_recovery_at = loop.time() + self._recovery_interval_seconds
            except Exception as exception:
                logger.error(
                    "generation_outbox_poll_failed",
                    extra={"error_type": type(exception).__name__},
                )
                published = 0
            delay = 0 if published else self._poll_seconds
            if delay:
                await asyncio.sleep(delay)
