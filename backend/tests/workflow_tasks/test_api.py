from datetime import datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.workflow_contracts import (
    WorkflowServices,
    WorkflowTaskSnapshot,
)
from tests.workflow_tasks.test_service import (
    ASSET_ID,
    MODEL_ID,
)
from tests.workflow_tasks.conftest import PROJECT_ID


TASK_ID = UUID("019fa300-0000-7000-8000-000000000051")


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class WorkflowStub:
    def __init__(self) -> None:
        self.created = []

    @staticmethod
    def snapshot(*, replayed: bool = False) -> WorkflowTaskSnapshot:
        return WorkflowTaskSnapshot(
            task_id=TASK_ID,
            project_id=PROJECT_ID,
            brief_id=None,
            generation_task_id=None,
            title="形成销售经营复盘",
            output_kinds=("pptx", "xlsx"),
            stage="brief_queued",
            status="queued",
            progress=0,
            note="已提交，等待整理 Brief",
            failure_code=None,
            failure_reason=None,
            estimated_credits=0,
            settled_credits=0,
            created_at=datetime(2026, 7, 27, 10, 0, 0),
            updated_at=datetime(2026, 7, 27, 10, 0, 0),
            replayed=replayed,
        )

    async def create(self, access_token, command, idempotency_key):
        self.created.append((access_token, command, idempotency_key))
        return self.snapshot()

    async def list(self, access_token):
        assert access_token == "access-token"
        return (self.snapshot(),)

    async def get(self, access_token, task_id):
        assert access_token == "access-token"
        assert task_id == TASK_ID
        return self.snapshot()


async def test_workflow_task_api_returns_immediately_and_lists_real_tasks() -> None:
    workflow = WorkflowStub()
    app = create_app(
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        workflow_services=WorkflowServices(workflow),
    )
    headers = {
        "Authorization": "Bearer access-token",
        "Idempotency-Key": "workflow-api-001",
    }
    payload = {
        "project_id": str(PROJECT_ID),
        "asset_ids": [str(ASSET_ID)],
        "term_library_versions": [],
        "skill_codes": [
            "ppt.sales-business-review.v1",
            "excel.sales-analysis-dashboard.v1",
        ],
        "model_id": str(MODEL_ID),
        "goal": "形成销售经营复盘",
        "audience": "销售管理层",
        "must_include": [],
        "must_exclude": [],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/api/v1/workflow-tasks",
            headers=headers,
            json=payload,
        )
        listed = await client.get(
            "/api/v1/workflow-tasks",
            headers={"Authorization": "Bearer access-token"},
        )
        detail = await client.get(
            f"/api/v1/workflow-tasks/{TASK_ID}",
            headers={"Authorization": "Bearer access-token"},
        )

    assert created.status_code == 202
    assert created.json()["task_id"] == str(TASK_ID)
    assert created.json()["note"] == "已提交，等待整理 Brief"
    assert listed.json()[0]["output_kinds"] == ["pptx", "xlsx"]
    assert detail.json()["stage"] == "brief_queued"
    assert created.headers["cache-control"] == "private, no-store"
    assert listed.headers["cache-control"] == "private, no-store"
    assert detail.headers["cache-control"] == "private, no-store"
    assert workflow.created[0][2] == "workflow-api-001"
