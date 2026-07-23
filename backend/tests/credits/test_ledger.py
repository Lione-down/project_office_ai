from datetime import timedelta

from sqlalchemy import func, select

from app.models.credit_ledger import CreditLedger
from app.models.generation_tasks import GenerationTask
from app.models.outbox_events import OutboxEvent
from app.models.base import utc_now
from app.models.users import User
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
    StepExecutionResult,
)
from tests.generation.conftest import BRIEF_ID, USER_ID


class AllowAllCredentialLimiter:
    async def acquire(self, **_kwargs) -> bool:
        return True


async def run_task(generation_harness, outcomes):
    snapshot = await generation_harness.service.create(
        "access-token", BRIEF_ID, f"billing-{len(outcomes)}-{outcomes[0].status}"
    )
    worker = GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
        max_step_attempts=2,
    )
    processed = await worker.process(snapshot.task_id, ControlledStepExecutor(outcomes))
    return snapshot.task_id, processed


async def test_success_finalizes_reserve_without_second_charge(
    generation_harness,
) -> None:
    task_id, processed = await run_task(
        generation_harness, [StepExecutionResult.succeeded()]
    )
    duplicate = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(task_id, ControlledStepExecutor([StepExecutionResult.succeeded()]))

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        task = await session.get(GenerationTask, task_id)
        entries = list(
            await session.scalars(
                select(CreditLedger)
                .where(CreditLedger.task_id == task_id)
                .order_by(CreditLedger.created_at)
            )
        )

    assert processed.status == "succeeded"
    assert duplicate.status == "succeeded"
    assert user.credit_balance == 4_200
    assert task.settled_credits == 800
    assert [(entry.entry_type, entry.amount) for entry in entries] == [
        ("generation_reserve", -800),
        ("generation_finalize", 0),
    ]


async def test_failure_and_cancel_release_reserve(generation_harness) -> None:
    task_id, processed = await run_task(
        generation_harness,
        [StepExecutionResult.permanent_failure("provider_bad_request")],
    )
    cancelled = await generation_harness.service.create(
        "access-token", BRIEF_ID, "cancel-before-claim"
    )
    cancelled_snapshot = await generation_harness.service.cancel(
        "access-token", cancelled.task_id
    )

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        entries = list(await session.scalars(select(CreditLedger)))

    assert processed.status == "failed"
    assert cancelled_snapshot.status == "cancelled"
    assert user.credit_balance == 5_000
    assert sum(entry.amount for entry in entries) == 0
    assert sum(entry.entry_type == "generation_release" for entry in entries) == 2


async def test_partial_success_finalizes_success_and_releases_unused(
    generation_harness,
) -> None:
    await generation_harness.set_combined()
    task_id, processed = await run_task(
        generation_harness,
        [
            StepExecutionResult.succeeded(),
            StepExecutionResult.permanent_failure("render_failed"),
        ],
    )

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        task = await session.get(GenerationTask, task_id)
        entries = list(
            await session.scalars(
                select(CreditLedger).where(CreditLedger.task_id == task_id)
            )
        )

    assert processed.status == "partial_success"
    assert task.settled_credits == 800
    assert user.credit_balance == 4_200
    assert {(entry.entry_type, entry.amount) for entry in entries} == {
        ("generation_reserve", -1_600),
        ("generation_finalize", 0),
        ("generation_release", 800),
    }


async def test_provider_uncertain_keeps_reserve_and_never_auto_retries(
    generation_harness,
) -> None:
    task_id, processed = await run_task(
        generation_harness,
        [StepExecutionResult.provider_uncertain("provider_timeout")],
    )
    executor = ControlledStepExecutor([StepExecutionResult.succeeded()])
    duplicate = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(task_id, executor)

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
        entry_count = await session.scalar(
            select(func.count())
            .select_from(CreditLedger)
            .where(CreditLedger.task_id == task_id)
        )

    assert processed.status == "provider_uncertain"
    assert duplicate.status == "provider_uncertain"
    assert executor.calls == []
    assert user.credit_balance == 4_200
    assert entry_count == 1


async def test_retryable_failure_requeues_then_settles_without_new_reserve(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "retryable-provider"
    )
    worker = GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
        max_step_attempts=2,
    )
    retrying = await worker.process(
        created.task_id,
        ControlledStepExecutor(
            [StepExecutionResult.retryable_failure("provider_rate_limited")]
        ),
    )
    succeeded = await worker.process(
        created.task_id,
        ControlledStepExecutor([StepExecutionResult.succeeded()]),
    )

    async with generation_harness.session_factory() as session:
        entries = list(
            await session.scalars(
                select(CreditLedger).where(CreditLedger.task_id == created.task_id)
            )
        )
        events = list(
            await session.scalars(
                select(OutboxEvent).where(OutboxEvent.aggregate_id == created.task_id)
            )
        )
    assert retrying.status == "queued"
    assert succeeded.status == "succeeded"
    assert sum(entry.entry_type == "generation_reserve" for entry in entries) == 1
    assert len(events) == 2


async def test_expired_queued_task_fails_and_releases_before_execution(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "expired-before-claim"
    )
    async with generation_harness.session_factory() as session, session.begin():
        task = await session.get(GenerationTask, created.task_id, with_for_update=True)
        task.timeout_at = utc_now() - timedelta(seconds=1)
    executor = ControlledStepExecutor([StepExecutionResult.succeeded()])

    result = await GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    ).process(created.task_id, executor)

    async with generation_harness.session_factory() as session:
        user = await session.get(User, USER_ID)
    assert result.status == "failed"
    assert result.error_category == "task_timeout"
    assert executor.calls == []
    assert user.credit_balance == 5_000


async def test_retry_billing_key_stays_within_mysql_contract(
    generation_harness,
) -> None:
    created = await generation_harness.service.create(
        "access-token", BRIEF_ID, "a" * 128
    )
    worker = GenerationWorkerService(
        generation_harness.session_factory,
        AllowAllCredentialLimiter(),
    )
    await worker.process(
        created.task_id,
        ControlledStepExecutor(
            [StepExecutionResult.permanent_failure("deterministic_failure")]
        ),
    )
    await generation_harness.service.retry("access-token", created.task_id)

    async with generation_harness.session_factory() as session:
        keys = list(
            await session.scalars(
                select(CreditLedger.idempotency_key).where(
                    CreditLedger.task_id == created.task_id
                )
            )
        )
    assert max(map(len, keys)) <= 128
    assert len(set(keys)) == 2
