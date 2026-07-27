from datetime import datetime
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


WorkflowOutputKind = Literal["pptx", "xlsx"]


class WorkflowOperationError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class WorkflowTaskSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: UUID
    project_id: UUID
    brief_id: UUID | None
    generation_task_id: UUID | None
    title: str
    output_kinds: tuple[WorkflowOutputKind, ...]
    stage: str
    status: str
    progress: int
    note: str | None
    failure_code: str | None
    failure_reason: str | None
    estimated_credits: int
    settled_credits: int
    created_at: datetime
    updated_at: datetime
    replayed: bool = False


TERMINAL_WORKFLOW_STATUSES = {
    "succeeded",
    "partial_success",
    "failed",
    "provider_uncertain",
    "cancelled",
}


@dataclass(frozen=True)
class WorkflowServices:
    tasks: object
