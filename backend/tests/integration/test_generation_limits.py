from sqlalchemy import select

from app.models.generation_tasks import GenerationTask
from app.services.credential_limits import CredentialUsageLimiter
from app.services.generation_worker import (
    ControlledStepExecutor,
    GenerationWorkerService,
    StepExecutionResult,
)
from tests.generation.conftest import BRIEF_ID, USER_ID


class DeterministicBudgetStore:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    async def reserve(self, **values) -> bool:
        self.calls.append(values)
        return self.decisions.pop(0)


async def test_credential_rpm_tpm_budget_is_atomic_and_deterministic() -> None:
    store = DeterministicBudgetStore([True, False])
    limiter = CredentialUsageLimiter(store)

    assert await limiter.acquire(
        credential_id="credential",
        rpm_limit=2,
        tpm_limit=100,
        max_concurrency=2,
        active_count=1,
        requested_tokens=60,
        requested_requests=2,
    )
    assert not await limiter.acquire(
        credential_id="credential",
        rpm_limit=2,
        tpm_limit=100,
        max_concurrency=2,
        active_count=1,
        requested_tokens=60,
        requested_requests=2,
    )
    assert store.calls[0]["requested_tokens"] == 60
    assert store.calls[0]["requested_requests"] == 2


async def test_user_cannot_claim_more_than_two_running_tasks(
    generation_harness,
) -> None:
    created = []
    for index in range(3):
        created.append(
            await generation_harness.service.create(
                "access-token", BRIEF_ID, f"concurrency-{index}"
            )
        )
    async with generation_harness.session_factory() as session, session.begin():
        for item in created[:2]:
            task = await session.get(GenerationTask, item.task_id, with_for_update=True)
            task.status = "running"

    worker = GenerationWorkerService(
        generation_harness.session_factory,
        CredentialUsageLimiter(DeterministicBudgetStore([True])),
    )
    executor = ControlledStepExecutor([StepExecutionResult.succeeded()])
    deferred = await worker.process(created[2].task_id, executor)

    async with generation_harness.session_factory() as session:
        running = list(
            await session.scalars(
                select(GenerationTask).where(
                    GenerationTask.user_id == USER_ID,
                    GenerationTask.status == "running",
                )
            )
        )
    assert deferred.status == "queued"
    assert executor.calls == []
    assert len(running) == 2
