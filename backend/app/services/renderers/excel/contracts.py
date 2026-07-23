from hashlib import sha256
import json
import math
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


ReferenceId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=500)]
ColumnKey = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
CellValue = str | int | float | bool | None
SHEET_NAME_PATTERN = re.compile(r"^[^\\/*?:\[\]]{1,31}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class WorkbookContractError(ValueError):
    def __init__(self, error_code: str = "workbook_plan_invalid") -> None:
        super().__init__(error_code)
        self.error_code = error_code


class TemplateRef(StrictModel):
    code: Literal[
        "excel.analysis-dashboard.v1",
        "excel.operating-review.v1",
    ]
    version: Literal["1.0.0"]


class WorkbookMetadata(StrictModel):
    title: ShortText
    subject: ShortText
    author: ShortText
    company: ShortText
    revision: Annotated[str, Field(pattern=r"^[0-9]{1,9}$")]


class FreezePanes(StrictModel):
    row: Annotated[int, Field(ge=0, le=1_048_575)]
    column: Annotated[int, Field(ge=0, le=16_383)]


class PrintSettings(StrictModel):
    orientation: Literal["portrait", "landscape"]
    fit_width: Annotated[int, Field(ge=0, le=100)]
    fit_height: Annotated[int, Field(ge=0, le=100)]
    repeat_header: bool


class DataColumn(StrictModel):
    key: ColumnKey
    header: ShortText
    value_type: Literal["text", "number", "integer", "boolean"]


class ComparisonCalculation(StrictModel):
    kind: Literal["yoy", "mom"]
    current_column: ColumnKey
    previous_column: ColumnKey


class RankCalculation(StrictModel):
    kind: Literal["rank"]
    source_column: ColumnKey
    order: Literal["ascending", "descending"]


ComputedCalculation = Annotated[
    ComparisonCalculation | RankCalculation,
    Field(discriminator="kind"),
]


class ComputedColumn(StrictModel):
    key: ColumnKey
    header: ShortText
    value_type: Literal["percent", "integer"]
    calculation: ComputedCalculation

    @model_validator(mode="after")
    def calculation_matches_type(self):
        if isinstance(self.calculation, ComparisonCalculation):
            if self.value_type != "percent":
                raise ValueError("comparison columns must be percentages")
        elif self.value_type != "integer":
            raise ValueError("rank columns must be integers")
        return self


class ConditionalFormat(StrictModel):
    target_column: ColumnKey
    kind: Literal["cell", "data_bar", "color_scale"]
    operator: (
        Literal[
            "less_than",
            "less_than_or_equal_to",
            "greater_than",
            "greater_than_or_equal_to",
            "equal_to",
            "not_equal_to",
        ]
        | None
    ) = None
    value: Annotated[float, Field(allow_inf_nan=False)] | None = None

    @model_validator(mode="after")
    def cell_rule_is_complete(self):
        if self.kind == "cell" and (self.operator is None or self.value is None):
            raise ValueError("cell conditional format requires operator and value")
        if self.kind != "cell" and (
            self.operator is not None or self.value is not None
        ):
            raise ValueError("non-cell conditional format cannot define a threshold")
        return self


class DataValidation(StrictModel):
    target_column: ColumnKey
    values: Annotated[list[ShortText], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def values_are_unique(self):
        if len(set(self.values)) != len(self.values):
            raise ValueError("validation values must be unique")
        if any("," in value for value in self.values):
            raise ValueError("validation values cannot contain commas")
        if sum(len(value) for value in self.values) + len(self.values) - 1 > 255:
            raise ValueError("inline validation list exceeds Excel limit")
        return self


class DataSheet(StrictModel):
    kind: Literal["data"]
    name: ShortText
    title: ShortText
    columns: Annotated[list[DataColumn], Field(min_length=1, max_length=50)]
    computed_columns: Annotated[list[ComputedColumn], Field(max_length=20)]
    rows: Annotated[list[dict[ColumnKey, CellValue]], Field(min_length=1)]
    conditional_formats: Annotated[list[ConditionalFormat], Field(max_length=50)]
    data_validations: Annotated[list[DataValidation], Field(max_length=50)]
    freeze_panes: FreezePanes
    print_settings: PrintSettings

    @model_validator(mode="after")
    def validate_structure(self):
        _validate_sheet_name(self.name)
        raw_columns = {column.key: column for column in self.columns}
        computed_columns = {column.key: column for column in self.computed_columns}
        if len(raw_columns) != len(self.columns):
            raise ValueError("data column keys must be unique")
        if len(computed_columns) != len(self.computed_columns):
            raise ValueError("computed column keys must be unique")
        if set(raw_columns) & set(computed_columns):
            raise ValueError("raw and computed column keys must be unique")
        for row in self.rows:
            if set(row) != set(raw_columns):
                raise ValueError("data row keys must match raw columns")
            for key, value in row.items():
                _validate_cell_value(raw_columns[key], value)
        all_columns = set(raw_columns) | set(computed_columns)
        for column in self.computed_columns:
            calculation = column.calculation
            if isinstance(calculation, ComparisonCalculation):
                references = {
                    calculation.current_column,
                    calculation.previous_column,
                }
            else:
                references = {calculation.source_column}
            if not references.issubset(raw_columns):
                raise ValueError("computed column references must target raw columns")
            if any(
                raw_columns[reference].value_type not in {"number", "integer"}
                for reference in references
            ):
                raise ValueError("computed column references must be numeric")
        if any(
            item.target_column not in all_columns for item in self.conditional_formats
        ):
            raise ValueError("conditional format references an unknown column")
        if any(item.target_column not in raw_columns for item in self.data_validations):
            raise ValueError("data validation references an unknown raw column")
        return self

    @property
    def generated_cell_count(self) -> int:
        column_count = len(self.columns) + len(self.computed_columns)
        return 1 + column_count + len(self.rows) * column_count


class SummaryCalculation(StrictModel):
    kind: Literal["sum", "average", "count"]
    source_sheet: ShortText
    source_column: ColumnKey


class SummaryMetric(StrictModel):
    key: ColumnKey
    label: ShortText
    calculation: SummaryCalculation


class ChartPlan(StrictModel):
    chart_type: Literal["column", "line", "pie"]
    title: ShortText
    source_sheet: ShortText
    categories_column: ColumnKey
    value_columns: Annotated[list[ColumnKey], Field(min_length=1, max_length=10)]
    anchor: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")]

    @model_validator(mode="after")
    def value_columns_are_unique(self):
        if len(set(self.value_columns)) != len(self.value_columns):
            raise ValueError("chart value columns must be unique")
        if not _is_valid_excel_cell_reference(self.anchor):
            raise ValueError("chart anchor exceeds Excel limits")
        return self


class SummarySheet(StrictModel):
    kind: Literal["summary"]
    name: ShortText
    title: ShortText
    metrics: Annotated[list[SummaryMetric], Field(min_length=1, max_length=100)]
    charts: Annotated[list[ChartPlan], Field(max_length=20)]
    freeze_panes: FreezePanes
    print_settings: PrintSettings

    @model_validator(mode="after")
    def validate_structure(self):
        _validate_sheet_name(self.name)
        if len({metric.key for metric in self.metrics}) != len(self.metrics):
            raise ValueError("summary metric keys must be unique")
        return self

    @property
    def generated_cell_count(self) -> int:
        return 1 + 2 + len(self.metrics) * 2


WorkbookSheet = Annotated[
    DataSheet | SummarySheet,
    Field(discriminator="kind"),
]


class WorkbookPlan(StrictModel):
    schema_version: Literal["workbook-plan.v1"]
    renderer_version: Literal["excel-renderer.v1"]
    template: TemplateRef
    locale: Literal["zh-CN"]
    metadata: WorkbookMetadata
    evidence_ids: Annotated[list[ReferenceId], Field(min_length=1, max_length=10_000)]
    sheets: Annotated[list[WorkbookSheet], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def references_exist(self):
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Evidence IDs must be unique")
        names = [sheet.name.casefold() for sheet in self.sheets]
        if len(set(names)) != len(names):
            raise ValueError("Sheet names must be unique")
        data_sheets = {
            sheet.name: sheet for sheet in self.sheets if isinstance(sheet, DataSheet)
        }
        if not data_sheets:
            raise ValueError("at least one data Sheet is required")
        for sheet in self.sheets:
            if not isinstance(sheet, SummarySheet):
                continue
            for metric in sheet.metrics:
                _validate_source_reference(
                    data_sheets,
                    metric.calculation.source_sheet,
                    metric.calculation.source_column,
                    require_numeric=True,
                )
            for chart in sheet.charts:
                source = _validate_source_reference(
                    data_sheets,
                    chart.source_sheet,
                    chart.categories_column,
                    require_numeric=False,
                )
                for value_column in chart.value_columns:
                    _validate_source_reference(
                        data_sheets,
                        chart.source_sheet,
                        value_column,
                        require_numeric=True,
                    )
                if not source.rows:
                    raise ValueError("chart source range is empty")
        enforce_workbook_limits(
            sheet_count=len(self.sheets),
            generated_cell_count=sum(
                sheet.generated_cell_count for sheet in self.sheets
            ),
        )
        return self

    @classmethod
    def validate_for_renderer(cls, value) -> "WorkbookPlan":
        if not isinstance(value, dict):
            raise WorkbookContractError()
        sheets = value.get("sheets")
        if isinstance(sheets, list) and len(sheets) > 20:
            raise WorkbookContractError("workbook_sheet_limit_exceeded")
        try:
            return cls.model_validate(value)
        except ValidationError as exception:
            raise WorkbookContractError() from exception


def enforce_workbook_limits(*, sheet_count: int, generated_cell_count: int) -> None:
    if sheet_count > 20:
        raise WorkbookContractError("workbook_sheet_limit_exceeded")
    if generated_cell_count > 200_000:
        raise WorkbookContractError("workbook_cell_limit_exceeded")


def workbook_plan_json_schema() -> dict:
    schema = WorkbookPlan.model_json_schema()
    schema["$id"] = "https://office-ai.local/schemas/workbook-plan.v1.json"
    return schema


def workbook_plan_sha256(plan: WorkbookPlan) -> str:
    canonical = _canonical_json(plan.model_dump(mode="json", exclude_none=True))
    return sha256(canonical.encode("utf-8")).hexdigest()


def _validate_sheet_name(value: str) -> None:
    if (
        not SHEET_NAME_PATTERN.fullmatch(value)
        or value.startswith("'")
        or value.endswith("'")
    ):
        raise ValueError("invalid Sheet name")


def _validate_cell_value(column: DataColumn, value: CellValue) -> None:
    if isinstance(value, str) and len(value) > 500:
        raise ValueError("cell text is too long")
    if isinstance(value, float) and not _is_deterministic_number(value):
        raise ValueError("cell number is not deterministic")
    expected = {
        "text": lambda item: isinstance(item, str),
        "number": lambda item: (
            isinstance(item, (int, float)) and not isinstance(item, bool)
        ),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
    }
    if value is not None and not expected[column.value_type](value):
        raise ValueError("cell value does not match column type")


def _validate_source_reference(
    data_sheets: dict[str, DataSheet],
    sheet_name: str,
    column_key: str,
    *,
    require_numeric: bool,
) -> DataSheet:
    sheet = data_sheets.get(sheet_name)
    if sheet is None:
        raise ValueError("source Sheet does not exist")
    columns = {
        column.key: column for column in [*sheet.columns, *sheet.computed_columns]
    }
    column = columns.get(column_key)
    if column is None:
        raise ValueError("source column does not exist")
    if require_numeric and column.value_type not in {
        "number",
        "integer",
        "percent",
    }:
        raise ValueError("source column must be numeric")
    return sheet


def _canonical_json(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        fixed = f"{float(value):.6f}".rstrip("0").rstrip(".")
        return "0" if fixed in {"", "-0"} else fixed
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return f"[{','.join(_canonical_json(item) for item in value)}]"
    if isinstance(value, dict):
        members = (
            f"{json.dumps(key, ensure_ascii=False)}:{_canonical_json(value[key])}"
            for key in sorted(value)
        )
        return f"{{{','.join(members)}}}"
    raise TypeError("unsupported canonical JSON value")


def _is_deterministic_number(value: float) -> bool:
    scaled = value * 1_000_000
    return (
        math.isfinite(value)
        and abs(value) <= 1_000_000_000_000
        and abs(scaled - round(scaled)) <= 0.0001
    )


def _is_valid_excel_cell_reference(value: str) -> bool:
    matched = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if matched is None:
        return False
    column_number = 0
    for character in matched.group(1):
        column_number = column_number * 26 + ord(character) - ord("A") + 1
    return column_number <= 16_384 and int(matched.group(2)) <= 1_048_576
