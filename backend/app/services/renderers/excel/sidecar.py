from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.renderers.excel.libreoffice import (
    LibreOfficeWorkbookValidator,
    WorkbookValidationError,
    WorkbookValidationReport,
)
from app.services.renderers.excel.renderer import RenderedWorkbook


Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
MAX_WORKBOOK_BYTES = 200 * 1024 * 1024
MAX_REPORT_BYTES = 10 * 1024 * 1024


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SpreadsheetRecalculationRequest(StrictModel):
    schema_version: Literal["libreoffice-spreadsheet-request.v1"]
    request_id: Annotated[UUID, Field(strict=False)]
    user_id: Annotated[UUID, Field(strict=False)]
    asset_id: Annotated[UUID, Field(strict=False)]
    source_sha256: Sha256
    source_byte_size: Annotated[int, Field(gt=0, le=MAX_WORKBOOK_BYTES)]
    plan_sha256: Sha256
    renderer_version: Literal["excel-renderer.v1"]
    template_code: Literal[
        "excel.analysis-dashboard.v1",
        "excel.operating-review.v1",
    ]
    template_version: Literal["1.0.0"]


class SpreadsheetArtifactDescriptor(StrictModel):
    key: Annotated[str, Field(min_length=1, max_length=768)]
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=MAX_WORKBOOK_BYTES)]


class SpreadsheetRecalculationResponse(StrictModel):
    schema_version: Literal["libreoffice-spreadsheet-response.v1"]
    request_id: Annotated[UUID, Field(strict=False)]
    status: Literal["succeeded"]
    source_sha256: Sha256
    plan_sha256: Sha256
    renderer_version: Literal["excel-renderer.v1"]
    template_code: Literal[
        "excel.analysis-dashboard.v1",
        "excel.operating-review.v1",
    ]
    template_version: Literal["1.0.0"]
    libreoffice_version: Annotated[str, Field(min_length=1, max_length=64)]
    formula_count: Annotated[int, Field(ge=0, le=200_000)]
    difference_count: Annotated[int, Field(ge=0, le=200_000)]
    validation_copy: SpreadsheetArtifactDescriptor
    validation_report: SpreadsheetArtifactDescriptor


@dataclass(frozen=True)
class VerifiedSpreadsheetArtifact:
    path: Path
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class VerifiedSpreadsheetValidation:
    validation_copy: VerifiedSpreadsheetArtifact
    report_artifact: VerifiedSpreadsheetArtifact
    report: WorkbookValidationReport


class SpreadsheetLibreOfficeRunner:
    def __init__(
        self,
        files_root: str | Path,
        work_root: str | Path,
        *,
        timeout_seconds: float = 120,
        validator_factory: Callable[[Path], LibreOfficeWorkbookValidator] | None = None,
    ) -> None:
        self._files_root = Path(files_root).resolve()
        self._work_root = Path(work_root).resolve()
        self._validator_factory = validator_factory or (
            lambda root: LibreOfficeWorkbookValidator(
                root,
                timeout_seconds=timeout_seconds,
            )
        )

    def recalculate(
        self,
        request: SpreadsheetRecalculationRequest,
    ) -> SpreadsheetRecalculationResponse:
        source = self._source_path(request.user_id, request.asset_id)
        source_digest, source_size = _digest(source, MAX_WORKBOOK_BYTES)
        if (
            source_digest != request.source_sha256
            or source_size != request.source_byte_size
        ):
            raise WorkbookValidationError("workbook_original_integrity_failed")
        rendered = RenderedWorkbook(
            path=source,
            sha256=source_digest,
            byte_size=source_size,
            plan_sha256=request.plan_sha256,
            schema_version="workbook-plan.v1",
            renderer_version=request.renderer_version,
            template_code=request.template_code,
            template_version=request.template_version,
            sheet_count=0,
            generated_cell_count=0,
        )
        validation_root = self._work_root / "spreadsheet" / str(request.request_id)
        artifacts = self._validator_factory(validation_root).validate(rendered)
        validation = self._artifact_descriptor(
            artifacts.validation_copy_path,
            MAX_WORKBOOK_BYTES,
        )
        report = self._artifact_descriptor(
            artifacts.report_path,
            MAX_REPORT_BYTES,
        )
        return SpreadsheetRecalculationResponse(
            schema_version="libreoffice-spreadsheet-response.v1",
            request_id=request.request_id,
            status="succeeded",
            source_sha256=source_digest,
            plan_sha256=request.plan_sha256,
            renderer_version=request.renderer_version,
            template_code=request.template_code,
            template_version=request.template_version,
            libreoffice_version=artifacts.report.libreoffice_version,
            formula_count=artifacts.report.formula_count,
            difference_count=artifacts.report.difference_count,
            validation_copy=validation,
            validation_report=report,
        )

    def _source_path(self, user_id: UUID, asset_id: UUID) -> Path:
        path = self._files_root.joinpath(
            "users",
            str(user_id),
            "outputs",
            str(asset_id),
            "analysis.xlsx",
        ).resolve()
        if not path.is_relative_to(self._files_root) or not path.is_file():
            raise WorkbookValidationError("workbook_file_missing")
        return path

    def _artifact_descriptor(
        self,
        path: Path,
        maximum: int,
    ) -> SpreadsheetArtifactDescriptor:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._work_root):
            raise WorkbookValidationError("workbook_validation_key_invalid")
        digest, byte_size = _digest(resolved, maximum)
        return SpreadsheetArtifactDescriptor(
            key=resolved.relative_to(self._work_root).as_posix(),
            sha256=digest,
            byte_size=byte_size,
        )


class SpreadsheetLibreOfficeClient:
    def __init__(
        self,
        base_url: str,
        work_root: str | Path,
        *,
        timeout_seconds: float = 120,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("LibreOffice base URL is invalid")
        self._base_url = base_url.rstrip("/")
        self._work_root = Path(work_root).resolve()
        self._timeout = timeout_seconds
        self._transport = transport

    async def recalculate(
        self,
        *,
        request_id: UUID,
        user_id: UUID,
        asset_id: UUID,
        source_sha256: str,
        source_byte_size: int,
        plan_sha256: str,
        renderer_version: str,
        template_code: str,
        template_version: str,
    ) -> VerifiedSpreadsheetValidation:
        request = SpreadsheetRecalculationRequest(
            schema_version="libreoffice-spreadsheet-request.v1",
            request_id=request_id,
            user_id=user_id,
            asset_id=asset_id,
            source_sha256=source_sha256,
            source_byte_size=source_byte_size,
            plan_sha256=plan_sha256,
            renderer_version=renderer_version,
            template_code=template_code,
            template_version=template_version,
        )
        response = await self._request(request)
        self._verify_trace(request, response)
        validation = self._resolve_artifact(
            request,
            response.validation_copy,
            ("recalculated", "analysis.xlsx"),
            MAX_WORKBOOK_BYTES,
        )
        report_artifact = self._resolve_artifact(
            request,
            response.validation_report,
            ("validation-report.json",),
            MAX_REPORT_BYTES,
        )
        try:
            report = WorkbookValidationReport.model_validate_json(
                report_artifact.path.read_bytes()
            )
        except (OSError, ValidationError, ValueError) as exception:
            raise WorkbookValidationError("libreoffice_response_invalid") from exception
        if (
            report.original_sha256 != request.source_sha256
            or report.validation_sha256 != validation.sha256
            or report.plan_sha256 != request.plan_sha256
            or report.renderer_version != request.renderer_version
            or report.template_code != request.template_code
            or report.template_version != request.template_version
            or report.formula_count != response.formula_count
            or report.difference_count != response.difference_count
            or report.libreoffice_version != response.libreoffice_version
        ):
            raise WorkbookValidationError("libreoffice_response_invalid")
        return VerifiedSpreadsheetValidation(
            validation_copy=validation,
            report_artifact=report_artifact,
            report=report,
        )

    async def _request(
        self,
        request: SpreadsheetRecalculationRequest,
    ) -> SpreadsheetRecalculationResponse:
        content = json.dumps(
            request.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                async with client.stream(
                    "POST",
                    "/v1/spreadsheet/recalculate",
                    content=content,
                    headers={"Content-Type": "application/json"},
                ) as result:
                    status_code = result.status_code
                    content_type = result.headers.get("content-type", "")
                    response_bytes = bytearray()
                    async for chunk in result.aiter_bytes():
                        response_bytes.extend(chunk)
                        if len(response_bytes) > 64 * 1024:
                            raise WorkbookValidationError(
                                "libreoffice_response_invalid"
                            )
            except httpx.HTTPError as exception:
                raise WorkbookValidationError("libreoffice_unavailable") from exception
        if content_type.split(";")[0].strip() != "application/json":
            raise WorkbookValidationError("libreoffice_response_invalid")
        try:
            body = json.loads(response_bytes)
        except (UnicodeDecodeError, ValueError) as exception:
            raise WorkbookValidationError("libreoffice_response_invalid") from exception
        if status_code != 200:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            code = error.get("code")
            if not isinstance(code, str) or len(code) > 64:
                code = "libreoffice_response_invalid"
            raise WorkbookValidationError(code)
        try:
            return SpreadsheetRecalculationResponse.model_validate(body)
        except ValidationError as exception:
            raise WorkbookValidationError("libreoffice_response_invalid") from exception

    @staticmethod
    def _verify_trace(
        request: SpreadsheetRecalculationRequest,
        response: SpreadsheetRecalculationResponse,
    ) -> None:
        if (
            response.request_id != request.request_id
            or response.source_sha256 != request.source_sha256
            or response.plan_sha256 != request.plan_sha256
            or response.renderer_version != request.renderer_version
            or response.template_code != request.template_code
            or response.template_version != request.template_version
        ):
            raise WorkbookValidationError("libreoffice_response_invalid")

    def _resolve_artifact(
        self,
        request: SpreadsheetRecalculationRequest,
        descriptor: SpreadsheetArtifactDescriptor,
        suffix: tuple[str, ...],
        maximum: int,
    ) -> VerifiedSpreadsheetArtifact:
        key = PurePosixPath(descriptor.key)
        expected = (
            "spreadsheet",
            str(request.request_id),
            request.source_sha256,
            *suffix,
        )
        if key.is_absolute() or key.parts != expected:
            raise WorkbookValidationError("libreoffice_response_invalid")
        path = self._work_root.joinpath(*key.parts).resolve()
        if not path.is_relative_to(self._work_root):
            raise WorkbookValidationError("libreoffice_response_invalid")
        digest, byte_size = _digest(path, maximum)
        if digest != descriptor.sha256 or byte_size != descriptor.byte_size:
            raise WorkbookValidationError("libreoffice_response_invalid")
        return VerifiedSpreadsheetArtifact(path, digest, byte_size)


def _digest(path: Path, maximum: int) -> tuple[str, int]:
    if not path.is_file():
        raise WorkbookValidationError("workbook_file_missing")
    digest = sha256()
    byte_size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            byte_size += len(chunk)
            if byte_size > maximum:
                raise WorkbookValidationError("workbook_file_too_large")
            digest.update(chunk)
    return digest.hexdigest(), byte_size
