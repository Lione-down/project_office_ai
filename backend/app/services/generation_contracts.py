from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID


if TYPE_CHECKING:
    from app.services.generation import GenerationService


TERMINAL_TASK_STATUSES = {
    "succeeded",
    "partial_success",
    "provider_uncertain",
    "failed",
    "cancelled",
}


class GenerationOperationError(RuntimeError):
    def __init__(self, error_code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class GenerationStepSnapshot:
    step_key: str
    output_kind: str
    status: str
    attempt: int
    estimated_credits: int
    error_category: str | None
    output_asset_id: UUID | None = None
    asset_version: str | None = None
    quality_status: str | None = None
    download_allowed: bool = False
    quality_report_schema_version: str | None = None


@dataclass(frozen=True)
class GenerationOutputSnapshot:
    output_kind: str
    status: str
    estimated_credits: int
    error_category: str | None
    asset_id: UUID | None
    asset_version: str | None
    quality_status: str | None
    download_allowed: bool
    quality_report_schema_version: str | None


@dataclass(frozen=True)
class GenerationSnapshot:
    task_id: UUID
    brief_id: UUID
    status: str
    progress: int
    estimated_credits: int
    settled_credits: int
    error_category: str | None
    cancel_requested: bool
    steps: tuple[GenerationStepSnapshot, ...]
    replayed: bool = False


@dataclass(frozen=True)
class CreditEntrySnapshot:
    entry_id: UUID
    task_id: UUID | None
    entry_type: str
    amount: int
    balance_after: int
    related_entry_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class GenerationServices:
    generation: "GenerationService"
