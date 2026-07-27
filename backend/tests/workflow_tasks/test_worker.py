from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select

from app.models.workflow_tasks import WorkflowTask
from app.services.briefs.service import BriefOperationError
from app.services.workflow_worker import WorkflowTaskWorkerService
from tests.workflow_tasks.test_service import command


BRIEF_GROUP_ID = UUID("019fa300-0000-7000-8000-000000000061")


class ControlledBriefGenerator:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = []

    async def generate_for_user(self, current_user, generation_command, *, trace_id):
        self.calls.append((current_user, generation_command, trace_id))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def test_worker_persists_brief_ready_state_and_deduplicates_delivery(
    workflow_harness,
) -> None:
    created = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-worker-success",
    )
    generator = ControlledBriefGenerator(
        [SimpleNamespace(brief_group_id=BRIEF_GROUP_ID)]
    )
    worker = WorkflowTaskWorkerService(
        workflow_harness.session_factory,
        generator,
    )

    first = await worker.process(created.task_id)
    second = await worker.process(created.task_id)

    assert first.status == "awaiting_confirmation"
    assert first.stage == "awaiting_confirmation"
    assert first.progress == 30
    assert first.note == "Brief 已就绪，等待确认"
    assert second.status == "awaiting_confirmation"
    assert len(generator.calls) == 1
    async with workflow_harness.session_factory() as session:
        stored = await session.get(WorkflowTask, created.task_id)
    assert stored.brief_group_id == BRIEF_GROUP_ID
    assert stored.failure_code is None


async def test_worker_keeps_schema_failure_visible_with_safe_reason(
    workflow_harness,
) -> None:
    created = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-worker-failure",
    )
    generator = ControlledBriefGenerator(
        [
            BriefOperationError(
                "brief_schema_invalid",
                "Structured Brief Schema 无效",
                422,
            )
        ]
    )
    result = await WorkflowTaskWorkerService(
        workflow_harness.session_factory,
        generator,
    ).process(created.task_id)

    assert result.status == "failed"
    assert result.stage == "brief_failed"
    assert result.progress == 100
    assert result.failure_code == "brief_schema_invalid"
    assert result.failure_reason == "Structured Brief Schema 无效"
    assert result.note == "Brief 整理失败"

    async with workflow_harness.session_factory() as session:
        stored = await session.scalar(
            select(WorkflowTask).where(WorkflowTask.id == created.task_id)
        )
    assert stored.failure_reason == "Structured Brief Schema 无效"
