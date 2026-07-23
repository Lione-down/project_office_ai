import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.quality.presentation.libreoffice import (
    LibreOfficeError,
    LibreOfficeRequest,
    LibreOfficeResponse,
    LibreOfficeRunner,
)
from app.services.renderers.excel.libreoffice import WorkbookValidationError
from app.services.renderers.excel.sidecar import (
    SpreadsheetLibreOfficeRunner,
    SpreadsheetRecalculationRequest,
    SpreadsheetRecalculationResponse,
)


MAX_REQUEST_BYTES = 4096


def create_libreoffice_app(runner=None, spreadsheet_runner=None) -> FastAPI:
    application = FastAPI(
        title="Office AI LibreOffice Quality Sidecar",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.runner = runner or LibreOfficeRunner(
        Path(os.environ.get("OFFICE_AI_FILES_ROOT", "/app/files")),
        Path(os.environ.get("OFFICE_AI_QUALITY_WORK_ROOT", "/app/work")),
        timeout_seconds=float(
            os.environ.get("OFFICE_AI_LIBREOFFICE_TIMEOUT_SECONDS", "120")
        ),
    )
    application.state.spreadsheet_runner = (
        spreadsheet_runner
        or SpreadsheetLibreOfficeRunner(
            Path(os.environ.get("OFFICE_AI_FILES_ROOT", "/app/files")),
            Path(os.environ.get("OFFICE_AI_QUALITY_WORK_ROOT", "/app/work")),
            timeout_seconds=float(
                os.environ.get(
                    "OFFICE_AI_LIBREOFFICE_TIMEOUT_SECONDS",
                    "120",
                )
            ),
        )
    )

    @application.middleware("http")
    async def bound_request_body(request: Request, call_next):
        if request.url.path in {
            "/v1/presentation/convert",
            "/v1/spreadsheet/recalculate",
        }:
            raw_length = request.headers.get("content-length")
            try:
                content_length = int(raw_length or "")
            except ValueError:
                content_length = -1
            if not 0 < content_length <= MAX_REQUEST_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "libreoffice_request_invalid",
                            "retryable": False,
                        }
                    },
                )
        return await call_next(request)

    @application.exception_handler(LibreOfficeError)
    async def handle_libreoffice_error(_request: Request, exception: LibreOfficeError):
        return JSONResponse(
            status_code=503 if exception.retryable else 422,
            content={
                "error": {
                    "code": exception.error_code,
                    "retryable": exception.retryable,
                }
            },
        )

    @application.exception_handler(WorkbookValidationError)
    async def handle_workbook_validation_error(
        _request: Request,
        exception: WorkbookValidationError,
    ):
        retryable = exception.error_code in {
            "libreoffice_timeout",
            "libreoffice_unavailable",
        }
        return JSONResponse(
            status_code=503 if retryable else 422,
            content={
                "error": {
                    "code": exception.error_code,
                    "retryable": retryable,
                }
            },
        )

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "live"}

    @application.post(
        "/v1/presentation/convert",
        response_model=LibreOfficeResponse,
    )
    def convert(payload: LibreOfficeRequest) -> LibreOfficeResponse:
        return application.state.runner.convert(payload)

    @application.post(
        "/v1/spreadsheet/recalculate",
        response_model=SpreadsheetRecalculationResponse,
    )
    def recalculate(
        payload: SpreadsheetRecalculationRequest,
    ) -> SpreadsheetRecalculationResponse:
        return application.state.spreadsheet_runner.recalculate(payload)

    return application


app = create_libreoffice_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
