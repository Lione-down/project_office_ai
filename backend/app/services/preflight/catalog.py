from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Literal

from app.skills.catalog import (
    EXCEL_SKILL_CODE,
    KNOWLEDGE_EDUCATION_SKILL_CODE,
    PPT_SKILL_CODE,
)


PPT_DEFAULT_TEMPLATE = "ppt.operating-review.v1"
EXCEL_DEFAULT_TEMPLATE = "excel.analysis-dashboard.v1"
_BASE_OUTPUT_CREDITS = 800


class TemplateSelectionError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class TemplateDefinition:
    template_code: str
    version: str
    output_kind: Literal["pptx", "xlsx"]


@dataclass(frozen=True)
class PlannedOutput:
    skill_code: str
    kind: Literal["pptx", "xlsx"]
    title: str
    template_code: str
    template_version: str
    estimated_credits: int


ALPHA_TEMPLATES = (
    TemplateDefinition(PPT_DEFAULT_TEMPLATE, "1.0.0", "pptx"),
    TemplateDefinition("ppt.executive-blue.v1", "1.0.0", "pptx"),
    TemplateDefinition("ppt.data-story.v1", "1.0.0", "pptx"),
    TemplateDefinition(EXCEL_DEFAULT_TEMPLATE, "1.0.0", "xlsx"),
    TemplateDefinition("excel.operating-review.v1", "1.0.0", "xlsx"),
)
_TEMPLATE_BY_REFERENCE = {
    (template.template_code, template.version): template for template in ALPHA_TEMPLATES
}
_SKILL_OUTPUTS = {
    PPT_SKILL_CODE: ("pptx", "销售经营汇报", PPT_DEFAULT_TEMPLATE),
    KNOWLEDGE_EDUCATION_SKILL_CODE: (
        "pptx",
        "知识科普与培训",
        "ppt.executive-blue.v1",
    ),
    EXCEL_SKILL_CODE: ("xlsx", "销售数据分析与经营看板", EXCEL_DEFAULT_TEMPLATE),
}


def build_alpha_output_plan(
    skill_codes: tuple[str, ...],
    template_versions: tuple[tuple[str, str], ...],
    credit_multiplier: Decimal,
) -> tuple[PlannedOutput, ...]:
    selected_templates: dict[str, TemplateDefinition] = {}
    for reference in template_versions:
        template = _TEMPLATE_BY_REFERENCE.get(reference)
        if template is None or template.output_kind in selected_templates:
            raise TemplateSelectionError(
                "template_incompatible", "系统模板与所选输出不兼容"
            )
        selected_templates[template.output_kind] = template

    estimated_credits = int(
        (Decimal(_BASE_OUTPUT_CREDITS) * credit_multiplier).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    outputs = []
    for skill_code in skill_codes:
        skill_output = _SKILL_OUTPUTS.get(skill_code)
        if skill_output is None:
            raise TemplateSelectionError(
                "skill_selection_invalid", "Alpha Skill 选择不受支持"
            )
        output_kind, title, default_template_code = skill_output
        template = (
            selected_templates.get(output_kind)
            or _TEMPLATE_BY_REFERENCE[(default_template_code, "1.0.0")]
        )
        outputs.append(
            PlannedOutput(
                skill_code=skill_code,
                kind=output_kind,
                title=title,
                template_code=template.template_code,
                template_version=template.version,
                estimated_credits=estimated_credits,
            )
        )

    if set(selected_templates) - {output.kind for output in outputs}:
        raise TemplateSelectionError(
            "template_incompatible", "系统模板与所选输出不兼容"
        )
    return tuple(outputs)
