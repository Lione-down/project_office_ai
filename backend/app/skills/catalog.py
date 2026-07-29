from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

from app.services.briefs.contracts import BRIEF_TOP_LEVEL_FIELDS


PPT_SKILL_CODE = "ppt.sales-business-review.v1"
EXCEL_SKILL_CODE = "excel.sales-analysis-dashboard.v1"
KNOWLEDGE_EDUCATION_SKILL_CODE = "ppt.knowledge-education.v1"


class SkillSelectionError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class SkillDefinition:
    skill_code: str
    version: str
    kind: Literal["user_workflow", "internal_step"]
    display_name: str
    description: str
    output_kind: Literal["pptx", "xlsx"]
    input_schema: dict
    output_schema: dict
    workflow: dict
    capability_requirements: dict
    status: Literal["published", "inactive"]

    @property
    def checksum(self) -> str:
        payload = {
            "skill_code": self.skill_code,
            "version": self.version,
            "kind": self.kind,
            "display_name": self.display_name,
            "description": self.description,
            "output_kind": self.output_kind,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "workflow": self.workflow,
            "capability_requirements": self.capability_requirements,
            "status": self.status,
        }
        serialized = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SkillSelection:
    module: Literal["ppt", "excel", "combined"]
    skills: tuple[SkillDefinition, ...]


def skill_row_matches_definition(row: object, expected: SkillDefinition) -> bool:
    return (
        getattr(row, "skill_code", None) == expected.skill_code
        and getattr(row, "version", None) == expected.version
        and getattr(row, "kind", None) == expected.kind
        and getattr(row, "display_name", None) == expected.display_name
        and getattr(row, "description", None) == expected.description
        and getattr(row, "output_kind", None) == expected.output_kind
        and getattr(row, "input_schema", None) == expected.input_schema
        and getattr(row, "output_schema", None) == expected.output_schema
        and getattr(row, "workflow", None) == expected.workflow
        and getattr(row, "capability_requirements", None)
        == expected.capability_requirements
        and getattr(row, "status", None) == expected.status
        and getattr(row, "checksum", None) == expected.checksum
    )


_COMMON_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source_asset_versions",
        "term_library_versions",
        "selected_model",
        "user_requirements",
    ],
    "properties": {
        "source_asset_versions": {"type": "array", "minItems": 1, "maxItems": 20},
        "term_library_versions": {"type": "array"},
        "selected_model": {"type": "object"},
        "user_requirements": {"type": "object"},
    },
}
_BRIEF_OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "office-ai://schemas/structured-brief.v1",
    "type": "object",
    "additionalProperties": False,
    "required": list(BRIEF_TOP_LEVEL_FIELDS),
    "$defs": {
        "content_item": {
            "type": "object",
            "additionalProperties": False,
            "required": ["content", "source", "evidence_ids"],
            "properties": {
                "content": {"type": "string", "minLength": 1},
                "source": {
                    "enum": [
                        "user",
                        "file",
                        "calculation",
                        "agnes_inference",
                        "system_default",
                    ]
                },
                "evidence_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^e-[a-f0-9]{64}$"},
                },
            },
        }
    },
    "properties": {
        "module": {"enum": ["ppt", "excel", "combined"]},
        "goal": {"type": "string", "minLength": 1},
        "audience": {"type": "string", "minLength": 1},
        "language": {"const": "zh-CN"},
        "domain": {"const": "sales"},
        "tone": {"const": "professional"},
        "source_asset_versions": {"type": "array", "minItems": 1, "maxItems": 20},
        "term_library_versions": {"type": "array", "maxItems": 20},
        "selected_skills": {"type": "array", "minItems": 1, "maxItems": 2},
        "selected_model": {"type": "object"},
        "output_plan": {"type": "object"},
        "facts": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "inferences": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "unresolved_items": {"type": "array"},
        "must_include": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "must_exclude": {
            "type": "array",
            "items": {"$ref": "#/$defs/content_item"},
        },
        "citation_policy": {"type": "object"},
    },
}
_COMMON_CAPABILITIES = {
    "text_generation": True,
    "structured_output": True,
    "image_input": False,
    "max_context_tokens": 262_144,
}


ALPHA_SKILLS = (
    SkillDefinition(
        skill_code=PPT_SKILL_CODE,
        version="1.0.0",
        kind="user_workflow",
        display_name="销售经营汇报",
        description="从销售材料生成证据约束的经营汇报 Structured Brief。",
        output_kind="pptx",
        input_schema={
            **_COMMON_INPUT_SCHEMA,
            "x-supported-inputs": [
                "xlsx",
                "xlsm",
                "pdf",
                "docx",
                "png",
                "jpg",
                "jpeg",
                "webp",
                "txt",
                "md",
            ],
        },
        output_schema=_BRIEF_OUTPUT_SCHEMA,
        workflow={
            "steps": [
                "select_evidence",
                "generate_structured_brief",
                "validate_and_repair_once",
                "persist_revision",
            ],
            "output": "pptx",
        },
        capability_requirements=_COMMON_CAPABILITIES,
        status="published",
    ),
    SkillDefinition(
        skill_code=EXCEL_SKILL_CODE,
        version="1.0.0",
        kind="user_workflow",
        display_name="销售数据分析与经营看板",
        description="从销售材料生成证据约束的分析看板 Structured Brief。",
        output_kind="xlsx",
        input_schema={
            **_COMMON_INPUT_SCHEMA,
            "x-supported-inputs": [
                "xlsx",
                "xlsm",
                "csv",
                "pdf",
                "png",
                "jpg",
                "jpeg",
                "webp",
                "txt",
                "md",
            ],
        },
        output_schema=_BRIEF_OUTPUT_SCHEMA,
        workflow={
            "steps": [
                "select_evidence",
                "generate_structured_brief",
                "validate_and_repair_once",
                "persist_revision",
            ],
            "output": "xlsx",
        },
        capability_requirements=_COMMON_CAPABILITIES,
        status="published",
    ),
)
KNOWLEDGE_EDUCATION_SKILL = SkillDefinition(
    skill_code=KNOWLEDGE_EDUCATION_SKILL_CODE,
    version="1.0.0",
    kind="user_workflow",
    display_name="知识科普与培训",
    description="把用户输入、Agnes推断和可选Evidence组织为可编辑的知识型演示。",
    output_kind="pptx",
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "required": [
            "topic",
            "audience",
            "slide_count",
            "language",
            "style",
            "source_mode",
            "selected_model",
        ],
        "properties": {
            "topic": {"type": "string", "minLength": 1, "maxLength": 500},
            "audience": {"type": "string", "minLength": 1, "maxLength": 500},
            "slide_count": {"type": "integer", "minimum": 3, "maximum": 40},
            "language": {"const": "zh-CN"},
            "style": {"type": "string", "minLength": 1, "maxLength": 500},
            "source_mode": {"enum": ["inspiration", "materials", "mixed"]},
            "selected_model": {"type": "object"},
        },
    },
    output_schema={
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "office-ai://schemas/deck-brief.v1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "topic",
            "audience",
            "language",
            "style",
            "source_mode",
            "skill_code",
            "slides",
        ],
        "properties": {
            "schema_version": {"const": "deck-brief.v1"},
            "slides": {"type": "array", "minItems": 3, "maxItems": 40},
        },
    },
    workflow={
        "steps": [
            "build_ppt_outline",
            "validate_and_repair_once",
            "persist_deck_revision",
            "run_deck_preflight",
            "submit_ppt_generation",
        ],
        "output": "pptx",
    },
    capability_requirements={
        "text_generation": True,
        "structured_output": True,
        "image_input": False,
        "max_context_tokens": 262_144,
    },
    status="published",
)
POST_ALPHA_USER_SKILLS = (*ALPHA_SKILLS, KNOWLEDGE_EDUCATION_SKILL)
_SKILL_BY_CODE = {skill.skill_code: skill for skill in ALPHA_SKILLS}
_POST_ALPHA_SKILL_BY_CODE = {
    skill.skill_code: skill for skill in POST_ALPHA_USER_SKILLS
}


def resolve_alpha_skill_selection(skill_codes: tuple[str, ...]) -> SkillSelection:
    if (
        not skill_codes
        or len(skill_codes) > len(ALPHA_SKILLS)
        or len(set(skill_codes)) != len(skill_codes)
        or any(code not in _SKILL_BY_CODE for code in skill_codes)
    ):
        raise SkillSelectionError("skill_selection_invalid", "Alpha Skill 选择不受支持")
    selected = tuple(_SKILL_BY_CODE[code] for code in skill_codes)
    output_kinds = {skill.output_kind for skill in selected}
    if len(selected) == 2 and output_kinds != {"pptx", "xlsx"}:
        raise SkillSelectionError("skill_selection_invalid", "Alpha Skill 组合不受支持")
    module = (
        "combined"
        if len(selected) == 2
        else "ppt"
        if selected[0].output_kind == "pptx"
        else "excel"
    )
    return SkillSelection(module=module, skills=selected)


def resolve_deck_skill_selection(skill_codes: tuple[str, ...]) -> SkillSelection:
    if len(skill_codes) != 1 or skill_codes[0] not in {
        PPT_SKILL_CODE,
        KNOWLEDGE_EDUCATION_SKILL_CODE,
    }:
        raise SkillSelectionError("skill_selection_invalid", "Deck Skill 选择不受支持")
    return SkillSelection(
        module="ppt",
        skills=(_POST_ALPHA_SKILL_BY_CODE[skill_codes[0]],),
    )
