from dataclasses import dataclass
from hashlib import sha256
import json

from app.skills.catalog import KNOWLEDGE_EDUCATION_SKILL_CODE, PPT_SKILL_CODE


TEMPLATE_CATALOG_SCHEMA_VERSION = "presentation-template-catalog.v1"
TEMPLATE_VERSION = "1.0.0"
TEMPLATE_LAYOUTS = ("title", "content", "section", "closing")
ORIGINAL_SOURCE = {
    "kind": "system_original",
    "license": "Office AI Original",
    "attribution": "Office AI Design System",
}


@dataclass(frozen=True)
class PresentationTemplateDefinition:
    template_code: str
    version: str
    name: str
    category: str
    description: str
    style_keywords: tuple[str, ...]
    use_cases: tuple[str, ...]
    colors: tuple[str, ...]
    fonts: tuple[str, ...]
    layouts: tuple[str, ...]
    compatible_skills: tuple[str, ...]
    cover_url: str
    representative_urls: tuple[str, ...]
    source: dict[str, str]
    renderer: dict[str, str]
    checksum: str

    @property
    def database_version(self) -> int:
        return 1

    def catalog_payload(self) -> dict:
        return {
            "schema_version": TEMPLATE_CATALOG_SCHEMA_VERSION,
            "template_code": self.template_code,
            "version": self.version,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "style_keywords": list(self.style_keywords),
            "use_cases": list(self.use_cases),
            "colors": list(self.colors),
            "fonts": list(self.fonts),
            "layouts": list(self.layouts),
            "compatible_skills": list(self.compatible_skills),
            "cover_url": self.cover_url,
            "representative_urls": list(self.representative_urls),
            "source": self.source,
            "renderer": self.renderer,
        }

    def design_config(self) -> dict:
        return self.catalog_payload()


def _checksum(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _template(
    *,
    code: str,
    name: str,
    category: str,
    description: str,
    style_keywords: tuple[str, ...],
    use_cases: tuple[str, ...],
    colors: tuple[str, ...],
    compatible_skills: tuple[str, ...],
    renderer: dict[str, str],
) -> PresentationTemplateDefinition:
    preview_root = f"/template-previews/{code}"
    payload = {
        "schema_version": TEMPLATE_CATALOG_SCHEMA_VERSION,
        "template_code": code,
        "version": TEMPLATE_VERSION,
        "name": name,
        "category": category,
        "description": description,
        "style_keywords": list(style_keywords),
        "use_cases": list(use_cases),
        "colors": list(colors),
        "fonts": ["Microsoft YaHei"],
        "layouts": list(TEMPLATE_LAYOUTS),
        "compatible_skills": list(compatible_skills),
        "cover_url": f"{preview_root}/cover.svg",
        "representative_urls": [f"{preview_root}/representative.svg"],
        "source": ORIGINAL_SOURCE,
        "renderer": renderer,
    }
    return PresentationTemplateDefinition(
        template_code=code,
        version=TEMPLATE_VERSION,
        name=name,
        category=category,
        description=description,
        style_keywords=style_keywords,
        use_cases=use_cases,
        colors=colors,
        fonts=("Microsoft YaHei",),
        layouts=TEMPLATE_LAYOUTS,
        compatible_skills=compatible_skills,
        cover_url=f"{preview_root}/cover.svg",
        representative_urls=(f"{preview_root}/representative.svg",),
        source=ORIGINAL_SOURCE,
        renderer=renderer,
        checksum=_checksum(payload),
    )


PRESENTATION_TEMPLATES = (
    _template(
        code="ppt.executive-blue.v1",
        name="高管钢蓝",
        category="management",
        description="克制留白与清晰层级兼顾的管理层沟通模板。",
        style_keywords=("克制", "专业", "清晰"),
        use_cases=("管理层汇报", "知识培训", "方案沟通"),
        colors=("#F5F8FC", "#123B6D", "#2F6FB0", "#29A3A3"),
        compatible_skills=(PPT_SKILL_CODE, KNOWLEDGE_EDUCATION_SKILL_CODE),
        renderer={
            "background": "F5F8FC",
            "surface": "FFFFFF",
            "primary": "123B6D",
            "secondary": "2F6FB0",
            "accent": "29A3A3",
            "text": "172033",
            "muted": "64748B",
        },
    ),
    _template(
        code="ppt.operating-review.v1",
        name="经营复盘",
        category="operating-review",
        description="围绕目标、差距、原因与行动项组织经营复盘。",
        style_keywords=("复盘", "行动", "稳健"),
        use_cases=("销售经营汇报", "季度复盘", "行动计划"),
        colors=("#FBF9F6", "#8B1E1E", "#B33A3A", "#C89B3C"),
        compatible_skills=(PPT_SKILL_CODE,),
        renderer={
            "background": "FBF9F6",
            "surface": "FFFFFF",
            "primary": "8B1E1E",
            "secondary": "B33A3A",
            "accent": "C89B3C",
            "text": "2B211F",
            "muted": "7D6C68",
        },
    ),
    _template(
        code="ppt.data-story.v1",
        name="数据叙事",
        category="data-story",
        description="用指标层级、对比关系和结论强调构建数据故事。",
        style_keywords=("数据", "叙事", "洞察"),
        use_cases=("指标分析", "趋势解读", "研究分享"),
        colors=("#F8F6FC", "#3D2C68", "#7357A8", "#DD6B7B"),
        compatible_skills=(PPT_SKILL_CODE, KNOWLEDGE_EDUCATION_SKILL_CODE),
        renderer={
            "background": "F8F6FC",
            "surface": "FFFFFF",
            "primary": "3D2C68",
            "secondary": "7357A8",
            "accent": "DD6B7B",
            "text": "251F32",
            "muted": "746B84",
        },
    ),
)

_PRESENTATION_TEMPLATE_BY_REFERENCE = {
    (item.template_code, item.version): item for item in PRESENTATION_TEMPLATES
}


def get_presentation_template(
    template_code: str,
    version: str = TEMPLATE_VERSION,
) -> PresentationTemplateDefinition | None:
    return _PRESENTATION_TEMPLATE_BY_REFERENCE.get((template_code, version))


def default_presentation_template(
    skill_code: str,
) -> PresentationTemplateDefinition:
    code = (
        "ppt.operating-review.v1"
        if skill_code == PPT_SKILL_CODE
        else "ppt.executive-blue.v1"
    )
    template = get_presentation_template(code)
    if template is None:
        raise RuntimeError("presentation template catalog is incomplete")
    return template


def template_row_matches_definition(
    row,
    definition: PresentationTemplateDefinition,
) -> bool:
    return (
        row.owner_user_id is None
        and row.template_type == "pptx"
        and row.source == "system_original"
        and row.template_code == definition.template_code
        and row.version == definition.database_version
        and row.status == "published"
        and row.display_name == definition.name
        and row.category == definition.category
        and tuple(row.style_keywords or ()) == definition.style_keywords
        and row.design_config == definition.design_config()
        and row.checksum == definition.checksum
    )
