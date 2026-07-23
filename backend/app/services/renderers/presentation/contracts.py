from hashlib import sha256
import json
import math
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


ReferenceId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]
ShortText = Annotated[str, Field(min_length=1, max_length=500)]
Coordinate = Annotated[float, Field(ge=0, le=13.333, allow_inf_nan=False)]
Extent = Annotated[float, Field(gt=0, le=13.333, allow_inf_nan=False)]
EvidenceIds = Annotated[list[ReferenceId], Field(min_length=1, max_length=100)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PresentationContractError(ValueError):
    def __init__(self, error_code: str = "presentation_plan_invalid") -> None:
        super().__init__(error_code)
        self.error_code = error_code


class TemplateRef(StrictModel):
    code: Literal[
        "ppt.executive-blue.v1",
        "ppt.operating-review.v1",
        "ppt.data-story.v1",
    ]
    version: Literal["1.0.0"]


class PresentationMetadata(StrictModel):
    title: ShortText
    subject: ShortText
    author: ShortText
    company: ShortText
    revision: Annotated[str, Field(pattern=r"^[0-9]{1,9}$")]


class ImageData(StrictModel):
    data_uri: Annotated[
        str,
        Field(
            max_length=10 * 1024 * 1024,
            pattern=r"^data:image/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$",
        ),
    ]
    alt_text: ShortText


class ChartSeries(StrictModel):
    name: ShortText
    values: Annotated[list[float], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def values_are_deterministic(self):
        if any(not _is_deterministic_number(value) for value in self.values):
            raise ValueError("chart value precision is unsupported")
        return self


class ChartDataSource(StrictModel):
    kind: Literal["chart"]
    categories: Annotated[list[ShortText], Field(min_length=1, max_length=100)]
    series: Annotated[list[ChartSeries], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def values_match_categories(self):
        if any(len(series.values) != len(self.categories) for series in self.series):
            raise ValueError("chart series length must match categories")
        return self


class TableDataSource(StrictModel):
    kind: Literal["table"]
    columns: Annotated[list[ShortText], Field(min_length=1, max_length=20)]
    rows: Annotated[
        list[list[Annotated[str | float, Field()]]],
        Field(min_length=1, max_length=200),
    ]

    @model_validator(mode="after")
    def rows_match_columns(self):
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("table row length must match columns")
        if any(
            isinstance(value, str) and len(value) > 500
            for row in self.rows
            for value in row
        ):
            raise ValueError("table cell is too long")
        if any(
            isinstance(value, float) and not _is_deterministic_number(value)
            for row in self.rows
            for value in row
        ):
            raise ValueError("table value precision is unsupported")
        return self


class Geometry(StrictModel):
    x: Coordinate
    y: Annotated[float, Field(ge=0, le=7.5, allow_inf_nan=False)]
    w: Extent
    h: Annotated[float, Field(gt=0, le=7.5, allow_inf_nan=False)]

    @model_validator(mode="after")
    def geometry_is_deterministic(self):
        if any(
            not _is_deterministic_number(value)
            for value in (self.x, self.y, self.w, self.h)
        ):
            raise ValueError("geometry precision is unsupported")
        return self


class EvidenceGeometry(Geometry):
    evidence_ids: EvidenceIds


class TextElement(EvidenceGeometry):
    type: Literal["text"]
    text: ShortText


class ImageElement(Geometry):
    type: Literal["image"]
    image_id: ReferenceId
    decorative: Literal[True] | None = None
    evidence_ids: EvidenceIds | None = None

    @model_validator(mode="after")
    def requires_provenance_or_decorative(self):
        if self.decorative is not True and not self.evidence_ids:
            raise ValueError("image requires Evidence IDs or decorative=true")
        return self


class TableElement(EvidenceGeometry):
    type: Literal["table"]
    data_source_id: ReferenceId


class ChartElement(EvidenceGeometry):
    type: Literal["chart"]
    chart_type: Literal["bar", "line", "pie"]
    data_source_id: ReferenceId


class SourceElement(EvidenceGeometry):
    type: Literal["source"]
    text: ShortText


PresentationElement = Annotated[
    TextElement | ImageElement | TableElement | ChartElement | SourceElement,
    Field(discriminator="type"),
]


class PresentationSlide(StrictModel):
    layout: Literal["title", "content", "section", "closing"]
    title: ShortText
    subtitle: ShortText | None = None
    speaker_notes: Annotated[list[ShortText], Field(min_length=1, max_length=20)]
    elements: Annotated[list[PresentationElement], Field(max_length=100)]


class PresentationPlan(StrictModel):
    schema_version: Literal["presentation-plan.v1"]
    renderer_version: Literal["ppt-renderer.v1"]
    template: TemplateRef
    locale: Literal["zh-CN"]
    metadata: PresentationMetadata
    evidence_ids: Annotated[list[ReferenceId], Field(min_length=1, max_length=10_000)]
    images: Annotated[dict[ReferenceId, ImageData], Field(max_length=100)]
    data_sources: Annotated[
        dict[ReferenceId, ChartDataSource | TableDataSource],
        Field(max_length=100),
    ]
    slides: Annotated[list[PresentationSlide], Field(min_length=3, max_length=30)]

    @model_validator(mode="after")
    def references_exist(self):
        evidence = set(self.evidence_ids)
        if len(evidence) != len(self.evidence_ids):
            raise ValueError("Evidence IDs must be unique")
        for slide in self.slides:
            for element in slide.elements:
                if getattr(element, "evidence_ids", None) and not set(
                    element.evidence_ids
                ).issubset(evidence):
                    raise ValueError("element references unknown Evidence")
                if (
                    isinstance(element, ImageElement)
                    and element.image_id not in self.images
                ):
                    raise ValueError("image reference does not exist")
                if isinstance(element, (TableElement, ChartElement)):
                    source = self.data_sources.get(element.data_source_id)
                    if source is None or source.kind != element.type:
                        raise ValueError("data source reference is incompatible")
        return self

    @classmethod
    def validate_for_renderer(cls, value) -> "PresentationPlan":
        if not isinstance(value, dict):
            raise PresentationContractError()
        try:
            return cls.model_validate(value)
        except ValidationError as exception:
            raise PresentationContractError() from exception


def presentation_plan_sha256(plan: PresentationPlan) -> str:
    canonical = _canonical_json(plan.model_dump(mode="json", exclude_none=True))
    return sha256(canonical.encode("utf-8")).hexdigest()


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
