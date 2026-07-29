from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.templates.catalog import PresentationTemplateDefinition


class TemplateSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["system_original"]
    license: Literal["Office AI Original"]
    attribution: Literal["Office AI Design System"]


class TemplateSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    template_code: str
    version: Literal["1.0.0"]
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    name: str
    category: str
    style_keywords: tuple[str, ...]
    use_cases: tuple[str, ...]
    cover_url: str
    representative_urls: tuple[str, ...]
    compatible_skills: tuple[str, ...]

    @classmethod
    def from_definition(
        cls,
        definition: PresentationTemplateDefinition | dict,
    ) -> "TemplateSummaryResponse":
        return cls(
            **{
                key: (
                    definition[key]
                    if isinstance(definition, dict)
                    else getattr(definition, key)
                )
                for key in cls.model_fields
            }
        )


class TemplateDetailResponse(TemplateSummaryResponse):
    description: str
    colors: tuple[str, ...]
    fonts: tuple[str, ...]
    layouts: tuple[str, ...]
    source: TemplateSourceResponse

    @classmethod
    def from_definition(
        cls,
        definition: PresentationTemplateDefinition | dict,
    ) -> "TemplateDetailResponse":
        return cls(
            **{
                key: (
                    definition[key]
                    if isinstance(definition, dict)
                    else getattr(definition, key)
                )
                for key in cls.model_fields
            }
        )
