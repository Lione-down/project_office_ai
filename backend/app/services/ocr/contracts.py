from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


Coordinate = Annotated[float, Field(ge=0)]
Point = tuple[Coordinate, Coordinate]


class OcrServiceError(Exception):
    def __init__(
        self,
        error_code: str,
        safe_message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(safe_message)
        self.error_code = error_code
        self.safe_message = safe_message
        self.retryable = retryable


class OcrEngine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)


class OcrItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    text: str = Field(min_length=1, max_length=16_384)
    confidence: float = Field(ge=0, le=1)
    polygon: tuple[Point, Point, Point, Point]

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OCR text must not be blank")
        return value

    @computed_field
    @property
    def bbox(self) -> tuple[float, float, float, float]:
        x_values = [point[0] for point in self.polygon]
        y_values = [point[1] for point in self.polygon]
        return min(x_values), min(y_values), max(x_values), max(y_values)


class OcrResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: str = Field(pattern=r"^paddleocr-response\.v1$")
    engine: OcrEngine
    items: tuple[OcrItem, ...]
