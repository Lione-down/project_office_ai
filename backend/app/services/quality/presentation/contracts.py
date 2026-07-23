from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
StableCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")]
StableVersion = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
ReferenceId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PresentationOutputReference(StrictModel):
    asset_id: UUID
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=100 * 1024 * 1024)]
    slide_count: Annotated[int, Field(ge=1, le=30)]
    renderer_version: StableVersion
    template_code: StableVersion
    template_version: StableVersion
    plan_sha256: Sha256


class PresentationValidatedOutputReference(StrictModel):
    asset_id: UUID
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=100 * 1024 * 1024)]


class PresentationQualityFinding(StrictModel):
    code: StableCode
    severity: Literal["warning", "blocker"]
    rule_version: StableVersion
    slide_number: Annotated[int, Field(ge=1, le=30)] | None = None
    shape_id: ReferenceId | None = None
    evidence_ids: Annotated[list[ReferenceId], Field(max_length=100)] = Field(
        default_factory=list
    )
    repairable: bool


class LibreOfficeVerification(StrictModel):
    status: Literal["passed", "failed", "unavailable"]
    version: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    pdf_sha256: Sha256 | None = None
    pdf_byte_size: Annotated[int, Field(gt=0, le=100 * 1024 * 1024)] | None = None
    page_count: Annotated[int, Field(ge=1, le=30)] | None = None
    error_code: StableCode | None = None

    @model_validator(mode="after")
    def fields_match_status(self):
        output_fields = (
            self.version,
            self.pdf_sha256,
            self.pdf_byte_size,
            self.page_count,
        )
        if self.status == "passed":
            if any(value is None for value in output_fields) or self.error_code:
                raise ValueError("passed LibreOffice result is incomplete")
        elif (
            any(value is not None for value in output_fields) or self.error_code is None
        ):
            raise ValueError("failed LibreOffice result must contain only error_code")
        return self


class PresentationPreviewReference(StrictModel):
    page_number: Annotated[int, Field(ge=1, le=30)]
    sha256: Sha256
    byte_size: Annotated[int, Field(gt=0, le=20 * 1024 * 1024)]
    width: Annotated[int, Field(ge=1, le=4096)]
    height: Annotated[int, Field(ge=1, le=4096)]


class PresentationQualityReport(StrictModel):
    schema_version: Literal["presentation-quality-report.v1"]
    quality_engine_version: Literal["presentation-quality.v1"]
    source: PresentationOutputReference
    validated_output: PresentationValidatedOutputReference
    status: Literal["passed", "passed_with_warnings", "blocked"]
    download_allowed: bool
    findings: Annotated[list[PresentationQualityFinding], Field(max_length=500)]
    libreoffice: LibreOfficeVerification
    previews: Annotated[list[PresentationPreviewReference], Field(max_length=30)]
    repair_attempt_count: Annotated[int, Field(ge=0, le=1)]
    repaired_output_sha256: Sha256 | None = None
    generated_at: datetime

    @model_validator(mode="after")
    def result_is_coherent(self):
        blockers = [item for item in self.findings if item.severity == "blocker"]
        warnings = [item for item in self.findings if item.severity == "warning"]
        if self.status == "blocked":
            if self.download_allowed or not blockers:
                raise ValueError("blocked report requires blocker and denies download")
        elif not self.download_allowed:
            raise ValueError("download must be allowed for non-blocked report")
        elif blockers:
            raise ValueError("downloadable report cannot contain blocker")
        elif self.libreoffice.status != "passed":
            raise ValueError("downloadable report requires LibreOffice pass")
        elif self.status == "passed" and warnings:
            raise ValueError("passed report cannot contain warnings")
        elif self.status == "passed_with_warnings" and not warnings:
            raise ValueError("passed_with_warnings requires a warning")
        if self.libreoffice.status == "passed":
            expected_pages = list(range(1, self.libreoffice.page_count + 1))
            actual_pages = [preview.page_number for preview in self.previews]
            if actual_pages != expected_pages:
                raise ValueError("preview pages must match LibreOffice PDF")
        elif self.previews:
            raise ValueError("failed LibreOffice result cannot contain previews")
        if (self.repair_attempt_count == 0) != (self.repaired_output_sha256 is None):
            raise ValueError("repair output requires exactly one repair attempt")
        if self.validated_output.asset_id != self.source.asset_id:
            raise ValueError("validated output must belong to source asset")
        if self.repair_attempt_count == 0 and (
            self.validated_output.sha256 != self.source.sha256
            or self.validated_output.byte_size != self.source.byte_size
        ):
            raise ValueError("unrepaired validated output must match source")
        if (
            self.repair_attempt_count == 1
            and self.validated_output.sha256 != self.repaired_output_sha256
        ):
            raise ValueError("repaired validated output hash must match repair")
        return self
