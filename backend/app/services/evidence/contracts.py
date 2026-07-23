from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)


class EvidenceProcessingError(Exception):
    def __init__(self, error_code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.error_code = error_code
        self.safe_message = safe_message


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class EngineVersion(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)


class ExcelCellLocation(StrictModel):
    kind: Literal["excel_cell"]
    sheet: str = Field(min_length=1, max_length=255)
    cell: str = Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")


class PdfRegionLocation(StrictModel):
    kind: Literal["pdf_region"]
    page: int = Field(ge=1, le=200)
    bbox: tuple[float, float, float, float]


class WordParagraphLocation(StrictModel):
    kind: Literal["word_paragraph"]
    paragraph: int = Field(ge=1)


class ImageOcrLocation(StrictModel):
    kind: Literal["image_ocr"]
    bbox: tuple[float, float, float, float]


class TextLineLocation(StrictModel):
    kind: Literal["text_line"]
    line: int = Field(ge=1)


class CsvCellLocation(StrictModel):
    kind: Literal["csv_cell"]
    row: int = Field(ge=1)
    column: int = Field(ge=1)


EvidenceLocation = Annotated[
    ExcelCellLocation
    | PdfRegionLocation
    | WordParagraphLocation
    | ImageOcrLocation
    | TextLineLocation
    | CsvCellLocation,
    Field(discriminator="kind"),
]
EvidenceLocationAdapter = TypeAdapter(EvidenceLocation)


class ManifestIssue(StrictModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    evidence_id: str = Field(pattern=r"^e-[a-f0-9]{64}$")


class EvidenceItem(StrictModel):
    evidence_id: str = Field(pattern=r"^e-[a-f0-9]{64}$")
    evidence_type: Literal["source_fact", "calculated_fact", "ai_inference"]
    asset_id: UUID
    asset_version: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    location: EvidenceLocation
    raw_value: str = Field(min_length=1, max_length=16_384)
    normalized_value: str | None = Field(default=None, max_length=16_384)
    value_kind: Literal["narrative", "number"]
    unit: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, max_length=3)
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    parser_name: str = Field(min_length=1, max_length=64)
    parser_version: str = Field(min_length=1, max_length=32)
    ocr_engine_name: str | None = Field(default=None, max_length=64)
    ocr_engine_version: str | None = Field(default=None, max_length=32)
    warnings: tuple[str, ...] = ()
    calculation_blocked: bool = False
    calculation_expression: str | None = Field(default=None, max_length=2048)
    inference_model: EngineVersion | None = None

    @model_validator(mode="after")
    def require_type_provenance(self):
        if self.evidence_type == "source_fact":
            if (
                self.calculation_expression is not None
                or self.inference_model is not None
            ):
                raise ValueError("source facts cannot contain derived provenance")
        elif self.evidence_type == "calculated_fact":
            if not self.calculation_expression or self.inference_model is not None:
                raise ValueError("calculated facts require a calculation expression")
        elif self.inference_model is None or self.calculation_expression is not None:
            raise ValueError("AI inference requires explicit model provenance")
        return self


class EvidenceManifest(StrictModel):
    schema_version: Literal["evidence-manifest.v1"]
    manifest_id: str = Field(pattern=r"^m-[a-f0-9]{64}$")
    asset_id: UUID
    asset_version: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    generated_at: datetime
    generator: EngineVersion
    source_parser: EngineVersion
    ocr_engine: EngineVersion | None = None
    evidence: tuple[EvidenceItem, ...]
    warnings: tuple[ManifestIssue, ...] = ()
    blockers: tuple[ManifestIssue, ...] = ()

    @field_validator("generated_at")
    @classmethod
    def generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value

    @model_validator(mode="after")
    def manifest_links_must_be_consistent(self):
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence IDs must be unique")
        if any(
            item.asset_id != self.asset_id or item.asset_version != self.asset_version
            for item in self.evidence
        ):
            raise ValueError("evidence must link to the manifest asset version")
        known_ids = set(evidence_ids)
        if any(
            issue.evidence_id not in known_ids
            for issue in (*self.warnings, *self.blockers)
        ):
            raise ValueError("manifest issues must reference existing evidence")
        return self
