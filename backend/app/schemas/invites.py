from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class InviteCreateRequest(BaseModel):
    max_uses: int = Field(ge=1, le=10_000)
    expires_at: datetime
    registration_credit: int = Field(ge=0, le=1_000_000)


class InviteCreatedResponse(BaseModel):
    invite_id: UUID
    code: str
    code_prefix: str
    max_uses: int
    expires_at: datetime
    registration_credit: int


class InviteSummaryResponse(BaseModel):
    invite_id: UUID
    code_prefix: str
    max_uses: int
    used_count: int
    expires_at: datetime
    status: str
    registration_credit: int
