from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SensitiveOperationRequest(StrictModel):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    reason: str = Field(max_length=500)


class PasswordResetRequest(SensitiveOperationRequest):
    new_password: SecretStr = Field(min_length=12, max_length=128)


class UserStatusRequest(SensitiveOperationRequest):
    status: str


class CreditAdjustmentRequest(SensitiveOperationRequest):
    user_id: UUID
    amount: int = Field(ge=-1_000_000, le=1_000_000)


class AdminUserResponse(StrictModel):
    user_id: UUID
    masked_phone: str
    role: str
    status: str
    credit_balance: int
    must_change_password: bool
    created_at: datetime


class AdminAssetResponse(StrictModel):
    asset_id: UUID
    owner_user_id: UUID
    project_id: UUID
    original_filename: str
    file_category: str
    mime_type: str
    byte_size: int
    sha256: str
    processing_status: str
    created_at: datetime


class CreditAdjustmentResponse(StrictModel):
    ledger_id: UUID
    user_id: UUID
    amount: int
    balance_after: int


class AuditLogResponse(StrictModel):
    audit_id: UUID
    actor_user_id: UUID | None
    action: str
    target_type: str
    target_id: UUID | None
    ip_address: str | None
    user_agent: str | None
    reason: str
    result: str
    context: dict
    trace_id: str
    created_at: datetime
