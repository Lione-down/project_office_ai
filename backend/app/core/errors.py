from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.auth_registration import AuthOperationError
from app.services.rate_limit import RateLimitExceeded


def _error_response(
    request: Request, status_code: int, error_code: str, message: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "error_code": error_code,
                "message": message,
                "trace_id": request.state.trace_id,
            }
        },
    )


async def handle_http_exception(
    request: Request, exception: HTTPException
) -> JSONResponse:
    if exception.status_code == 404:
        return _error_response(request, 404, "not_found", "请求的资源不存在")
    return _error_response(request, exception.status_code, "http_error", "请求处理失败")


async def handle_validation_error(
    request: Request, _: RequestValidationError
) -> JSONResponse:
    return _error_response(request, 422, "validation_error", "请求参数无效")


async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
    return _error_response(request, 500, "internal_error", "服务内部错误")


async def handle_auth_operation_error(
    request: Request, exception: AuthOperationError | RateLimitExceeded
) -> JSONResponse:
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(AuthOperationError, handle_auth_operation_error)
    app.add_exception_handler(RateLimitExceeded, handle_auth_operation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
