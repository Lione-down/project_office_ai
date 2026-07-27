import pytest_asyncio
from sqlalchemy import select

from app.models.workflow_tasks import WorkflowTask
from app.services.workflow_tasks import WorkflowTaskService
from tests.generation import conftest as generation_fixtures
from tests.generation.conftest import (
    BRIEF_GROUP_ID,
    BRIEF_ID,
    PROJECT_ID,
    USER_ID,
    FakeSessions,
)


@pytest_asyncio.fixture
async def generation_link_harness():
    async for harness in generation_fixtures.generation_harness.__wrapped__():
        yield harness


async def test_generation_creation_links_and_projects_into_existing_workflow_task(
    generation_link_harness,
) -> None:
    async with (
        generation_link_harness.session_factory() as session,
        session.begin(),
    ):
        session.add(
            WorkflowTask(
                user_id=USER_ID,
                project_id=PROJECT_ID,
                brief_group_id=BRIEF_GROUP_ID,
                generation_task_id=None,
                idempotency_key="workflow-generation-link",
                title="形成销售经营复盘",
                request_snapshot={},
                output_kinds=["pptx"],
                stage="awaiting_confirmation",
                status="awaiting_confirmation",
                progress=30,
                note="Brief 已就绪，等待确认",
                failure_code=None,
                failure_reason=None,
                dispatch_sequence=1,
            )
        )

    generation = await generation_link_harness.service.create(
        "access-token",
        BRIEF_ID,
        "generation-link-001",
    )
    workflow = (
        await WorkflowTaskService(
            generation_link_harness.session_factory,
            FakeSessions(),
        ).list("access-token")
    )[0]

    assert workflow.generation_task_id == generation.task_id
    assert workflow.stage == "generation_queued"
    assert workflow.status == "queued"
    assert workflow.progress == 30
    assert workflow.note == "文件生成已进入队列"
    assert workflow.estimated_credits == 800

    async with generation_link_harness.session_factory() as session:
        stored = await session.scalar(select(WorkflowTask))
    assert stored.generation_task_id == generation.task_id
