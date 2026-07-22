from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.schemas.providers import (
    CredentialCreateRequest,
    CredentialAdminResponse,
    CredentialResponse,
    CredentialRevealRequest,
    CredentialRevealResponse,
    CredentialTestResponse,
    CredentialUpdateRequest,
    ModelCreateRequest,
    ModelResponse,
    ModelUpdateRequest,
    ProviderCreateRequest,
    ProviderResponse,
    ProviderUpdateRequest,
    SensitiveOperationRequest,
)
from app.services.provider_admin import AuditContext, ProviderOperationError


admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin-providers"])
model_router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise ProviderOperationError("session_invalid", "Session 已失效", 401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise ProviderOperationError("session_invalid", "Session 已失效", 401)
    return token


def _provider_service(request: Request):
    service = request.app.state.provider_services
    if service is None:
        raise ProviderOperationError(
            "provider_not_configured", "Provider 服务未配置", 503
        )
    return service


def _audit_context(request: Request) -> AuditContext:
    return AuditContext(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        trace_id=request.state.trace_id,
    )


@admin_router.post("/providers", status_code=201, response_model=ProviderResponse)
async def create_provider(
    payload: ProviderCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ProviderResponse:
    created = await _provider_service(request).create_provider(
        access_token=_bearer_token(authorization), **payload.model_dump()
    )
    return ProviderResponse(**created.__dict__)


@admin_router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(
    request: Request, authorization: str | None = Header(default=None)
) -> list[ProviderResponse]:
    providers = await _provider_service(request).list_providers(
        _bearer_token(authorization)
    )
    return [ProviderResponse(**provider.__dict__) for provider in providers]


@admin_router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    payload: ProviderUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ProviderResponse:
    updated = await _provider_service(request).update_provider(
        access_token=_bearer_token(authorization),
        provider_id=provider_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return ProviderResponse(**updated.__dict__)


@admin_router.post("/credentials", status_code=201, response_model=CredentialResponse)
async def create_credential(
    payload: CredentialCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    values = payload.model_dump(exclude={"api_key"})
    created = await _provider_service(request).create_credential(
        access_token=_bearer_token(authorization),
        api_key=payload.api_key.get_secret_value(),
        **values,
    )
    response = JSONResponse(
        status_code=201,
        content=CredentialResponse(**created.__dict__).model_dump(mode="json"),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_router.get("/credentials", response_model=list[CredentialAdminResponse])
async def list_credentials(
    request: Request, authorization: str | None = Header(default=None)
) -> list[CredentialAdminResponse]:
    credentials = await _provider_service(request).list_credentials(
        _bearer_token(authorization)
    )
    return [CredentialAdminResponse(**item.__dict__) for item in credentials]


@admin_router.patch(
    "/credentials/{credential_id}", response_model=CredentialAdminResponse
)
async def update_credential(
    credential_id: UUID,
    payload: CredentialUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> CredentialAdminResponse:
    updated = await _provider_service(request).update_credential(
        access_token=_bearer_token(authorization),
        credential_id=credential_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return CredentialAdminResponse(**updated.__dict__)


@admin_router.post(
    "/credentials/{credential_id}/test", response_model=CredentialTestResponse
)
async def test_credential(
    credential_id: UUID,
    payload: SensitiveOperationRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> CredentialTestResponse:
    result = await _provider_service(request).test_credential(
        access_token=_bearer_token(authorization),
        credential_id=credential_id,
        reason=payload.reason,
        audit=_audit_context(request),
    )
    return CredentialTestResponse(**result.__dict__)


@admin_router.post(
    "/credentials/{credential_id}/reveal",
    response_model=CredentialRevealResponse,
)
async def reveal_credential(
    credential_id: UUID,
    payload: CredentialRevealRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    revealed = await _provider_service(request).reveal_credential(
        access_token=_bearer_token(authorization),
        credential_id=credential_id,
        current_password=payload.current_password.get_secret_value(),
        reason=payload.reason,
        audit=_audit_context(request),
    )
    response = JSONResponse(
        content=CredentialRevealResponse(**revealed.__dict__).model_dump(mode="json")
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@admin_router.post("/models", status_code=201, response_model=ModelResponse)
async def create_model(
    payload: ModelCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ModelResponse:
    created = await _provider_service(request).create_model(
        access_token=_bearer_token(authorization), **payload.model_dump()
    )
    return ModelResponse(**created.__dict__)


@admin_router.get("/models", response_model=list[ModelResponse])
async def list_admin_models(
    request: Request, authorization: str | None = Header(default=None)
) -> list[ModelResponse]:
    models = await _provider_service(request).list_models(_bearer_token(authorization))
    return [ModelResponse(**model.__dict__) for model in models]


@admin_router.patch("/models/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: UUID,
    payload: ModelUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ModelResponse:
    updated = await _provider_service(request).update_model(
        access_token=_bearer_token(authorization),
        model_id=model_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return ModelResponse(**updated.__dict__)


@model_router.get("", response_model=list[ModelResponse])
async def list_models(
    request: Request, authorization: str | None = Header(default=None)
) -> list[ModelResponse]:
    models = await _provider_service(request).list_visible_models(
        _bearer_token(authorization)
    )
    return [ModelResponse(**model.__dict__) for model in models]
