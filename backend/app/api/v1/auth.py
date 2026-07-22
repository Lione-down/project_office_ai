from fastapi import APIRouter, Header, Request, Response

from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_registration import AuthOperationError


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _auth_services(request: Request):
    services = request.app.state.auth_services
    if services is None:
        raise AuthOperationError(
            "auth_not_configured", "认证服务未配置", status_code=503
        )
    return services


def _bearer_token(authorization: str | None) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise AuthOperationError("session_invalid", "Session 已失效", 401)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthOperationError("session_invalid", "Session 已失效", 401)
    return token


def _client_context(request: Request) -> tuple[str, str | None, str | None]:
    ip_address = request.client.host if request.client else None
    device_info = request.headers.get("user-agent")
    return (
        ip_address or "unknown",
        device_info[:255] if device_info else None,
        ip_address,
    )


def _token_response(tokens) -> Response:
    response = Response(
        content=TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
        ).model_dump_json(),
        media_type="application/json",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, request: Request) -> Response:
    services = _auth_services(request)
    client_key, device_info, ip_address = _client_context(request)
    await services.registration.register(
        phone_number=payload.phone_number,
        password=payload.password,
        invite_code=payload.invite_code,
        client_key=client_key,
    )
    tokens = await services.sessions.login(
        phone_number=payload.phone_number,
        password=payload.password,
        client_key=client_key,
        device_info=device_info,
        ip_address=ip_address,
    )
    response = _token_response(tokens)
    response.status_code = 201
    return response


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> Response:
    client_key, device_info, ip_address = _client_context(request)
    tokens = await _auth_services(request).sessions.login(
        phone_number=payload.phone_number,
        password=payload.password,
        client_key=client_key,
        device_info=device_info,
        ip_address=ip_address,
    )
    return _token_response(tokens)


@router.post("/refresh")
async def refresh(payload: RefreshRequest, request: Request) -> Response:
    _, device_info, ip_address = _client_context(request)
    tokens = await _auth_services(request).sessions.refresh(
        refresh_token=payload.refresh_token,
        device_info=device_info,
        ip_address=ip_address,
    )
    return _token_response(tokens)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, authorization: str | None = Header(default=None)
) -> Response:
    await _auth_services(request).sessions.logout(_bearer_token(authorization))
    return Response(status_code=204)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    request: Request, authorization: str | None = Header(default=None)
) -> CurrentUserResponse:
    user = await _auth_services(request).sessions.authenticate_access(
        _bearer_token(authorization)
    )
    return CurrentUserResponse(**user.__dict__)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    _, device_info, ip_address = _client_context(request)
    tokens = await _auth_services(request).sessions.change_password(
        access_token=_bearer_token(authorization),
        current_password=payload.current_password,
        new_password=payload.new_password,
        device_info=device_info,
        ip_address=ip_address,
    )
    return _token_response(tokens)
