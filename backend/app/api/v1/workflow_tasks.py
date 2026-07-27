from uuid import UUID

from fastapi import APIRouter, Header, Request, Response

from app.schemas.briefs import BriefGenerationRequest
from app.services.workflow_contracts import (
    WorkflowOperationError,
    WorkflowTaskSnapshot,
)


router = APIRouter(prefix="/api/v1/workflow-tasks", tags=["workflow-tasks"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise WorkflowOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise WorkflowOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    services = request.app.state.workflow_services
    if services is None:
        raise WorkflowOperationError(
            "workflow_not_configured",
            "工作流任务服务未配置",
            503,
        )
    return services.tasks


@router.post("", status_code=202, response_model=WorkflowTaskSnapshot)
async def create_workflow_task(
    payload: BriefGenerationRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
) -> WorkflowTaskSnapshot:
    snapshot = await _service(request).create(
        _bearer_token(authorization),
        payload.to_command(),
        idempotency_key,
    )
    response.status_code = 200 if snapshot.replayed else 202
    response.headers["Cache-Control"] = "private, no-store"
    return snapshot


@router.get("", response_model=list[WorkflowTaskSnapshot])
async def list_workflow_tasks(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> list[WorkflowTaskSnapshot]:
    snapshots = await _service(request).list(_bearer_token(authorization))
    response.headers["Cache-Control"] = "private, no-store"
    return list(snapshots)


@router.get("/{task_id}", response_model=WorkflowTaskSnapshot)
async def get_workflow_task(
    task_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> WorkflowTaskSnapshot:
    snapshot = await _service(request).get(
        _bearer_token(authorization),
        task_id,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return snapshot
