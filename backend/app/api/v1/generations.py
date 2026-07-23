from uuid import UUID

from fastapi import APIRouter, Header, Request, Response

from app.schemas.generation import (
    CreditBalanceResponse,
    CreditEntryResponse,
    CreditLedgerResponse,
    GenerationCreateRequest,
    GenerationTaskResponse,
)
from app.services.generation_contracts import GenerationOperationError


task_router = APIRouter(prefix="/api/v1/generations", tags=["generations"])
credit_router = APIRouter(prefix="/api/v1/credits", tags=["credits"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise GenerationOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise GenerationOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    services = request.app.state.generation_services
    if services is None:
        raise GenerationOperationError(
            "generation_not_configured", "生成任务服务未配置", 503
        )
    return services.generation


@task_router.post("", response_model=GenerationTaskResponse)
async def create_generation(
    payload: GenerationCreateRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
) -> GenerationTaskResponse:
    snapshot = await _service(request).create(
        _bearer_token(authorization), payload.brief_id, idempotency_key
    )
    response.status_code = 200 if snapshot.replayed else 201
    response.headers["Cache-Control"] = "private, no-store"
    return GenerationTaskResponse.from_snapshot(snapshot)


@task_router.get("/{task_id}", response_model=GenerationTaskResponse)
async def get_generation(
    task_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> GenerationTaskResponse:
    snapshot = await _service(request).get(_bearer_token(authorization), task_id)
    response.headers["Cache-Control"] = "private, no-store"
    return GenerationTaskResponse.from_snapshot(snapshot)


@task_router.post("/{task_id}/cancel", response_model=GenerationTaskResponse)
async def cancel_generation(
    task_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> GenerationTaskResponse:
    snapshot = await _service(request).cancel(_bearer_token(authorization), task_id)
    response.headers["Cache-Control"] = "private, no-store"
    return GenerationTaskResponse.from_snapshot(snapshot)


@task_router.post("/{task_id}/retry", response_model=GenerationTaskResponse)
async def retry_generation(
    task_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> GenerationTaskResponse:
    snapshot = await _service(request).retry(_bearer_token(authorization), task_id)
    response.headers["Cache-Control"] = "private, no-store"
    return GenerationTaskResponse.from_snapshot(snapshot)


@credit_router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> CreditBalanceResponse:
    balance = await _service(request).balance(_bearer_token(authorization))
    response.headers["Cache-Control"] = "private, no-store"
    return CreditBalanceResponse(balance=balance)


@credit_router.get("/ledger", response_model=CreditLedgerResponse)
async def get_credit_ledger(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> CreditLedgerResponse:
    entries = await _service(request).ledger(_bearer_token(authorization))
    response.headers["Cache-Control"] = "private, no-store"
    return CreditLedgerResponse(
        entries=tuple(CreditEntryResponse.from_snapshot(item) for item in entries)
    )
