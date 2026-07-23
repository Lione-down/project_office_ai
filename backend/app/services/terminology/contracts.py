from typing import Literal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services.evidence.contracts import EvidenceItem


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UnresolvedItem(StrictModel):
    code: Literal[
        "currency_conflict",
        "date_incomplete",
        "date_invalid",
        "metric_scope_conflict",
        "source_conflict",
        "term_ambiguous",
        "unit_conflict",
        "unit_unknown",
    ]
    fact_key: str | None = Field(default=None, max_length=255)
    evidence_ids: tuple[str, ...] = ()
    candidates: tuple[str, ...] = ()
    requires_authority: bool = False


class TermRule(StrictModel):
    library_id: UUID
    library_version: int = Field(ge=1)
    project_id: UUID | None
    canonical_term: str = Field(min_length=1, max_length=255)
    aliases: tuple[str, ...] = ()
    unit: str | None = Field(default=None, max_length=32)
    metric_scope: str | None = Field(default=None, max_length=1024)
    priority: int = Field(ge=-1000, le=1000)


class TermResolution(StrictModel):
    canonical_term: str | None
    unit: str | None
    metric_scope: str | None
    library_id: UUID | None
    library_version: int | None
    unresolved: tuple[UnresolvedItem, ...] = ()


class NormalizedValue(StrictModel):
    raw_value: str = Field(min_length=1, max_length=16_384)
    normalized_value: str | None = Field(default=None, max_length=16_384)
    value_kind: Literal["date", "narrative", "number"]
    unit: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, max_length=3)
    rule_version: str = Field(min_length=1, max_length=64)
    unresolved: tuple[UnresolvedItem, ...] = ()


class EvidenceFact(StrictModel):
    fact_key: str = Field(min_length=1, max_length=255)
    evidence_id: str = Field(pattern=r"^e-[a-f0-9]{64}$")
    normalized_value: str | None = Field(default=None, max_length=16_384)
    unit: str | None = Field(default=None, max_length=32)


class TermItemSummary(StrictModel):
    item_id: UUID
    canonical_term: str
    aliases: tuple[str, ...]
    unit: str | None
    definition: str | None
    metric_scope: str | None
    priority: int


class TermLibrarySnapshot(StrictModel):
    library_id: UUID
    project_id: UUID | None
    name: str
    description: str | None
    status: Literal["active", "deleted"]
    version: int
    created_at: datetime
    items: tuple[TermItemSummary, ...] = ()


class NormalizedEvidenceItem(EvidenceItem):
    fact_key: str = Field(min_length=1, max_length=255)
    canonical_term: str = Field(min_length=1, max_length=255)
    normalization_rule_version: str = Field(min_length=1, max_length=64)
    term_library_id: UUID | None = None
    term_library_version: int | None = Field(default=None, ge=1)
    normalization_unresolved: tuple[str, ...] = ()
