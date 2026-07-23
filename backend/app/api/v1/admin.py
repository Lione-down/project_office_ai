from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import FileResponse

from app.api.v1.assets import _content_response
from app.schemas.admin import (
    AdminAssetResponse,
    AdminUserResponse,
    AuditLogResponse,
    CreditAdjustmentRequest,
    CreditAdjustmentResponse,
    PasswordResetRequest,
    SensitiveOperationRequest,
    UserStatusRequest,
)
from app.services.admin_contracts import AdminOperationError
from app.services.audit import AuditContext


router = APIRouter(prefix="/api/v1/admin", tags=["admin-operations"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise AdminOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise AdminOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    service = request.app.state.admin_services
    if service is None:
        raise AdminOperationError("admin_not_configured", "管理员服务未配置", 503)
    return service


def _audit(request: Request) -> AuditContext:
    return AuditContext(
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
        request.state.trace_id,
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    request: Request, authorization: str | None = Header(default=None)
) -> list[AdminUserResponse]:
    items = await _service(request).list_users(_bearer_token(authorization))
    return [AdminUserResponse(**item.__dict__) for item in items]


@router.post("/users/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: UUID,
    payload: PasswordResetRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _service(request).reset_password(
        access_token=_bearer_token(authorization),
        target_user_id=user_id,
        new_password=payload.new_password.get_secret_value(),
        current_password=payload.current_password.get_secret_value(),
        reason=payload.reason,
        audit=_audit(request),
    )
    return Response(status_code=204)


@router.post("/users/{user_id}/status", status_code=204)
async def change_user_status(
    user_id: UUID,
    payload: UserStatusRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _service(request).change_user_status(
        access_token=_bearer_token(authorization),
        target_user_id=user_id,
        status=payload.status,
        current_password=payload.current_password.get_secret_value(),
        reason=payload.reason,
        audit=_audit(request),
    )
    return Response(status_code=204)


@router.get("/assets", response_model=list[AdminAssetResponse])
async def list_assets(
    request: Request, authorization: str | None = Header(default=None)
) -> list[AdminAssetResponse]:
    items = await _service(request).list_assets(_bearer_token(authorization))
    return [AdminAssetResponse(**item.__dict__) for item in items]


async def _open_asset(
    asset_id: UUID,
    payload: SensitiveOperationRequest,
    request: Request,
    authorization: str | None,
    action: str,
    disposition: str,
) -> FileResponse:
    content = await _service(request).open_asset(
        access_token=_bearer_token(authorization),
        asset_id=asset_id,
        current_password=payload.current_password.get_secret_value(),
        reason=payload.reason,
        action=action,
        audit=_audit(request),
    )
    return _content_response(content, disposition)


@router.post("/assets/{asset_id}/preview")
async def preview_asset(
    asset_id: UUID,
    payload: SensitiveOperationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> FileResponse:
    return await _open_asset(
        asset_id, payload, request, authorization, "preview", "inline"
    )


@router.post("/assets/{asset_id}/download")
async def download_asset(
    asset_id: UUID,
    payload: SensitiveOperationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> FileResponse:
    return await _open_asset(
        asset_id, payload, request, authorization, "download", "attachment"
    )


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: UUID,
    payload: SensitiveOperationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _service(request).delete_asset(
        access_token=_bearer_token(authorization),
        asset_id=asset_id,
        current_password=payload.current_password.get_secret_value(),
        reason=payload.reason,
        audit=_audit(request),
    )
    return Response(status_code=204)


@router.post(
    "/credits/adjustments", response_model=CreditAdjustmentResponse, status_code=201
)
async def adjust_credits(
    payload: CreditAdjustmentRequest,
    request: Request,
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=1, max_length=128
    ),
    authorization: str | None = Header(default=None),
) -> CreditAdjustmentResponse:
    result = await _service(request).adjust_credits(
        access_token=_bearer_token(authorization),
        target_user_id=payload.user_id,
        amount=payload.amount,
        current_password=payload.current_password.get_secret_value(),
        reason=payload.reason,
        idempotency_key=idempotency_key,
        audit=_audit(request),
    )
    return CreditAdjustmentResponse(**result.__dict__)


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    request: Request, authorization: str | None = Header(default=None)
) -> list[AuditLogResponse]:
    items = await _service(request).list_audit_logs(_bearer_token(authorization))
    return [AuditLogResponse(**item.__dict__) for item in items]
