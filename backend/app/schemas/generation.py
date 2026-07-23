from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.services.generation_contracts import (
    CreditEntrySnapshot,
    GenerationSnapshot,
    GenerationStepSnapshot,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationCreateRequest(StrictModel):
    brief_id: UUID


class GenerationStepResponse(StrictModel):
    step_key: str
    output_kind: Literal["pptx", "xlsx"]
    status: str
    attempt: int
    estimated_credits: int
    error_category: str | None

    @classmethod
    def from_snapshot(cls, item: GenerationStepSnapshot):
        return cls(**item.__dict__)


class GenerationTaskResponse(StrictModel):
    task_id: UUID
    brief_id: UUID
    status: str
    progress: int
    estimated_credits: int
    settled_credits: int
    error_category: str | None
    cancel_requested: bool
    steps: tuple[GenerationStepResponse, ...]
    replayed: bool

    @classmethod
    def from_snapshot(cls, item: GenerationSnapshot):
        return cls(
            **{
                **item.__dict__,
                "steps": tuple(
                    GenerationStepResponse.from_snapshot(step) for step in item.steps
                ),
            }
        )


class CreditBalanceResponse(StrictModel):
    balance: int


class CreditEntryResponse(StrictModel):
    entry_id: UUID
    task_id: UUID | None
    entry_type: str
    amount: int
    balance_after: int
    related_entry_id: UUID | None
    created_at: datetime

    @classmethod
    def from_snapshot(cls, item: CreditEntrySnapshot):
        return cls(**item.__dict__)


class CreditLedgerResponse(StrictModel):
    entries: tuple[CreditEntryResponse, ...]
