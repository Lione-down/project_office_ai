from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.schemas.invites import (
    InviteCreatedResponse,
    InviteCreateRequest,
    InviteSummaryResponse,
)
from app.services.auth_registration import AuthOperationError


router = APIRouter(prefix="/api/v1/admin/invite-codes", tags=["admin-invites"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise AuthOperationError("session_invalid", "Session 已失效", 401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthOperationError("session_invalid", "Session 已失效", 401)
    return token


def _invite_service(request: Request):
    services = request.app.state.auth_services
    if services is None or services.invites is None:
        raise AuthOperationError(
            "auth_not_configured", "认证服务未配置", status_code=503
        )
    return services.invites


@router.post("", status_code=201)
async def create_invite(
    payload: InviteCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    created = await _invite_service(request).create(
        _bearer_token(authorization),
        max_uses=payload.max_uses,
        expires_at=payload.expires_at,
        registration_credit=payload.registration_credit,
    )
    response = JSONResponse(
        status_code=201,
        content=InviteCreatedResponse(**created.__dict__).model_dump(mode="json"),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("", response_model=list[InviteSummaryResponse])
async def list_invites(
    request: Request, authorization: str | None = Header(default=None)
) -> list[InviteSummaryResponse]:
    invites = await _invite_service(request).list(_bearer_token(authorization))
    return [InviteSummaryResponse(**invite.__dict__) for invite in invites]
