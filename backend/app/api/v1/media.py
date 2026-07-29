from uuid import UUID

from fastapi import APIRouter, Header, Request, Response, status

from app.services.media.images.contracts import (
    ImageJobCreateCommand,
    ImageJobSnapshot,
)
from app.services.media.images.service import ImageJobOperationError


router = APIRouter(tags=["media"])


def _service(request: Request):
    service = request.app.state.media_services
    if service is None:
        raise ImageJobOperationError("media_not_configured", "图片服务未配置", 503)
    return service


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise ImageJobOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise ImageJobOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post(
    "/api/v1/deck-drafts/{draft_id}/media/images",
    response_model=ImageJobSnapshot,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_image_job(
    draft_id: UUID,
    command: ImageJobCreateCommand,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ImageJobSnapshot:
    snapshot = await _service(request).create(
        _bearer_token(authorization),
        draft_id,
        command,
        idempotency_key,
    )
    _no_store(response)
    return snapshot


@router.get(
    "/api/v1/media/jobs/{job_id}",
    response_model=ImageJobSnapshot,
)
async def get_image_job(
    job_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> ImageJobSnapshot:
    snapshot = await _service(request).get(_bearer_token(authorization), job_id)
    _no_store(response)
    return snapshot


@router.post(
    "/api/v1/media/jobs/{job_id}/cancel",
    response_model=ImageJobSnapshot,
)
async def cancel_image_job(
    job_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> ImageJobSnapshot:
    snapshot = await _service(request).cancel(_bearer_token(authorization), job_id)
    _no_store(response)
    return snapshot
