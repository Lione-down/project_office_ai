from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Sha256 = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoldenManifestError(ValueError):
    pass


class GoldenRegressionError(RuntimeError):
    pass


class Coverage(StrictModel):
    available_cases: Literal[1]
    planned_cases: Literal[10]
    label: Literal["1/10 pilot"]


class Authorization(StrictModel):
    confirmed: Literal[True]
    confirmed_on: date
    scope: Literal["local_deidentified_derivative"]


class Deidentification(StrictModel):
    schema_version: Literal["golden-deidentification.v1"]
    method: Literal["deterministic_alias_and_safe_regeneration"]
    changed_cell_count: int = Field(ge=1)
    salesperson_alias_count: int = Field(ge=0)
    customer_alias_count: int = Field(ge=0)
    terminal_alias_count: int = Field(ge=0)
    address_alias_count: int = Field(ge=0)
    phone_alias_count: int = Field(ge=0)
    email_alias_count: int = Field(ge=0)
    removed_blank_sheet_count: Literal[1]
    fixed_formula_cell_count: Literal[2]
    normalized_metric_sheet_count: Literal[1]
    author_metadata_removed: Literal[True]
    external_relationships_removed: Literal[True]
    private_reference_regenerated: Literal[True]


class Repetitions(StrictModel):
    presentation: int = Field(ge=20, le=100)
    spreadsheet: int = Field(ge=20, le=100)


class PrivateSource(StrictModel):
    role: Literal["source_workbook", "reference_presentation"]
    sha256: Sha256 = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(gt=0)
    reference_slide_count: int | None = Field(default=None, gt=0)


class Artifact(StrictModel):
    path: str = Field(min_length=1, max_length=300)
    sha256: Sha256 = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(gt=0)
    sheet_count: int | None = Field(default=None, gt=0)
    slide_count: int | None = Field(default=None, gt=0)


class ExpectedMetric(StrictModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: float
    tolerance: float = Field(ge=0, le=1)
    source: Literal["system_derived_from_authorized_source"]
    source_sheet_index: int = Field(ge=1, le=30)
    source_range: str = Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]*:[A-Z]{1,3}[1-9][0-9]*$")
    aggregation: Literal[
        "sum",
        "max",
        "ratio_of_sums",
        "growth_of_sums",
    ]
    evidence_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Requirements(StrictModel):
    presentation_page_range: tuple[int, int]
    workbook_sheet_range: tuple[int, int]
    presentation_citations_required: Literal[True]
    workbook_chart_count: int = Field(ge=1)

    @model_validator(mode="after")
    def ranges_are_ordered(self):
        if self.presentation_page_range[0] > self.presentation_page_range[1]:
            raise ValueError("presentation page range invalid")
        if self.workbook_sheet_range[0] > self.workbook_sheet_range[1]:
            raise ValueError("workbook sheet range invalid")
        return self


class GoldenCaseManifest(StrictModel):
    schema_version: Literal["golden-case-manifest.v1"]
    case_id: Literal["sales-pilot-v1"]
    coverage: Coverage
    authorization: Authorization
    deidentification: Deidentification
    repetitions: Repetitions
    private_sources: tuple[PrivateSource, ...] = Field(min_length=2)
    input_workbook: Artifact
    expected_presentation: Artifact
    expected_workbook: Artifact
    presentation_plan: Artifact
    workbook_plan: Artifact
    expected_metrics: tuple[ExpectedMetric, ...] = Field(min_length=1)
    expected_evidence_ids: tuple[str, ...] = Field(min_length=1)
    requirements: Requirements

    @property
    def artifacts(self) -> tuple[Artifact, ...]:
        return (
            self.input_workbook,
            self.expected_presentation,
            self.expected_workbook,
        )

    @property
    def tracked_files(self) -> tuple[Artifact, ...]:
        return (*self.artifacts, self.presentation_plan, self.workbook_plan)


class OfficeArtifactInspection(StrictModel):
    is_safe: bool
    potential_pii_count: int
    external_relationship_count: int
    macro_payload_count: int
    embedded_object_count: int
    author_metadata_present: bool


class GoldenRegressionReport(StrictModel):
    schema_version: Literal["golden-regression-report.v1"]
    case_id: str
    coverage_label: Literal["1/10 pilot"]
    status: Literal["passed", "blocked"]
    spreadsheet_generation_runs: int
    presentation_reference_runs: int
    presentation_generation_runs: int
    presentation_generation_evidence: Literal["ppt_renderer_suite_required"]
    findings: tuple[str, ...]
