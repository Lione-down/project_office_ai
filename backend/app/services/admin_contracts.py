from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class AdminOperationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class AdminUserSummary:
    user_id: UUID
    masked_phone: str
    role: str
    status: str
    credit_balance: int
    must_change_password: bool
    created_at: datetime


@dataclass(frozen=True)
class AdminAssetSummary:
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


@dataclass(frozen=True)
class CreditAdjustmentResult:
    ledger_id: UUID
    user_id: UUID
    amount: int
    balance_after: int


@dataclass(frozen=True)
class AuditLogSummary:
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
