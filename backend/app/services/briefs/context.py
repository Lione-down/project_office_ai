from dataclasses import dataclass
import json
from math import ceil

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
    estimated_tokens: int
    available_tokens: int


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
    ordered = tuple(sorted(evidence, key=lambda item: item.evidence_id))
    evidence_ids = tuple(item.evidence_id for item in ordered)
    if not ordered or len(set(evidence_ids)) != len(evidence_ids):
        raise BriefContextError("evidence_selection_invalid", "Brief evidence 选择无效")
    if any(
        item.evidence_type not in {"source_fact", "calculated_fact"} for item in ordered
    ):
        raise BriefContextError(
            "evidence_type_invalid", "Brief 输入不能使用既有 AI inference"
        )
    payload = [
        {
            "evidence_id": item.evidence_id,
            "evidence_type": item.evidence_type,
            "asset_id": str(item.asset_id),
            "asset_version": item.asset_version,
            "location": item.location.model_dump(mode="json"),
            "raw_value": item.raw_value,
            "normalized_value": item.normalized_value,
            "unit": item.unit,
            "currency": item.currency,
        }
        for item in ordered
    ]
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
        estimated_tokens=estimated_tokens,
        available_tokens=available_tokens,
    )
