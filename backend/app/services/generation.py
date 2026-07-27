from datetime import timedelta
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.base import utc_now
from app.models.briefs import Brief
from app.models.credit_ledger import CreditLedger
from app.models.generation_task_inputs import GenerationTaskInput
from app.models.generation_task_steps import GenerationTaskStep
from app.models.generation_tasks import GenerationTask
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.credit_transactions import (
    release_reserved_credits,
    retry_billing_key,
)
from app.services.generation_contracts import (
    CreditEntrySnapshot,
    GenerationOperationError,
    GenerationOutputSnapshot,
    GenerationSnapshot,
    TERMINAL_TASK_STATUSES,
)
from app.services.generation_snapshots import (
    build_model_snapshot,
    build_skill_snapshot,
    validate_runtime_snapshot,
)
from app.services.generation_outputs import (
    generation_output_snapshot,
    generation_step_snapshot,
    verify_generation_output,
)
from app.services.outbox_events import build_generation_outbox_event
from app.services.preflight.contracts import PreflightSnapshot


class GenerationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        *,
        task_timeout_seconds: int = 2_700,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._task_timeout = timedelta(seconds=task_timeout_seconds)

    async def create(
        self,
        access_token: str,
        brief_id: UUID,
        idempotency_key: str,
    ) -> GenerationSnapshot:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", idempotency_key) is None:
            raise GenerationOperationError(
                "idempotency_key_invalid", "Idempotency-Key 无效", 422
            )
        current_user = await self._sessions.authenticate_access(access_token)
        try:
            async with self._session_factory() as session, session.begin():
                existing = await self._task_by_idempotency(
                    session, current_user.user_id, idempotency_key, for_update=True
                )
                if existing is not None:
                    return await self._snapshot(session, existing, replayed=True)
                brief = await self._owned_confirmed_brief(
                    session, current_user, brief_id
                )
                preflight = self._validated_preflight(brief)
                model = await session.get(AiModel, brief.selected_model_id)
                if model is None:
                    raise GenerationOperationError("model_not_found", "模型不存在", 404)
                credential = await session.get(ProviderCredential, model.credential_id)
                if credential is None or credential.status != "active":
                    raise GenerationOperationError(
                        "credential_unavailable", "Credential 当前不可用", 409
                    )
                provider = await session.get(AiProvider, model.provider_id)
                validate_runtime_snapshot(brief, preflight, model, credential, provider)
                user = await session.get(
                    User, current_user.user_id, with_for_update=True
                )
                if user is None:
                    raise GenerationOperationError(
                        "session_invalid", "Session 已失效", 401
                    )
                if user.credit_balance < preflight.estimated_credits:
                    raise GenerationOperationError(
                        "insufficient_credits", "积分余额不足", 409
                    )
                now = utc_now()
                task = GenerationTask(
                    user_id=user.id,
                    project_id=brief.project_id,
                    brief_id=brief.id,
                    model_id=model.id,
                    credential_id=credential.id,
                    idempotency_key=idempotency_key,
                    combination_group_id=brief.brief_group_id,
                    parent_task_id=None,
                    status="queued",
                    progress=0,
                    skill_snapshot=build_skill_snapshot(brief, preflight),
                    model_snapshot=build_model_snapshot(model, credential),
                    estimated_credits=preflight.estimated_credits,
                    settled_credits=0,
                    retry_count=0,
                    dispatch_sequence=1,
                    timeout_at=now + self._task_timeout,
                    last_enqueued_at=now,
                )
                session.add(task)
                await session.flush()
                workflow_task = await session.scalar(
                    select(WorkflowTask)
                    .where(
                        WorkflowTask.user_id == current_user.user_id,
                        WorkflowTask.brief_group_id == brief.brief_group_id,
                    )
                    .with_for_update()
                )
                if workflow_task is not None:
                    workflow_task.generation_task_id = task.id
                    workflow_task.stage = "generation_queued"
                    workflow_task.status = "queued"
                    workflow_task.progress = 30
                    workflow_task.note = "文件生成已进入队列"
                    workflow_task.failure_code = None
                    workflow_task.failure_reason = None
                session.add_all(self._steps(task, preflight, model))
                session.add_all(self._inputs(task, brief, preflight))
                user.credit_balance -= preflight.estimated_credits
                session.add(
                    CreditLedger(
                        user_id=user.id,
                        task_id=task.id,
                        entry_type="generation_reserve",
                        amount=-preflight.estimated_credits,
                        balance_after=user.credit_balance,
                        related_entry_id=None,
                        idempotency_key=idempotency_key,
                        description=None,
                    )
                )
                session.add(build_generation_outbox_event(task, "generation.queued"))
                await session.flush()
                return await self._snapshot(session, task)
        except IntegrityError:
            async with self._session_factory() as session:
                existing = await self._task_by_idempotency(
                    session, current_user.user_id, idempotency_key
                )
                if existing is None:
                    raise
                return await self._snapshot(session, existing, replayed=True)

    async def get(self, access_token: str, task_id: UUID) -> GenerationSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            task = await self._owned_task(session, current_user, task_id)
            snapshot = await self._snapshot(session, task)
            for step in snapshot.steps:
                await verify_generation_output(session, task, step)
            return snapshot

    async def outputs(
        self, access_token: str, task_id: UUID
    ) -> tuple[GenerationOutputSnapshot, ...]:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            task = await self._owned_task(session, current_user, task_id)
            snapshot = await self._snapshot(session, task)
            outputs = []
            for step in snapshot.steps:
                await verify_generation_output(session, task, step)
                outputs.append(generation_output_snapshot(step))
            return tuple(outputs)

    async def cancel(self, access_token: str, task_id: UUID) -> GenerationSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            task = await self._owned_task(
                session, current_user, task_id, for_update=True
            )
            if task.status in TERMINAL_TASK_STATUSES:
                return await self._snapshot(session, task)
            now = utc_now()
            if task.status == "running":
                task.cancel_requested_at = now
            else:
                task.status = "cancelled"
                task.completed_at = now
                task.progress = 100
                for step in await self._task_steps(session, task.id, for_update=True):
                    if step.status not in {"succeeded", "failed"}:
                        step.status = "cancelled"
                        step.completed_at = now
                await release_reserved_credits(session, task)
            return await self._snapshot(session, task)

    async def retry(self, access_token: str, task_id: UUID) -> GenerationSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session, session.begin():
            task = await self._owned_task(
                session, current_user, task_id, for_update=True
            )
            if task.status != "failed":
                raise GenerationOperationError(
                    "task_retry_not_allowed", "当前任务状态不允许重试", 409
                )
            user = await session.get(User, task.user_id, with_for_update=True)
            if user.credit_balance < task.estimated_credits:
                raise GenerationOperationError(
                    "insufficient_credits", "积分余额不足", 409
                )
            retry_number = task.retry_count + 1
            billing_key = retry_billing_key(task.id, retry_number)
            user.credit_balance -= task.estimated_credits
            session.add(
                CreditLedger(
                    user_id=user.id,
                    task_id=task.id,
                    entry_type="generation_reserve",
                    amount=-task.estimated_credits,
                    balance_after=user.credit_balance,
                    related_entry_id=None,
                    idempotency_key=billing_key,
                    description=None,
                )
            )
            task.retry_count = retry_number
            task.status = "queued"
            task.progress = 0
            task.completed_at = None
            task.error_category = None
            task.error_message = None
            task.cancel_requested_at = None
            task.dispatch_sequence += 1
            task.last_enqueued_at = utc_now()
            for step in await self._task_steps(session, task.id, for_update=True):
                step.status = "pending"
                step.attempt = 0
                step.checkpoint = {}
                step.error_category = None
                step.error_message = None
                step.started_at = None
                step.completed_at = None
            session.add(build_generation_outbox_event(task, "generation.retry"))
            return await self._snapshot(session, task)

    async def balance(self, access_token: str) -> int:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            user = await session.get(User, current_user.user_id)
            if user is None:
                raise GenerationOperationError("session_invalid", "Session 已失效", 401)
            return user.credit_balance

    async def ledger(
        self, access_token: str, *, limit: int = 100
    ) -> tuple[CreditEntrySnapshot, ...]:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            entries = list(
                await session.scalars(
                    select(CreditLedger)
                    .where(CreditLedger.user_id == current_user.user_id)
                    .order_by(CreditLedger.created_at.desc(), CreditLedger.id.desc())
                    .limit(limit)
                )
            )
            return tuple(
                CreditEntrySnapshot(
                    entry_id=entry.id,
                    task_id=entry.task_id,
                    entry_type=entry.entry_type,
                    amount=entry.amount,
                    balance_after=entry.balance_after,
                    related_entry_id=entry.related_entry_id,
                    created_at=entry.created_at,
                )
                for entry in entries
            )

    @staticmethod
    async def _task_by_idempotency(
        session: AsyncSession,
        user_id: UUID,
        idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> GenerationTask | None:
        statement = select(GenerationTask).where(
            GenerationTask.user_id == user_id,
            GenerationTask.idempotency_key == idempotency_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    @staticmethod
    async def _owned_confirmed_brief(
        session: AsyncSession, current_user: CurrentUser, brief_id: UUID
    ) -> Brief:
        brief = await session.scalar(
            select(Brief)
            .where(
                Brief.id == brief_id,
                Brief.user_id == current_user.user_id,
            )
            .with_for_update()
        )
        if brief is None:
            raise GenerationOperationError("brief_not_found", "Brief 不存在", 404)
        latest = await session.scalar(
            select(Brief)
            .where(
                Brief.brief_group_id == brief.brief_group_id,
                Brief.user_id == current_user.user_id,
            )
            .order_by(Brief.revision.desc())
            .limit(1)
            .with_for_update()
        )
        if latest is None or latest.id != brief.id:
            raise GenerationOperationError(
                "brief_revision_stale", "Brief Revision 已更新，请刷新后重试", 409
            )
        if (
            brief.status != "queued"
            or brief.preflight_snapshot is None
            or brief.estimated_credits is None
            or brief.confirmed_at is None
        ):
            raise GenerationOperationError(
                "brief_not_confirmed", "Brief 尚未完成确认", 409
            )
        return brief

    @staticmethod
    def _validated_preflight(brief: Brief) -> PreflightSnapshot:
        try:
            snapshot = PreflightSnapshot.model_validate(brief.preflight_snapshot)
        except Exception as exception:
            raise GenerationOperationError(
                "brief_integrity_failed", "Brief 确认快照不完整", 409
            ) from exception
        if (
            snapshot.status != "queued"
            or snapshot.has_blockers
            or snapshot.brief_id != brief.id
            or snapshot.estimated_credits != brief.estimated_credits
            or not 1 <= len(snapshot.outputs) <= 2
            or len({output.kind for output in snapshot.outputs})
            != len(snapshot.outputs)
            or any(output.estimated_credits <= 0 for output in snapshot.outputs)
            or sum(output.estimated_credits for output in snapshot.outputs)
            != snapshot.estimated_credits
            or snapshot.confirmed_at is None
        ):
            raise GenerationOperationError(
                "brief_integrity_failed", "Brief 确认快照不完整", 409
            )
        return snapshot

    @staticmethod
    def _steps(
        task: GenerationTask, preflight: PreflightSnapshot, model: AiModel
    ) -> list[GenerationTaskStep]:
        return [
            GenerationTaskStep(
                task_id=task.id,
                step_key=f"render:{output.kind}",
                output_kind=output.kind,
                status="pending",
                attempt=0,
                estimated_credits=output.estimated_credits,
                checkpoint={},
                token_estimate=model.max_output_tokens,
            )
            for output in preflight.outputs
        ]

    @staticmethod
    def _inputs(
        task: GenerationTask, brief: Brief, preflight: PreflightSnapshot
    ) -> list[GenerationTaskInput]:
        inputs = [
            GenerationTaskInput(
                task_id=task.id,
                input_type="brief",
                reference_key=str(brief.id),
                snapshot={
                    "brief_id": str(brief.id),
                    "brief_group_id": str(brief.brief_group_id),
                    "revision": brief.revision,
                    "content_checksum": brief.content_checksum,
                    "resolutions": brief.source_snapshot.get("resolutions", []),
                },
            )
        ]
        for item in brief.source_snapshot.get("source_asset_versions", []):
            inputs.append(
                GenerationTaskInput(
                    task_id=task.id,
                    input_type="asset",
                    reference_key=str(item["asset_id"]),
                    snapshot=dict(item),
                )
            )
        for output in preflight.outputs:
            inputs.append(
                GenerationTaskInput(
                    task_id=task.id,
                    input_type="template",
                    reference_key=f"{output.template_code}@{output.template_version}",
                    snapshot={
                        "template_code": output.template_code,
                        "version": output.template_version,
                        "output_kind": output.kind,
                    },
                )
            )
        for item in brief.source_snapshot.get("term_library_versions", []):
            inputs.append(
                GenerationTaskInput(
                    task_id=task.id,
                    input_type="term_library",
                    reference_key=str(item["library_id"]),
                    snapshot=dict(item),
                )
            )
        return inputs

    @staticmethod
    async def _owned_task(
        session: AsyncSession,
        current_user: CurrentUser,
        task_id: UUID,
        *,
        for_update: bool = False,
    ) -> GenerationTask:
        statement = select(GenerationTask).where(
            GenerationTask.id == task_id,
            GenerationTask.user_id == current_user.user_id,
        )
        if for_update:
            statement = statement.with_for_update()
        task = await session.scalar(statement)
        if task is None:
            raise GenerationOperationError("task_not_found", "生成任务不存在", 404)
        return task

    @staticmethod
    async def _task_steps(
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
        self,
        session: AsyncSession,
        task: GenerationTask,
        *,
        replayed: bool = False,
    ) -> GenerationSnapshot:
        steps = await self._task_steps(session, task.id)
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
            replayed=replayed,
        )
