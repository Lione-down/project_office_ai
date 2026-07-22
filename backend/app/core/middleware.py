import logging
import re
import tempfile
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.auth_registration import AuthOperationError
from app.services.asset_contracts import AssetOperationError

TRACE_ID_HEADER = "X-Trace-ID"
_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_request_logger = logging.getLogger("office_ai.request")


class UploadBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int,
        auth_sessions: object | None,
        asset_services: object | None,
    ) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes
        self._auth_sessions = auth_sessions
        self._asset_services = asset_services

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/v1/assets/uploads"
        ):
            await self._app(scope, receive, send)
            return

        token = await self._authenticate(scope, receive, send)
        if token is None:
            return
        if await self._return_replay(scope, receive, send, token):
            return

        content_lengths = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        has_transfer_encoding = any(
            name.lower() == b"transfer-encoding" for name, _ in scope.get("headers", [])
        )
        if has_transfer_encoding or len(content_lengths) != 1:
            await self._reject_body(scope, receive, send, "upload_body_invalid")
            return

        raw_content_length = content_lengths[0]
        try:
            content_length = int(raw_content_length)
        except ValueError:
            content_length = -1
        if not raw_content_length.isdigit() or content_length < 0:
            await self._reject_body(scope, receive, send, "upload_body_invalid")
            return
        if content_length > self._max_body_bytes:
            await self._reject_body(scope, receive, send, "upload_body_too_large")
            return

        body_spool = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
        try:
            received_bytes = 0
            while True:
                message = await receive()
                if message["type"] != "http.request":
                    await self._reject_body(scope, receive, send, "upload_body_invalid")
                    return
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > self._max_body_bytes:
                    await self._reject_body(
                        scope, receive, send, "upload_body_too_large"
                    )
                    return
                body_spool.write(body)
                if not message.get("more_body", False):
                    break
            if received_bytes != content_length:
                await self._reject_body(scope, receive, send, "upload_body_invalid")
                return

            body_spool.seek(0)
            replay_complete = False

            async def replay_receive() -> Message:
                nonlocal replay_complete
                if replay_complete:
                    return {"type": "http.disconnect"}
                chunk = body_spool.read(1024 * 1024)
                more_body = body_spool.tell() < received_bytes
                replay_complete = not more_body
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": more_body,
                }

            await self._app(scope, replay_receive, send)
        finally:
            body_spool.close()

    async def _return_replay(
        self, scope: Scope, receive: Receive, send: Send, token: str
    ) -> bool:
        if self._asset_services is None:
            await self._reject(
                scope, receive, send, "asset_not_configured", "资产服务未配置", 503
            )
            return True
        keys = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"idempotency-key"
        ]
        if len(keys) != 1:
            await self._reject(
                scope,
                receive,
                send,
                "validation_error",
                "请求参数无效",
                422,
            )
            return True
        key = keys[0].decode("latin-1").strip()
        try:
            replay = await self._asset_services.find_upload_replay(token, key)
        except AssetOperationError as exception:
            await self._reject(
                scope,
                receive,
                send,
                exception.error_code,
                exception.message,
                exception.status_code,
            )
            return True
        if replay is None:
            return False
        response = JSONResponse(status_code=201, content=jsonable_encoder(replay))
        await response(scope, receive, send)
        return True

    async def _authenticate(
        self, scope: Scope, receive: Receive, send: Send
    ) -> str | None:
        if self._auth_sessions is None:
            await self._reject(
                scope, receive, send, "auth_not_configured", "认证服务未配置", 503
            )
            return None
        authorization = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"authorization"
        ]
        if len(authorization) != 1:
            await self._reject(
                scope, receive, send, "session_invalid", "Session 已失效", 401
            )
            return None
        try:
            scheme, token = authorization[0].decode("latin-1").split(" ", 1)
        except ValueError:
            scheme, token = "", ""
        if scheme.lower() != "bearer" or not token.strip():
            await self._reject(
                scope, receive, send, "session_invalid", "Session 已失效", 401
            )
            return None
        try:
            await self._auth_sessions.authenticate_access(token.strip())
        except AuthOperationError as exception:
            await self._reject(
                scope,
                receive,
                send,
                exception.error_code,
                exception.message,
                exception.status_code,
            )
            return None
        return token.strip()

    @classmethod
    async def _reject_body(
        cls, scope: Scope, receive: Receive, send: Send, error_code: str
    ) -> None:
        await cls._reject(
            scope,
            receive,
            send,
            error_code,
            "上传请求体无效或超过允许上限",
            413,
        )

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        error_code: str,
        message: str,
        status_code: int,
    ) -> None:
        state: dict[str, Any] = scope.get("state", {})
        response = JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "error_code": error_code,
                    "message": message,
                    "trace_id": state.get("trace_id", ""),
                }
            },
        )
        await response(scope, receive, send)


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming_trace_id = request.headers.get(TRACE_ID_HEADER, "")
        trace_id = (
            incoming_trace_id
            if _TRACE_ID_PATTERN.fullmatch(incoming_trace_id)
            else str(uuid4())
        )
        request.state.trace_id = trace_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id
        _request_logger.info(
            "request_completed",
            extra={
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 3),
            },
        )
        return response
