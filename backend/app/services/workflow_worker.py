from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.users import User
from app.models.workflow_tasks import WorkflowTask
from app.services.auth_sessions import CurrentUser
from app.services.briefs.contracts import BriefGenerationCommand
from app.services.briefs.errors import BriefOperationError


@dataclass(frozen=True)
class WorkflowWorkerResult:
    task_id: UUID
    stage: str
    status: str
    progress: int
    note: str | None
    failure_code: str | None
    failure_reason: str | None


@dataclass(frozen=True)
class ClaimedWorkflowTask:
    task_id: UUID
    current_user: CurrentUser
    command: BriefGenerationCommand


class WorkflowTaskWorkerService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        brief_generator,
    ) -> None:
        self._session_factory = session_factory
        self._brief_generator = brief_generator

    async def process(self, task_id: UUID) -> WorkflowWorkerResult:
        claimed = await self._claim(task_id)
        if isinstance(claimed, WorkflowWorkerResult):
            return claimed
        try:
            generated = await self._brief_generator.generate_for_user(
                claimed.current_user,
                claimed.command,
                trace_id=f"workflow-task:{task_id}",
            )
        except BriefOperationError as exception:
            return await self._fail(
                task_id,
                error_code=exception.error_code,
                reason=exception.message,
                is_uncertain=exception.error_code == "provider_uncertain",
            )
        except Exception:
            return await self._fail(
                task_id,
                error_code="brief_worker_failed",
                reason="Brief 整理服务暂时不可用",
                is_uncertain=False,
            )
        return await self._complete(task_id, generated.brief_group_id)

    async def _claim(
        self,
        task_id: UUID,
    ) -> ClaimedWorkflowTask | WorkflowWorkerResult:
        async with self._session_factory() as session, session.begin():
            task = await session.get(WorkflowTask, task_id, with_for_update=True)
            if task is None:
                raise LookupError("workflow task not found")
            if task.status != "queued" or task.stage != "brief_queued":
                return self._result(task)
            user = await session.get(User, task.user_id)
            if user is None or user.status != "active":
                task.stage = "brief_failed"
                task.status = "failed"
                task.progress = 100
                task.note = "Brief 整理失败"
                task.failure_code = "user_unavailable"
                task.failure_reason = "用户当前不可用"
                task.completed_at = utc_now()
                return self._result(task)
            try:
                command = BriefGenerationCommand.model_validate(task.request_snapshot)
            except ValidationError:
                task.stage = "brief_failed"
                task.status = "failed"
                task.progress = 100
                task.note = "Brief 整理失败"
                task.failure_code = "workflow_request_invalid"
                task.failure_reason = "任务请求快照无效"
                task.completed_at = utc_now()
                return self._result(task)
            task.stage = "brief_generating"
            task.status = "running"
            task.progress = 10
            task.note = "正在整理 Brief"
            task.failure_code = None
            task.failure_reason = None
            task.started_at = task.started_at or utc_now()
            return ClaimedWorkflowTask(
                task_id=task.id,
                current_user=self._current_user(user),
                command=command,
            )

    async def _complete(
        self,
        task_id: UUID,
        brief_group_id: UUID,
    ) -> WorkflowWorkerResult:
        async with self._session_factory() as session, session.begin():
            task = await session.get(WorkflowTask, task_id, with_for_update=True)
            if task is None:
                raise LookupError("workflow task not found")
            if task.status != "running" or task.stage != "brief_generating":
                return self._result(task)
            task.brief_group_id = brief_group_id
            task.stage = "awaiting_confirmation"
            task.status = "awaiting_confirmation"
            task.progress = 30
            task.note = "Brief 已就绪，等待确认"
            task.failure_code = None
            task.failure_reason = None
            return self._result(task)

    async def _fail(
        self,
        task_id: UUID,
        *,
        error_code: str,
        reason: str,
        is_uncertain: bool,
    ) -> WorkflowWorkerResult:
        async with self._session_factory() as session, session.begin():
            task = await session.get(WorkflowTask, task_id, with_for_update=True)
            if task is None:
                raise LookupError("workflow task not found")
            if task.status != "running" or task.stage != "brief_generating":
                return self._result(task)
            task.stage = "brief_failed"
            task.status = "provider_uncertain" if is_uncertain else "failed"
            task.progress = 100
            task.note = "Brief 整理结果未知" if is_uncertain else "Brief 整理失败"
            task.failure_code = error_code
            task.failure_reason = reason
            task.completed_at = utc_now()
            return self._result(task)

    @staticmethod
    def _current_user(user: User) -> CurrentUser:
        return CurrentUser(
            user_id=user.id,
            phone_country_code=user.phone_country_code,
            phone_number=user.phone_number,
            role=user.role,
            status=user.status,
            credit_balance=user.credit_balance,
            must_change_password=user.must_change_password,
        )

    @staticmethod
    def _result(task: WorkflowTask) -> WorkflowWorkerResult:
        return WorkflowWorkerResult(
            task_id=task.id,
            stage=task.stage,
            status=task.status,
            progress=task.progress,
            note=task.note,
            failure_code=task.failure_code,
            failure_reason=task.failure_reason,
        )
