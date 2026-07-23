from dataclasses import dataclass
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.base import utc_now
from app.services.credit_transactions import (
    finalize_reserved_credits,
    release_reserved_credits,
)
from app.services.generation_contracts import (
    GenerationSnapshot,
    TERMINAL_TASK_STATUSES,
)
from app.services.generation_outputs import generation_step_snapshot
from app.services.outbox_events import build_generation_outbox_event


@dataclass(frozen=True)
class StepExecutionContext:
    task_id: UUID
    step_id: UUID
    step_key: str
    output_kind: str
    attempt: int
    model_snapshot: dict


@dataclass(frozen=True)
class StepExecutionResult:
    status: str
    error_category: str | None = None
    provider_request_id: str | None = None
    output_asset_id: UUID | None = None
    asset_version: str | None = None
    quality_status: str | None = None
    download_allowed: bool = False
    quality_report_schema_version: str | None = None

    def __post_init__(self) -> None:
        is_quality_success = self.quality_status in {
            "passed",
            "passed_with_warnings",
        }
        if (
            self.asset_version is not None
            and (
                self.output_asset_id is None
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.asset_version) is None
            )
            or self.download_allowed
            and (
                self.status != "succeeded"
                or not is_quality_success
                or self.output_asset_id is None
                or self.asset_version is None
                or self.quality_report_schema_version is None
            )
            or self.status == "succeeded"
            and self.quality_status == "blocked"
            or self.status != "succeeded"
            and is_quality_success
        ):
            raise ValueError("quality outcome is inconsistent")

    @classmethod
    def succeeded(
        cls,
        provider_request_id: str | None = None,
        *,
        output_asset_id: UUID | None = None,
        asset_version: str | None = None,
        quality_status: str | None = None,
        download_allowed: bool = False,
        quality_report_schema_version: str | None = None,
    ):
        return cls(
            "succeeded",
            provider_request_id=provider_request_id,
            output_asset_id=output_asset_id,
            asset_version=asset_version,
            quality_status=quality_status,
            download_allowed=download_allowed,
            quality_report_schema_version=quality_report_schema_version,
        )

    @classmethod
    def retryable_failure(cls, error_category: str):
        return cls("retryable_failure", error_category=error_category)

    @classmethod
    def permanent_failure(
        cls,
        error_category: str,
        *,
        output_asset_id: UUID | None = None,
        asset_version: str | None = None,
        quality_status: str | None = None,
        download_allowed: bool = False,
        quality_report_schema_version: str | None = None,
    ):
        return cls(
            "permanent_failure",
            error_category=error_category,
            output_asset_id=output_asset_id,
            asset_version=asset_version,
            quality_status=quality_status,
            download_allowed=download_allowed,
            quality_report_schema_version=quality_report_schema_version,
        )

    @classmethod
    def provider_uncertain(cls, error_category: str):
        return cls("provider_uncertain", error_category=error_category)


class ControlledStepExecutor:
    def __init__(self, outcomes: list[StepExecutionResult]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[StepExecutionContext] = []

    async def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        self.calls.append(context)
        if not self._outcomes:
            raise AssertionError("controlled executor has no remaining outcome")
        return self._outcomes.pop(0)


class GenerationWorkerService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        credential_limiter,
        *,
        max_step_attempts: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._credential_limiter = credential_limiter
        self._max_step_attempts = max_step_attempts

    async def process(self, task_id: UUID, executor) -> GenerationSnapshot:
        claimed = await self._claim(task_id)
        if claimed.status != "running":
            return claimed
        step_ids = await self._pending_step_ids(task_id)
        for step_id in step_ids:
            context = await self._begin_step(task_id, step_id)
            if context is None:
                break
            try:
                result = await executor.execute(context)
            except Exception:
                result = StepExecutionResult.retryable_failure(
                    "worker_execution_failed"
                )
            current = await self._complete_step(task_id, step_id, result)
            if current.status != "running":
                return current
        return await self._settle(task_id)

    async def _claim(self, task_id: UUID) -> GenerationSnapshot:
        async with self._session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id, with_for_update=True)
            if task is None:
                raise LookupError("generation task not found")
            if task.status != "queued":
                return await self._snapshot(session, task)
            if task.timeout_at <= utc_now():
                task.status = "failed"
                task.progress = 100
                task.error_category = "task_timeout"
                task.error_message = None
                task.completed_at = utc_now()
                for step in await self._steps(session, task.id, for_update=True):
                    if step.status == "pending":
                        step.status = "failed"
                        step.error_category = "task_timeout"
                        step.completed_at = task.completed_at
                await release_reserved_credits(session, task)
                return await self._snapshot(session, task)
            await session.get(User, task.user_id, with_for_update=True)
            running_for_user = await session.scalar(
                select(func.count())
                .select_from(GenerationTask)
                .where(
                    GenerationTask.user_id == task.user_id,
                    GenerationTask.status == "running",
                    GenerationTask.id != task.id,
                )
            )
            if running_for_user >= 2:
                return await self._snapshot(session, task)
            await session.get(
                ProviderCredential, task.credential_id, with_for_update=True
            )
            active_for_credential = await session.scalar(
                select(func.count())
                .select_from(GenerationTask)
                .where(
                    GenerationTask.credential_id == task.credential_id,
                    GenerationTask.status == "running",
                    GenerationTask.id != task.id,
                )
            )
            pending_steps = list(
                await session.scalars(
                    select(GenerationTaskStep).where(
                        GenerationTaskStep.task_id == task.id,
                        GenerationTaskStep.status == "pending",
                    )
                )
            )
            limits = task.model_snapshot
            allowed = await self._credential_limiter.acquire(
                credential_id=task.credential_id,
                rpm_limit=int(limits["rpm_limit"]),
                tpm_limit=int(limits["tpm_limit"]),
                max_concurrency=int(limits["max_concurrency"]),
                active_count=int(active_for_credential or 0),
                requested_tokens=sum(step.token_estimate for step in pending_steps),
                requested_requests=len(pending_steps),
            )
            if not allowed:
                return await self._snapshot(session, task)
            task.status = "running"
            task.error_category = None
            task.error_message = None
            task.started_at = task.started_at or utc_now()
            return await self._snapshot(session, task)

    async def _pending_step_ids(self, task_id: UUID) -> list[UUID]:
        async with self._session_factory() as session:
            return list(
                await session.scalars(
                    select(GenerationTaskStep.id)
                    .where(
                        GenerationTaskStep.task_id == task_id,
                        GenerationTaskStep.status == "pending",
                    )
                    .order_by(
                        GenerationTaskStep.created_at,
                        GenerationTaskStep.step_key,
                    )
                )
            )

    async def _begin_step(
        self, task_id: UUID, step_id: UUID
    ) -> StepExecutionContext | None:
        async with self._session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id, with_for_update=True)
            step = await session.get(GenerationTaskStep, step_id, with_for_update=True)
            if task.status != "running" or step.status != "pending":
                return None
            if task.cancel_requested_at is not None:
                await self._cancel_remaining(session, task)
                return None
            step.attempt += 1
            step.status = "running"
            step.started_at = utc_now()
            step.checkpoint = {
                **dict(step.checkpoint or {}),
                "provider_call_started": True,
                "attempt": step.attempt,
            }
            return StepExecutionContext(
                task_id=task.id,
                step_id=step.id,
                step_key=step.step_key,
                output_kind=step.output_kind,
                attempt=step.attempt,
                model_snapshot=dict(task.model_snapshot),
            )

    async def _complete_step(
        self,
        task_id: UUID,
        step_id: UUID,
        result: StepExecutionResult,
    ) -> GenerationSnapshot:
        async with self._session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id, with_for_update=True)
            step = await session.get(GenerationTaskStep, step_id, with_for_update=True)
            if task.status != "running" or step.status != "running":
                return await self._snapshot(session, task)
            step.provider_request_id = result.provider_request_id
            step.error_category = result.error_category
            step.error_message = None
            step.completed_at = utc_now()
            step.checkpoint = {
                **dict(step.checkpoint or {}),
                "provider_call_completed": result.status == "succeeded",
                "result": result.status,
                **self._output_checkpoint(result),
            }
            if result.status == "succeeded":
                step.status = "succeeded"
                return await self._snapshot(session, task)
            if result.status == "provider_uncertain":
                step.status = "provider_uncertain"
                task.status = "provider_uncertain"
                task.error_category = result.error_category
                task.completed_at = utc_now()
                return await self._snapshot(session, task)
            if (
                result.status == "retryable_failure"
                and step.attempt < self._max_step_attempts
            ):
                step.status = "pending"
                task.status = "queued"
                task.error_category = result.error_category
                task.dispatch_sequence += 1
                task.last_enqueued_at = utc_now()
                session.add(build_generation_outbox_event(task, "generation.retry"))
                return await self._snapshot(session, task)
            step.status = "failed"
            return await self._snapshot(session, task)

    async def _settle(self, task_id: UUID) -> GenerationSnapshot:
        async with self._session_factory() as session, session.begin():
            task = await session.get(GenerationTask, task_id, with_for_update=True)
            if task.status in TERMINAL_TASK_STATUSES:
                return await self._snapshot(session, task)
            if task.cancel_requested_at is not None:
                await self._cancel_remaining(session, task)
            steps = await self._steps(session, task.id, for_update=True)
            if any(step.status == "pending" for step in steps):
                return await self._snapshot(session, task)
            succeeded_credits = sum(
                step.estimated_credits for step in steps if step.status == "succeeded"
            )
            task.settled_credits = succeeded_credits
            task.progress = 100
            task.completed_at = utc_now()
            if succeeded_credits == task.estimated_credits:
                task.status = "succeeded"
                await finalize_reserved_credits(session, task)
            elif succeeded_credits > 0:
                task.status = "partial_success"
                await finalize_reserved_credits(session, task)
                await release_reserved_credits(
                    session,
                    task,
                    amount=task.estimated_credits - succeeded_credits,
                )
            else:
                task.status = (
                    "cancelled"
                    if all(step.status == "cancelled" for step in steps)
                    else "failed"
                )
                task.error_category = next(
                    (
                        step.error_category
                        for step in steps
                        if step.error_category is not None
                    ),
                    task.error_category,
                )
                await release_reserved_credits(session, task)
            return await self._snapshot(session, task)

    async def _cancel_remaining(
        self, session: AsyncSession, task: GenerationTask
    ) -> None:
        for step in await self._steps(session, task.id, for_update=True):
            if step.status == "pending":
                step.status = "cancelled"
                step.completed_at = utc_now()

    @staticmethod
    async def _steps(
        session: AsyncSession, task_id: UUID, *, for_update: bool = False
    ) -> list[GenerationTaskStep]:
        statement = (
            select(GenerationTaskStep)
            .where(GenerationTaskStep.task_id == task_id)
            .order_by(GenerationTaskStep.created_at, GenerationTaskStep.step_key)
        )
        if for_update:
            statement = statement.with_for_update()
        return list(await session.scalars(statement))

    async def _snapshot(
        self, session: AsyncSession, task: GenerationTask
    ) -> GenerationSnapshot:
        steps = await self._steps(session, task.id)
        return GenerationSnapshot(
            task_id=task.id,
            brief_id=task.brief_id,
            status=task.status,
            progress=task.progress,
            estimated_credits=task.estimated_credits,
            settled_credits=task.settled_credits,
            error_category=task.error_category,
            cancel_requested=task.cancel_requested_at is not None,
            steps=tuple(generation_step_snapshot(step) for step in steps),
        )

    @staticmethod
    def _output_checkpoint(result: StepExecutionResult) -> dict:
        values = {
            "output_asset_id": (
                str(result.output_asset_id)
                if result.output_asset_id is not None
                else None
            ),
            "asset_version": result.asset_version,
            "quality_status": result.quality_status,
            "quality_report_schema_version": result.quality_report_schema_version,
        }
        checkpoint = {key: value for key, value in values.items() if value is not None}
        if checkpoint:
            checkpoint["quality_download_allowed"] = result.download_allowed
        return checkpoint
