from dataclasses import dataclass
import json
import re
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from app.services.briefs.contracts import StructuredBrief


MAX_REPAIR_HINTS = 24
MAX_REPAIR_HINT_LENGTH = 160
_SAFE_ERROR_TYPE = re.compile(r"^[a-z0-9_.-]{1,80}$")


def _schema_property_names() -> frozenset[str]:
    names: set[str] = set()
    pending: list[object] = [StructuredBrief.model_json_schema()]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            properties = current.get("properties")
            if isinstance(properties, dict):
                names.update(str(name) for name in properties)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return frozenset(names)


_SCHEMA_PROPERTY_NAMES = _schema_property_names()


def _bounded_repair_hints(hints: tuple[str, ...]) -> tuple[str, ...]:
    bounded: list[str] = []
    for hint in hints:
        safe_hint = hint[:MAX_REPAIR_HINT_LENGTH]
        if safe_hint not in bounded:
            bounded.append(safe_hint)
        if len(bounded) == MAX_REPAIR_HINTS:
            break
    return tuple(bounded)


def _pydantic_repair_hints(exception: ValidationError) -> tuple[str, ...]:
    hints: list[str] = []
    for error in exception.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        path = []
        for component in error.get("loc", ()):
            if isinstance(component, int):
                path.append(str(component))
            elif str(component) in _SCHEMA_PROPERTY_NAMES:
                path.append(str(component))
            else:
                path.append("unknown_field")
        error_type = str(error.get("type", "validation_error"))
        if not _SAFE_ERROR_TYPE.fullmatch(error_type):
            error_type = "validation_error"
        hints.append(f"{'.'.join(path) or 'root'}:{error_type}")
    return _bounded_repair_hints(tuple(hints))


class BriefValidationError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        repair_hints: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.repair_hints = _bounded_repair_hints(repair_hints)


@dataclass(frozen=True)
class ExpectedBriefSnapshot:
    module: Literal["ppt", "excel", "combined"]
    goal: str
    audience: str
    must_include: tuple[str, ...]
    must_exclude: tuple[str, ...]
    source_asset_versions: tuple[tuple[UUID, str], ...]
    term_library_versions: tuple[tuple[UUID, int], ...]
    selected_skills: tuple[tuple[str, str], ...]
    model_id: UUID
    provider_id: UUID
    credential_id: UUID
    model_code: str
    evidence_ids: frozenset[str]


def resolve_brief_evidence_references(
    response_content: str,
    reference_map: dict[str, str],
) -> str:
    try:
        payload = json.loads(response_content)
    except (json.JSONDecodeError, TypeError):
        return response_content
    if not isinstance(payload, dict):
        return response_content

    def resolve_items(items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            evidence_ids = item.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not all(
                isinstance(value, str) for value in evidence_ids
            ):
                continue
            resolved = []
            for value in evidence_ids:
                if value in reference_map:
                    resolved.append(reference_map[value])
                else:
                    raise BriefValidationError(
                        "brief_evidence_invalid",
                        "Structured Brief 引用了不在本次 Context 的 evidence",
                        ("evidence_ids:unknown_reference",),
                    )
            item["evidence_ids"] = resolved

    output_plan = payload.get("output_plan")
    if isinstance(output_plan, dict):
        resolve_items(output_plan.get("deliverables"))
    for field in (
        "facts",
        "inferences",
        "unresolved_items",
        "must_include",
        "must_exclude",
    ):
        resolve_items(payload.get(field))
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def validate_brief_response(
    response_content: str, expected: ExpectedBriefSnapshot
) -> StructuredBrief:
    try:
        payload = json.loads(response_content)
        brief = StructuredBrief.model_validate(payload)
    except json.JSONDecodeError as exception:
        raise BriefValidationError(
            "brief_schema_invalid",
            "Structured Brief Schema 无效",
            ("json:invalid",),
        ) from exception
    except ValidationError as exception:
        raise BriefValidationError(
            "brief_schema_invalid",
            "Structured Brief Schema 无效",
            _pydantic_repair_hints(exception),
        ) from exception
    except TypeError as exception:
        raise BriefValidationError(
            "brief_schema_invalid",
            "Structured Brief Schema 无效",
            ("root:invalid_type",),
        ) from exception
    actual_assets = tuple(
        (item.asset_id, item.asset_version) for item in brief.source_asset_versions
    )
    actual_terms = tuple(
        (item.library_id, item.version) for item in brief.term_library_versions
    )
    actual_skills = tuple(
        (item.skill_code, item.version) for item in brief.selected_skills
    )
    expected_output_kinds = tuple(
        "pptx" if skill_code.startswith("ppt.") else "xlsx"
        for skill_code, _ in expected.selected_skills
    )
    actual_output_kinds = tuple(item.kind for item in brief.output_plan.deliverables)
    actual_must_include = tuple(item.content for item in brief.must_include)
    actual_must_exclude = tuple(item.content for item in brief.must_exclude)
    user_constraints_are_exact = all(
        item.source == "user" and not item.evidence_ids
        for item in (*brief.must_include, *brief.must_exclude)
    )
    model = brief.selected_model
    if (
        brief.module != expected.module
        or brief.goal != expected.goal
        or brief.audience != expected.audience
        or actual_must_include != expected.must_include
        or actual_must_exclude != expected.must_exclude
        or not user_constraints_are_exact
        or actual_assets != expected.source_asset_versions
        or actual_terms != expected.term_library_versions
        or actual_skills != expected.selected_skills
        or actual_output_kinds != expected_output_kinds
        or model.model_id != expected.model_id
        or model.provider_id != expected.provider_id
        or model.credential_id != expected.credential_id
        or model.model_code != expected.model_code
    ):
        raise BriefValidationError(
            "brief_snapshot_mismatch",
            "Structured Brief 输入快照不一致",
            ("authoritative_snapshot:mismatch",),
        )
    referenced_ids = {
        evidence_id
        for item in (
            *brief.output_plan.deliverables,
            *brief.facts,
            *brief.inferences,
            *brief.unresolved_items,
            *brief.must_include,
            *brief.must_exclude,
        )
        for evidence_id in item.evidence_ids
    }
    if not referenced_ids.issubset(expected.evidence_ids):
        raise BriefValidationError(
            "brief_evidence_invalid",
            "Structured Brief 引用了不存在的 evidence",
            ("evidence_ids:unknown_reference",),
        )
    return brief
