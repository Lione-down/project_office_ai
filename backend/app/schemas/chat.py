from uuid import UUID

from pydantic import BaseModel, Field

from app.services.chat_contracts import (
    ChatRunCommand,
    ChatThreadCreateCommand,
    ChatThreadUpdateCommand,
)


class ChatThreadCreateRequest(BaseModel):
    model_id: UUID | None = None
    mode: str = Field(default="chat", pattern=r"^(chat|ppt)$")

    def to_command(self) -> ChatThreadCreateCommand:
        return ChatThreadCreateCommand(**self.model_dump())


class ChatThreadUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    default_model_id: UUID | None = None
    mode: str | None = Field(default=None, pattern=r"^(chat|ppt)$")

    def to_command(self) -> ChatThreadUpdateCommand:
        return ChatThreadUpdateCommand(**self.model_dump(exclude_unset=True))


class ChatRunRequest(BaseModel):
    content: str | None = None
    model_id: UUID | None = None
    parent_message_id: UUID | None = None
    supersedes_message_id: UUID | None = None
    regenerate_from_message_id: UUID | None = None
    thinking_enabled: bool = False
    context_asset_ids: tuple[UUID, ...] = ()

    def to_command(self) -> ChatRunCommand:
        return ChatRunCommand(**self.model_dump())
