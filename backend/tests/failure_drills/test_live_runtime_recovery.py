import os
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from sqlalchemy import func, select

from app.core.database import DatabaseManager
from app.core.redis import RedisManager
from app.models import (
    AiModel,
    AiProvider,
    Brief,
    CreditLedger,
    GenerationTask,
    GenerationTaskStep,
    OutboxEvent,
    Project,
    ProviderCredential,
    User,
)
from app.models.base import utc_now
from app.services.auth_sessions import CurrentUser
from app.services.credential_limits import (
    CredentialUsageLimiter,
    RedisCredentialBudgetStore,
)
from app.services.generation import GenerationService
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
    StepExecutionResult,
)
from app.services.outbox import OutboxDispatcher, TaskRecoveryService
from app.settings.config import Settings
from app.workers.generation.consumer import GenerationQueueConsumer


RUN_LIVE = os.getenv("OFFICE_AI_RUN_T4_FAILURE_DRILL") == "1"
RUN_ID_TEXT = os.getenv("OFFICE_AI_T4_FAILURE_DRILL_RUN_ID", "")
pytestmark = pytest.mark.skipif(
    not RUN_LIVE,
    reason="T4-004 live MySQL/Redis failure drill 未显式 opt-in",
)


def _run_id() -> UUID:
    try:
        return UUID(RUN_ID_TEXT)
    except ValueError as exception:
        pytest.fail("OFFICE_AI_T4_FAILURE_DRILL_RUN_ID 必须是 UUID")
        raise exception


def _id(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"office-ai:t4-004:{_run_id()}:{label}")


def _idempotency(label: str) -> str:
    return f"t4-004:{_run_id()}:{label}"


def _preflight(brief_id: UUID, brief_group_id: UUID, *, combined: bool) -> dict:
    outputs = [
        {
            "skill_code": "ppt.sales-business-review.v1",
            "kind": "pptx",
            "title": "T4-004 presentation drill",
            "template_code": "ppt.executive-blue.v1",
            "template_version": "1.0.0",
            "estimated_credits": 800,
        }
    ]
    if combined:
        outputs.append(
            {
                "skill_code": "excel.sales-analysis-dashboard.v1",
                "kind": "xlsx",
                "title": "T4-004 workbook drill",
                "template_code": "excel.analysis-dashboard.v1",
                "template_version": "1.0.0",
                "estimated_credits": 800,
            }
        )
    return {
        "brief_id": str(brief_id),
        "brief_group_id": str(brief_group_id),
        "revision": 1,
        "status": "queued",
        "conflicts": [],
        "outputs": outputs,
        "credit_multiplier": "1.0000",
        "estimated_credits": sum(item["estimated_credits"] for item in outputs),
        "has_blockers": False,
        "confirmed_at": datetime(2026, 7, 27, tzinfo=UTC).isoformat(),
    }


class _Sessions:
    async def authenticate_access(self, _access_token: str) -> CurrentUser:
        return CurrentUser(
            user_id=_id("user"),
            phone_country_code="+86",
            phone_number="19900000000",
            role="user",
            status="active",
            credit_balance=20_000,
            must_change_password=False,
        )


class _Publisher:
    def __init__(self, redis: RedisManager) -> None:
        self._redis = redis
        self.queue_key = f"office_ai:generation:drill:{_run_id()}"

    async def publish(self, event_id, event_type, payload) -> None:
        await self._redis.enqueue_generation(
            self.queue_key,
            {
                "event_id": str(event_id),
                "event_type": event_type,
                "payload": payload,
            },
        )


class _Queue:
    def __init__(self, redis: RedisManager, queue_key: str) -> None:
        self._redis = redis
        self._queue_key = queue_key

    async def dequeue(self):
        return await self._redis.dequeue_generation(
            self._queue_key,
            timeout_seconds=1,
        )


def _brief(*, combined: bool) -> Brief:
    suffix = "combined" if combined else "single"
    brief_id = _id(f"brief-{suffix}")
    group_id = _id(f"brief-group-{suffix}")
    selected_skills = [
        {
            "skill_code": "ppt.sales-business-review.v1",
            "version": "1.0.0",
        }
    ]
    template_versions = [
        {
            "template_code": "ppt.executive-blue.v1",
            "version": "1.0.0",
        }
    ]
    if combined:
        selected_skills.append(
            {
                "skill_code": "excel.sales-analysis-dashboard.v1",
                "version": "1.0.0",
            }
        )
        template_versions.append(
            {
                "template_code": "excel.analysis-dashboard.v1",
                "version": "1.0.0",
            }
        )
    return Brief(
        id=brief_id,
        brief_group_id=group_id,
        revision=1,
        user_id=_id("user"),
        project_id=_id("project"),
        selected_model_id=_id("model"),
        source_snapshot={
            "source_asset_versions": [
                {
                    "asset_id": str(_id("source-asset")),
                    "asset_version": f"sha256:{'a' * 64}",
                }
            ],
            "term_library_versions": [],
            "selected_skills": selected_skills,
            "selected_model": {
                "model_id": str(_id("model")),
                "provider_id": str(_id("provider")),
                "credential_id": str(_id("credential")),
                "model_code": "agnes-t4-004-drill",
            },
            "template_versions": template_versions,
        },
        content={},
        content_checksum=("b" if combined else "a") * 64,
        status="queued",
        preflight_snapshot=_preflight(brief_id, group_id, combined=combined),
        estimated_credits=1600 if combined else 800,
        confirmed_at=datetime(2026, 7, 27, 0, 0),
    )


async def _runtime():
    settings = Settings()
    if not settings.database_url.get_secret_value().startswith("mysql+aiomysql://"):
        pytest.fail("T4-004 live drill 必须使用真实 MySQL URL")
    database = DatabaseManager(settings.database_url)
    redis = RedisManager(settings.redis_url)
    return database, redis


async def _task_by_key(session_factory, label: str) -> GenerationTask:
    async with session_factory() as session:
        task = await session.scalar(
            select(GenerationTask).where(
                GenerationTask.user_id == _id("user"),
                GenerationTask.idempotency_key == _idempotency(label),
            )
        )
    assert task is not None
    return task


async def _ledger_types(session_factory, task_id: UUID) -> list[tuple[str, int]]:
    async with session_factory() as session:
        entries = list(
            await session.scalars(
                select(CreditLedger)
                .where(CreditLedger.task_id == task_id)
                .order_by(CreditLedger.created_at, CreditLedger.id)
            )
        )
    return [(entry.entry_type, entry.amount) for entry in entries]


async def test_01_setup_persistent_task_and_idempotent_reserve() -> None:
    database, redis = await _runtime()
    try:
        async with database.session_factory() as session, session.begin():
            assert await session.get(User, _id("user")) is None
            phone_suffix = str(_run_id().int % 100_000_000).zfill(8)
            session.add_all(
                [
                    User(
                        id=_id("user"),
                        phone_number=f"199{phone_suffix}",
                        password_hash="t4-004-drill-not-a-login",
                        credit_balance=20_000,
                    ),
                    AiProvider(
                        id=_id("provider"),
                        vendor="agnes",
                        display_name="Agnes T4-004 drill",
                        protocol="openai-compatible",
                        base_url="https://apihub.agnes-ai.com/v1",
                        status="active",
                        default_timeout_seconds=120,
                        config={},
                    ),
                ]
            )
            await session.flush()
            session.add_all(
                [
                    Project(
                        id=_id("project"),
                        user_id=_id("user"),
                        name="T4-004 isolated runtime drill",
                        is_default=False,
                    ),
                    ProviderCredential(
                        id=_id("credential"),
                        provider_id=_id("provider"),
                        name="T4-004 non-secret drill credential",
                        encrypted_key="not-a-real-credential",
                        key_fingerprint=_run_id().hex * 2,
                        status="active",
                        rpm_limit=1000,
                        tpm_limit=1_000_000,
                        max_concurrency=10,
                        rotation_source="failure_drill",
                    ),
                ]
            )
            await session.flush()
            session.add(
                AiModel(
                    id=_id("model"),
                    provider_id=_id("provider"),
                    credential_id=_id("credential"),
                    model_code="agnes-t4-004-drill",
                    display_name="Agnes T4-004 drill",
                    capabilities={"structured_output": True},
                    context_window=4096,
                    max_output_tokens=512,
                    user_visible=True,
                    is_recommended=True,
                    credit_multiplier="1.0000",
                    allowed_skills=[
                        "ppt.sales-business-review.v1",
                        "excel.sales-analysis-dashboard.v1",
                    ],
                    status="active",
                )
            )
            await session.flush()
            session.add_all(
                [
                    _brief(combined=False),
                    _brief(combined=True),
                ]
            )
        service = GenerationService(database.session_factory, _Sessions())
        first = await service.create(
            "drill-access",
            _id("brief-single"),
            _idempotency("redis-recovery"),
        )
        replay = await service.create(
            "drill-access",
            _id("brief-single"),
            _idempotency("redis-recovery"),
        )
        assert first.task_id == replay.task_id
        async with database.session_factory() as session:
            task_count = await session.scalar(
                select(func.count())
                .select_from(GenerationTask)
                .where(
                    GenerationTask.user_id == _id("user"),
                    GenerationTask.idempotency_key == _idempotency("redis-recovery"),
                )
            )
            outbox_count = await session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.aggregate_id == first.task_id)
            )
        assert task_count == 1
        assert outbox_count == 1
        assert await _ledger_types(database.session_factory, first.task_id) == [
            ("generation_reserve", -800)
        ]
    finally:
        await redis.close()
        await database.close()


async def test_02_redis_outage_keeps_mysql_outbox_pending() -> None:
    database, redis = await _runtime()
    try:
        task = await _task_by_key(database.session_factory, "redis-recovery")
        dispatcher = OutboxDispatcher(
            database.session_factory,
            _Publisher(redis),
            retry_base_seconds=1,
        )
        assert await dispatcher.dispatch_once() == 0
        async with database.session_factory() as session:
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == task.id)
            )
            persisted = await session.get(GenerationTask, task.id)
        assert event is not None
        assert event.status == "pending"
        assert event.retry_count == 1
        assert event.last_error_code == "queue_publish_failed"
        assert persisted is not None and persisted.status == "queued"
        assert await _ledger_types(database.session_factory, task.id) == [
            ("generation_reserve", -800)
        ]
    finally:
        await redis.close()
        await database.close()


async def test_03_outbox_recovers_and_restarted_worker_deduplicates() -> None:
    database, redis = await _runtime()
    try:
        await redis.ping()
        task = await _task_by_key(database.session_factory, "redis-recovery")
        async with database.session_factory() as session, session.begin():
            event = await session.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.aggregate_id == task.id)
                .with_for_update()
            )
            assert event is not None
            event.next_attempt_at = utc_now()
        publisher = _Publisher(redis)
        dispatcher = OutboxDispatcher(database.session_factory, publisher)
        assert await dispatcher.dispatch_once() == 1
        assert await dispatcher.dispatch_once() == 0

        limiter = CredentialUsageLimiter(RedisCredentialBudgetStore(redis))
        executor = ControlledStepExecutor([StepExecutionResult.succeeded()])
        consumer = GenerationQueueConsumer(
            _Queue(redis, publisher.queue_key),
            GenerationWorkerService(database.session_factory, limiter),
            executor,
        )
        completed = await consumer.consume_once()
        assert completed is not None and completed.status == "succeeded"
        assert len(executor.calls) == 1

        await publisher.publish(
            event.id,
            "generation.duplicate-drill",
            {"task_id": str(task.id)},
        )
        replay_executor = ControlledStepExecutor([])
        replay_consumer = GenerationQueueConsumer(
            _Queue(redis, publisher.queue_key),
            GenerationWorkerService(database.session_factory, limiter),
            replay_executor,
        )
        replay = await replay_consumer.consume_once()
        assert replay is not None and replay.status == "succeeded"
        assert replay_executor.calls == []
        assert await _ledger_types(database.session_factory, task.id) == [
            ("generation_reserve", -800),
            ("generation_finalize", 0),
        ]
    finally:
        await redis.close()
        await database.close()


async def test_04_real_mysql_terminal_and_recovery_contracts() -> None:
    database, redis = await _runtime()
    try:
        service = GenerationService(database.session_factory, _Sessions())
        limiter = CredentialUsageLimiter(RedisCredentialBudgetStore(redis))

        cancelled = await service.create(
            "drill-access",
            _id("brief-single"),
            _idempotency("cancel"),
        )
        cancelled = await service.cancel("drill-access", cancelled.task_id)
        assert cancelled.status == "cancelled"
        assert await _ledger_types(database.session_factory, cancelled.task_id) == [
            ("generation_reserve", -800),
            ("generation_release", 800),
        ]

        uncertain = await service.create(
            "drill-access",
            _id("brief-single"),
            _idempotency("provider-uncertain"),
        )
        uncertain = await GenerationWorkerService(
            database.session_factory, limiter
        ).process(
            uncertain.task_id,
            ControlledStepExecutor(
                [StepExecutionResult.provider_uncertain("provider_timeout")]
            ),
        )
        assert uncertain.status == "provider_uncertain"
        assert await _ledger_types(database.session_factory, uncertain.task_id) == [
            ("generation_reserve", -800)
        ]

        partial = await service.create(
            "drill-access",
            _id("brief-combined"),
            _idempotency("partial"),
        )
        partial_worker = GenerationWorkerService(database.session_factory, limiter)
        partial = await partial_worker.process(
            partial.task_id,
            ControlledStepExecutor(
                [
                    StepExecutionResult.succeeded(),
                    StepExecutionResult.permanent_failure("controlled_failure"),
                ]
            ),
        )
        replay = await partial_worker.process(
            partial.task_id,
            ControlledStepExecutor([]),
        )
        assert partial.status == replay.status == "partial_success"
        assert partial.settled_credits == 800
        assert await _ledger_types(database.session_factory, partial.task_id) == [
            ("generation_reserve", -1600),
            ("generation_finalize", 0),
            ("generation_release", 800),
        ]

        safe = await service.create(
            "drill-access",
            _id("brief-single"),
            _idempotency("stale-safe"),
        )
        unsafe = await service.create(
            "drill-access",
            _id("brief-single"),
            _idempotency("stale-provider"),
        )
        stale_at = utc_now() - timedelta(minutes=10)
        async with database.session_factory() as session, session.begin():
            for snapshot, provider_started in ((safe, False), (unsafe, True)):
                task = await session.get(
                    GenerationTask, snapshot.task_id, with_for_update=True
                )
                step = await session.scalar(
                    select(GenerationTaskStep)
                    .where(GenerationTaskStep.task_id == snapshot.task_id)
                    .with_for_update()
                )
                assert task is not None and step is not None
                task.status = "running"
                task.started_at = stale_at
                step.status = "running"
                step.started_at = stale_at
                step.checkpoint = {"provider_call_started": provider_started}
        recovery = await TaskRecoveryService(
            database.session_factory,
            stale_after=timedelta(minutes=5),
        ).recover()
        assert recovery.requeued_tasks == 1
        assert recovery.uncertain_tasks == 1
        async with database.session_factory() as session:
            safe_task = await session.get(GenerationTask, safe.task_id)
            unsafe_task = await session.get(GenerationTask, unsafe.task_id)
        assert safe_task is not None and safe_task.status == "queued"
        assert unsafe_task is not None
        assert unsafe_task.status == "provider_uncertain"
        assert await _ledger_types(database.session_factory, unsafe.task_id) == [
            ("generation_reserve", -800)
        ]
    finally:
        await redis.close()
        await database.close()
