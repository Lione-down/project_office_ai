import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.auth_registration import AuthOperationError
from app.services.asset_contracts import AssetOperationError
from app.services.briefs.service import BriefOperationError
from app.services.generation_contracts import GenerationOperationError
from app.services.rate_limit import RateLimitExceeded
from app.services.provider_admin import ProviderOperationError
from app.services.provider_security import ProviderConfigurationError
from app.services.terminology.service import TerminologyOperationError


_error_logger = logging.getLogger("office_ai.error")


def log_asset_recovery_failure(
    request: Request, exception: BaseException, error_code: str
) -> None:
    cleanup_failed = bool(
        getattr(exception, "quarantine_cleanup_failed", False)
        or error_code == "quarantine_cleanup_failed"
    )
    reconciliation_failed = bool(getattr(exception, "recovery_failure", False))
    if not cleanup_failed and not reconciliation_failed:
        return
    _error_logger.error(
        "asset_recovery_failed",
        extra={
            "trace_id": request.state.trace_id,
            "error_code": error_code,
            "cleanup_failed": cleanup_failed,
            "checkpoint_reconciliation_failed": reconciliation_failed,
        },
    )


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


async def handle_unexpected_error(
    request: Request, exception: Exception
) -> JSONResponse:
    log_asset_recovery_failure(request, exception, "internal_error")
    return _error_response(request, 500, "internal_error", "服务内部错误")


async def handle_auth_operation_error(
    request: Request, exception: AuthOperationError | RateLimitExceeded
) -> JSONResponse:
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


async def handle_provider_operation_error(
    request: Request, exception: ProviderOperationError
) -> JSONResponse:
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


async def handle_asset_operation_error(
    request: Request, exception: AssetOperationError
) -> JSONResponse:
    log_asset_recovery_failure(request, exception, exception.error_code)
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


async def handle_terminology_operation_error(
    request: Request, exception: TerminologyOperationError
) -> JSONResponse:
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


async def handle_brief_operation_error(
    request: Request, exception: BriefOperationError
) -> JSONResponse:
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


async def handle_generation_operation_error(
    request: Request, exception: GenerationOperationError
) -> JSONResponse:
    return _error_response(
        request, exception.status_code, exception.error_code, exception.message
    )


async def handle_provider_configuration_error(
    request: Request, exception: ProviderConfigurationError
) -> JSONResponse:
    return _error_response(request, 503, exception.error_code, exception.message)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(AuthOperationError, handle_auth_operation_error)
    app.add_exception_handler(RateLimitExceeded, handle_auth_operation_error)
    app.add_exception_handler(ProviderOperationError, handle_provider_operation_error)
    app.add_exception_handler(AssetOperationError, handle_asset_operation_error)
    app.add_exception_handler(
        TerminologyOperationError, handle_terminology_operation_error
    )
    app.add_exception_handler(BriefOperationError, handle_brief_operation_error)
    app.add_exception_handler(
        GenerationOperationError, handle_generation_operation_error
    )
    app.add_exception_handler(
        ProviderConfigurationError, handle_provider_configuration_error
    )
    app.add_exception_handler(Exception, handle_unexpected_error)
