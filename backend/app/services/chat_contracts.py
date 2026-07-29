from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ChatRole = Literal["user", "assistant"]
ChatMessageStatus = Literal[
    "pending",
    "streaming",
    "succeeded",
    "cancelled_partial",
    "failed",
    "provider_uncertain",
]
ChatRunStatus = Literal[
    "queued",
    "streaming",
    "succeeded",
    "failed",
    "cancelled_partial",
    "provider_uncertain",
]
ChatEventName = Literal[
    "run.started",
    "message.delta",
    "message.snapshot",
    "run.completed",
    "run.cancelled_partial",
    "run.failed",
    "run.provider_uncertain",
]


class ChatOperationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class ChatThreadCreateCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: UUID | None = None
    mode: Literal["chat", "ppt"] = "chat"


class ChatThreadUpdateCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    default_model_id: UUID | None = None
    mode: Literal["chat", "ppt"] | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.title is None and self.default_model_id is None and self.mode is None:
            raise ValueError("at least one change is required")
        return self


class ChatRunCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str | None = None
    model_id: UUID | None = None
    parent_message_id: UUID | None = None
    supersedes_message_id: UUID | None = None
    regenerate_from_message_id: UUID | None = None
    thinking_enabled: bool = False
    context_asset_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_variant(self):
        if self.regenerate_from_message_id is not None:
            if self.content is not None or self.supersedes_message_id is not None:
                raise ValueError("regenerate cannot include content or supersedes")
        elif self.content is None or not self.content.strip():
            raise ValueError("content is required")
        if (
            self.supersedes_message_id is not None
            and self.parent_message_id is not None
        ):
            raise ValueError("supersedes and parent are mutually exclusive")
        return self


class ChatThreadSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    thread_id: UUID
    user_id: UUID
    title: str
    default_model_id: UUID
    model_code: str
    mode: str
    status: str
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime


class ChatMessageSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: UUID
    sequence: int
    role: ChatRole
    content: str
    status: ChatMessageStatus
    parent_message_id: UUID | None
    supersedes_message_id: UUID | None
    branch_root_id: UUID
    run_id: UUID | None
    model_code: str | None
    deck_draft_id: UUID | None = None
    deck_status: str | None = None
    generation_task_id: UUID | None = None
    generation_status: str | None = None
    created_at: datetime
    finalized_at: datetime | None


class ChatThreadDetail(ChatThreadSnapshot):
    messages: tuple[ChatMessageSnapshot, ...]


class ChatEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["chat-sse.v1"] = "chat-sse.v1"
    event: ChatEventName
    run_id: UUID
    thread_id: UUID
    sequence: int
    occurred_at: datetime
    trace_id: str
    payload: dict


@dataclass(frozen=True)
class PreparedChatStream:
    run_id: UUID
    events: AsyncIterator[ChatEvent]
    replayed: bool


@dataclass(frozen=True)
class ChatServices:
    conversations: object
