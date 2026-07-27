from dataclasses import dataclass
import json
from math import ceil
from typing import Any

from app.services.evidence.contracts import EvidenceItem


class BriefContextError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class EvidenceContext:
    serialized: str
    evidence_ids: tuple[str, ...]
    reference_map: tuple[tuple[str, str], ...]
    estimated_tokens: int
    available_tokens: int


_BASE36_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _short_reference(prefix: str, index: int) -> str:
    if index == 0:
        return f"{prefix}0"
    encoded = ""
    while index:
        index, remainder = divmod(index, 36)
        encoded = _BASE36_DIGITS[remainder] + encoded
    return f"{prefix}{encoded}"


def _location_row(item: EvidenceItem, reference: str) -> tuple[str, tuple[Any, ...]]:
    location = item.location
    if location.kind == "excel_cell":
        return location.sheet, (reference, location.cell)
    if location.kind == "pdf_region":
        return "", (reference, location.page, location.bbox)
    if location.kind == "word_paragraph":
        return "", (reference, location.paragraph)
    if location.kind == "image_ocr":
        return "", (reference, location.bbox)
    if location.kind == "text_line":
        return "", (reference, location.line)
    return "", (reference, location.row, location.column)


def _location_fields(kind: str) -> tuple[str, ...]:
    if kind == "excel_cell":
        return ("evidence_ref", "cell")
    if kind == "pdf_region":
        return ("evidence_ref", "page", "bbox")
    if kind == "word_paragraph":
        return ("evidence_ref", "paragraph")
    if kind == "image_ocr":
        return ("evidence_ref", "bbox")
    if kind == "text_line":
        return ("evidence_ref", "line")
    return ("evidence_ref", "row", "column")


def build_evidence_context(
    evidence: tuple[EvidenceItem, ...],
    *,
    context_window: int,
    max_output_tokens: int,
    fixed_prompt_reserve: int,
) -> EvidenceContext:
    available_tokens = context_window - max_output_tokens - fixed_prompt_reserve
    if available_tokens < 1:
        raise BriefContextError(
            "context_budget_exceeded", "模型 Context 不足以生成 Structured Brief"
        )
    evidence_ids = tuple(item.evidence_id for item in evidence)
    if not evidence or len(set(evidence_ids)) != len(evidence_ids):
        raise BriefContextError("evidence_selection_invalid", "Brief evidence 选择无效")
    if any(
        item.evidence_type not in {"source_fact", "calculated_fact"}
        for item in evidence
    ):
        raise BriefContextError(
            "evidence_type_invalid", "Brief 输入不能使用既有 AI inference"
        )

    asset_references: dict[tuple[str, str], str] = {}
    assets: list[dict[str, str]] = []
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    reference_map: list[tuple[str, str]] = []
    for index, item in enumerate(evidence):
        asset_key = (str(item.asset_id), item.asset_version)
        asset_reference = asset_references.get(asset_key)
        if asset_reference is None:
            asset_reference = _short_reference("a", len(asset_references))
            asset_references[asset_key] = asset_reference
            assets.append(
                {
                    "asset_ref": asset_reference,
                    "asset_id": asset_key[0],
                    "asset_version": asset_key[1],
                }
            )
        evidence_reference = _short_reference("r", index)
        reference_map.append((evidence_reference, item.evidence_id))
        location_scope, location_values = _location_row(item, evidence_reference)
        group_key = (
            asset_reference,
            item.location.kind,
            location_scope,
            item.evidence_type,
        )
        group = groups.get(group_key)
        if group is None:
            fields = (
                *_location_fields(item.location.kind),
                "raw_value",
                "normalized_value",
                "unit",
                "currency",
            )
            if item.evidence_type == "calculated_fact":
                fields = (*fields, "calculation_expression")
            group = {
                "asset_ref": asset_reference,
                "location_kind": item.location.kind,
                "evidence_type": item.evidence_type,
                "item_fields": fields,
                "items": [],
            }
            if location_scope:
                group["sheet"] = location_scope
            groups[group_key] = group
        row = (
            *location_values,
            item.raw_value,
            item.normalized_value,
            item.unit,
            item.currency,
        )
        if item.evidence_type == "calculated_fact":
            row = (*row, item.calculation_expression)
        group["items"].append(row)

    payload = {
        "schema_version": "brief-evidence-context.v2",
        "reference_policy": (
            "Use only evidence_ref values in Structured Brief evidence_ids."
        ),
        "assets": assets,
        "groups": list(groups.values()),
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    estimated_tokens = ceil(len(serialized.encode("utf-8")) / 3)
    if estimated_tokens > available_tokens:
        raise BriefContextError(
            "context_budget_exceeded", "所需 evidence 超出模型 Context 预算"
        )
    return EvidenceContext(
        serialized=serialized,
        evidence_ids=evidence_ids,
        reference_map=tuple(reference_map),
        estimated_tokens=estimated_tokens,
        available_tokens=available_tokens,
    )
