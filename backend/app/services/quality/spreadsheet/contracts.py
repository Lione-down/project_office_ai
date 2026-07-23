from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SpreadsheetQualityConflict(StrictModel):
    kind: Literal["sheet", "field", "unit"]
    code: SafeCode
    resolved: bool


class SpreadsheetQualityFinding(StrictModel):
    code: SafeCode
    severity: Literal["warning", "blocker"]
    rule_version: Annotated[str, Field(min_length=1, max_length=64)]


class SpreadsheetSourceReference(StrictModel):
    asset_id: UUID
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=200 * 1024 * 1024)]
    plan_sha256: Sha256
    renderer_version: Literal["excel-renderer.v1"]
    template_code: Literal[
        "excel.analysis-dashboard.v1",
        "excel.operating-review.v1",
    ]
    template_version: Literal["1.0.0"]


class SpreadsheetValidationReference(StrictModel):
    status: Literal["passed", "failed"]
    sha256: Sha256 | None = None
    byte_size: Annotated[int, Field(gt=0, le=200 * 1024 * 1024)] | None = None
    report_sha256: Sha256 | None = None
    libreoffice_version: Annotated[str, Field(min_length=1, max_length=64)] | None = (
        None
    )
    formula_count: Annotated[int, Field(ge=0, le=200_000)] | None = None
    difference_count: Annotated[int, Field(ge=0, le=200_000)] | None = None
    error_code: SafeCode | None = None

    @model_validator(mode="after")
    def status_matches_fields(self):
        passed_fields = (
            self.sha256,
            self.byte_size,
            self.report_sha256,
            self.libreoffice_version,
            self.formula_count,
            self.difference_count,
        )
        if self.status == "passed":
            if (
                any(value is None for value in passed_fields)
                or self.error_code is not None
            ):
                raise ValueError("passed validation requires complete artifacts")
        elif (
            any(value is not None for value in passed_fields) or self.error_code is None
        ):
            raise ValueError("failed validation only exposes a stable error code")
        return self


class SpreadsheetQualityReport(StrictModel):
    schema_version: Literal["workbook-quality-report.v1"]
    quality_engine_version: Literal["spreadsheet-quality.v1"]
    source: SpreadsheetSourceReference
    validation: SpreadsheetValidationReference
    status: Literal["passed", "passed_with_warnings", "blocked"]
    download_allowed: bool
    findings: Annotated[tuple[SpreadsheetQualityFinding, ...], Field(max_length=256)]
    generated_at: datetime

    @model_validator(mode="after")
    def status_matches_findings(self):
        has_blocker = any(item.severity == "blocker" for item in self.findings)
        has_warning = any(item.severity == "warning" for item in self.findings)
        expected = (
            "blocked"
            if has_blocker or self.validation.status == "failed"
            else "passed_with_warnings"
            if has_warning
            else "passed"
        )
        if self.status != expected or self.download_allowed != (expected != "blocked"):
            raise ValueError("quality status does not match findings")
        return self
