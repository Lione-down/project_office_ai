from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models.outbox_events import OutboxEvent
from app.models.workflow_tasks import WorkflowTask
from app.services.briefs.contracts import (
    BriefGenerationCommand,
    TermLibraryVersion,
)
from app.services.workflow_contracts import WorkflowOperationError
from app.services.workflow_tasks import WorkflowTaskService
from tests.workflow_tasks.conftest import (
    OTHER_USER_ID,
    PROJECT_ID,
    Sessions,
    current_user,
)


ASSET_ID = UUID("019fa300-0000-7000-8000-000000000021")
MODEL_ID = UUID("019fa300-0000-7000-8000-000000000031")
TERM_ID = UUID("019fa300-0000-7000-8000-000000000041")


def command() -> BriefGenerationCommand:
    return BriefGenerationCommand(
        project_id=PROJECT_ID,
        asset_ids=(ASSET_ID,),
        term_library_versions=(TermLibraryVersion(library_id=TERM_ID, version=1),),
        skill_codes=(
            "ppt.sales-business-review.v1",
            "excel.sales-analysis-dashboard.v1",
        ),
        model_id=MODEL_ID,
        goal="形成销售经营复盘",
        audience="销售管理层",
        must_include=(),
        must_exclude=(),
    )


async def test_enqueue_immediately_persists_visible_task_and_deduplicated_outbox(
    workflow_harness,
) -> None:
    created = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-create-001",
    )
    replayed = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-create-001",
    )

    assert created.task_id == replayed.task_id
    assert created.status == "queued"
    assert created.stage == "brief_queued"
    assert created.progress == 0
    assert created.note == "已提交，等待整理 Brief"
    assert created.output_kinds == ("pptx", "xlsx")
    assert replayed.replayed is True

    async with workflow_harness.session_factory() as session:
        task_count = await session.scalar(
            select(func.count()).select_from(WorkflowTask)
        )
        events = list(await session.scalars(select(OutboxEvent)))
        stored = await session.get(WorkflowTask, created.task_id)
    assert task_count == 1
    assert len(events) == 1
    assert events[0].event_type == "brief.generate"
    assert events[0].aggregate_type == "workflow_task"
    assert events[0].payload == {
        "workflow_task_id": str(created.task_id),
        "dispatch_sequence": 1,
    }
    assert "access-token" not in str(stored.request_snapshot)


async def test_list_and_detail_are_owner_scoped(workflow_harness) -> None:
    created = await workflow_harness.service.create(
        "access-token",
        command(),
        "workflow-owner-001",
    )
    listed = await workflow_harness.service.list("access-token")
    assert [item.task_id for item in listed] == [created.task_id]

    other_service = WorkflowTaskService(
        workflow_harness.session_factory,
        Sessions(current_user(OTHER_USER_ID)),
    )
    assert await other_service.list("other-token") == ()
    with pytest.raises(WorkflowOperationError) as error:
        await other_service.get("other-token", created.task_id)
    assert error.value.error_code == "workflow_task_not_found"
