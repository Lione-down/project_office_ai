import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.briefs import Brief
from app.models.generation_tasks import GenerationTask
from app.models.projects import Project
from app.models.workflow_tasks import WorkflowTask
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.briefs.contracts import BriefGenerationCommand
from app.services.outbox_events import build_workflow_outbox_event
from app.services.workflow_contracts import (
    WorkflowOperationError,
    WorkflowTaskSnapshot,
)
from app.skills.catalog import SkillSelectionError, resolve_alpha_skill_selection


class WorkflowTaskService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions

    async def create(
        self,
        access_token: str,
        command: BriefGenerationCommand,
        idempotency_key: str,
    ) -> WorkflowTaskSnapshot:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}", idempotency_key) is None:
            raise WorkflowOperationError(
                "idempotency_key_invalid",
                "Idempotency-Key 无效",
                422,
            )
        current_user = await self._sessions.authenticate_access(access_token)
        try:
            selection = resolve_alpha_skill_selection(command.skill_codes)
        except SkillSelectionError as exception:
            raise WorkflowOperationError(
                exception.error_code,
                exception.message,
                422,
            ) from exception
        try:
            async with self._session_factory() as session, session.begin():
                existing = await self._by_idempotency(
                    session,
                    current_user.user_id,
                    idempotency_key,
                    for_update=True,
                )
                if existing is not None:
                    return await self._snapshot(session, existing, replayed=True)
                await self._require_project_owner(
                    session, current_user, command.project_id
                )
                task = WorkflowTask(
                    user_id=current_user.user_id,
                    project_id=command.project_id,
                    brief_group_id=None,
                    generation_task_id=None,
                    idempotency_key=idempotency_key,
                    title=command.goal,
                    request_snapshot=command.model_dump(mode="json"),
                    output_kinds=[skill.output_kind for skill in selection.skills],
                    stage="brief_queued",
                    status="queued",
                    progress=0,
                    note="已提交，等待整理 Brief",
                    failure_code=None,
                    failure_reason=None,
                    dispatch_sequence=1,
                )
                session.add(task)
                await session.flush()
                session.add(build_workflow_outbox_event(task))
                await session.flush()
                return await self._snapshot(session, task)
        except IntegrityError:
            async with self._session_factory() as session:
                existing = await self._by_idempotency(
                    session,
                    current_user.user_id,
                    idempotency_key,
                )
                if existing is None:
                    raise
                return await self._snapshot(session, existing, replayed=True)

    async def list(
        self,
        access_token: str,
        *,
        limit: int = 100,
    ) -> tuple[WorkflowTaskSnapshot, ...]:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            tasks = list(
                await session.scalars(
                    select(WorkflowTask)
                    .where(WorkflowTask.user_id == current_user.user_id)
                    .order_by(WorkflowTask.created_at.desc(), WorkflowTask.id.desc())
                    .limit(limit)
                )
            )
            return tuple([await self._snapshot(session, task) for task in tasks])

    async def get(
        self,
        access_token: str,
        task_id: UUID,
    ) -> WorkflowTaskSnapshot:
        current_user = await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            task = await session.scalar(
                select(WorkflowTask).where(
                    WorkflowTask.id == task_id,
                    WorkflowTask.user_id == current_user.user_id,
                )
            )
            if task is None:
                raise WorkflowOperationError(
                    "workflow_task_not_found",
                    "任务不存在",
                    404,
                )
            return await self._snapshot(session, task)

    @staticmethod
    async def _require_project_owner(
        session: AsyncSession,
        current_user: CurrentUser,
        project_id: UUID,
    ) -> None:
        project = await session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.user_id,
                Project.deleted_at.is_(None),
            )
        )
        if project is None:
            raise WorkflowOperationError("project_not_found", "项目不存在", 404)

    @staticmethod
    async def _by_idempotency(
        session: AsyncSession,
        user_id: UUID,
        idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> WorkflowTask | None:
        statement = select(WorkflowTask).where(
            WorkflowTask.user_id == user_id,
            WorkflowTask.idempotency_key == idempotency_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    @staticmethod
    async def _snapshot(
        session: AsyncSession,
        task: WorkflowTask,
        *,
        replayed: bool = False,
    ) -> WorkflowTaskSnapshot:
        brief_id = None
        if task.brief_group_id is not None:
            brief_id = await session.scalar(
                select(Brief.id)
                .where(Brief.brief_group_id == task.brief_group_id)
                .order_by(Brief.revision.desc())
                .limit(1)
            )
        generation = (
            await session.get(GenerationTask, task.generation_task_id)
            if task.generation_task_id is not None
            else None
        )
        stage = task.stage
        status = task.status
        progress = task.progress
        note = task.note
        failure_code = task.failure_code
        failure_reason = task.failure_reason
        estimated_credits = 0
        settled_credits = 0
        if generation is not None:
            stage = f"generation_{generation.status}"
            status = generation.status
            progress = min(100, 30 + round(generation.progress * 0.7))
            note = _generation_note(generation.status)
            failure_code = generation.error_category
            failure_reason = generation.error_message
            estimated_credits = generation.estimated_credits
            settled_credits = generation.settled_credits
        return WorkflowTaskSnapshot(
            task_id=task.id,
            project_id=task.project_id,
            brief_id=brief_id,
            generation_task_id=task.generation_task_id,
            title=task.title,
            output_kinds=tuple(task.output_kinds),
            stage=stage,
            status=status,
            progress=progress,
            note=note,
            failure_code=failure_code,
            failure_reason=failure_reason,
            estimated_credits=estimated_credits,
            settled_credits=settled_credits,
            created_at=task.created_at,
            updated_at=task.updated_at,
            replayed=replayed,
        )


def _generation_note(status: str) -> str:
    return {
        "queued": "文件生成已进入队列",
        "running": "正在生成文件",
        "succeeded": "任务已完成",
        "partial_success": "部分文件已完成",
        "failed": "文件生成失败",
        "provider_uncertain": "Provider 结果未知，未自动重试",
        "cancelled": "任务已取消",
    }.get(status, "文件生成状态已更新")
