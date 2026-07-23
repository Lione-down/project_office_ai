from dataclasses import dataclass
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.audit_logs import AuditLog
from app.models.credit_ledger import CreditLedger
from app.models.users import User
from app.services.admin_contracts import AdminOperationError
from app.services.admin_operations import AdminOperationsService
from app.services.audit import AuditContext
from app.services.auth_security import PasswordService
from app.services.auth_sessions import CurrentUser


ADMIN_ID = UUID("019f0000-0000-7000-8000-000000000901")
USER_ID = UUID("019f0000-0000-7000-8000-000000000902")
ADMIN_PASSWORD = "admin-current-password"


@dataclass
class FakeSessions:
    async def authenticate_access(self, access_token: str) -> CurrentUser:
        identities = {
            "admin-token": (ADMIN_ID, "admin"),
            "user-token": (USER_ID, "user"),
        }
        user_id, role = identities[access_token]
        return CurrentUser(
            user_id=user_id,
            phone_country_code="+86",
            phone_number="13800138000",
            role=role,
            status="active",
            credit_balance=0,
            must_change_password=False,
        )


@pytest.fixture
async def admin_service(session_factory):
    passwords = PasswordService()
    async with session_factory() as session, session.begin():
        session.add_all(
            (
                User(
                    id=ADMIN_ID,
                    phone_number="13800138000",
                    password_hash=passwords.hash(ADMIN_PASSWORD),
                    role="admin",
                ),
                User(
                    id=USER_ID,
                    phone_number="13800138001",
                    password_hash=passwords.hash("user-current-password"),
                    credit_balance=100,
                ),
            )
        )
    return AdminOperationsService(
        session_factory,
        FakeSessions(),
        passwords,
        asset_service=None,
    )


def audit_context() -> AuditContext:
    return AuditContext(
        ip_address="203.0.113.42",
        user_agent="pytest-admin-browser",
        trace_id="trace-admin-operation",
    )


async def test_admin_user_mutations_require_reason_and_current_password_and_audit_failures(
    admin_service, session_factory
) -> None:
    with pytest.raises(AdminOperationError) as missing_reason:
        await admin_service.change_user_status(
            access_token="admin-token",
            target_user_id=USER_ID,
            status="suspended",
            current_password=ADMIN_PASSWORD,
            reason=" ",
            audit=audit_context(),
        )
    assert missing_reason.value.error_code == "reason_required"

    with pytest.raises(AdminOperationError) as failed_reauth:
        await admin_service.change_user_status(
            access_token="admin-token",
            target_user_id=USER_ID,
            status="suspended",
            current_password="wrong-password",
            reason="安全事件处置",
            audit=audit_context(),
        )
    assert failed_reauth.value.error_code == "reauthentication_failed"

    async with session_factory() as session:
        audits = list(
            await session.scalars(
                select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)
            )
        )
        user = await session.get(User, USER_ID)
    assert user.status == "active"
    assert [item.result for item in audits] == ["failed", "failed"]
    assert all("password" not in str(item.context).lower() for item in audits)
    assert all(item.ip_address != "203.0.113.42" for item in audits)


async def test_admin_reset_status_and_credit_adjustment_are_audited_and_append_only(
    admin_service, session_factory
) -> None:
    await admin_service.change_user_status(
        access_token="admin-token",
        target_user_id=USER_ID,
        status="suspended",
        current_password=ADMIN_PASSWORD,
        reason="账号风险复核",
        audit=audit_context(),
    )
    await admin_service.reset_password(
        access_token="admin-token",
        target_user_id=USER_ID,
        new_password="temporary-password-2026",
        current_password=ADMIN_PASSWORD,
        reason="用户本人申请",
        audit=audit_context(),
    )
    adjusted = await admin_service.adjust_credits(
        access_token="admin-token",
        target_user_id=USER_ID,
        amount=25,
        current_password=ADMIN_PASSWORD,
        reason="活动补发",
        idempotency_key="credit-adjustment-1",
        audit=audit_context(),
    )
    replay = await admin_service.adjust_credits(
        access_token="admin-token",
        target_user_id=USER_ID,
        amount=25,
        current_password=ADMIN_PASSWORD,
        reason="活动补发",
        idempotency_key="credit-adjustment-1",
        audit=audit_context(),
    )

    async with session_factory() as session:
        user = await session.get(User, USER_ID)
        ledger = list(await session.scalars(select(CreditLedger)))
        audits = list(await session.scalars(select(AuditLog)))
    assert user.status == "suspended"
    assert user.must_change_password is True
    assert user.credit_balance == 125
    assert adjusted.ledger_id == replay.ledger_id
    assert len(ledger) == 1
    assert ledger[0].entry_type == "admin_grant"
    assert {item.action for item in audits} >= {
        "user.status_changed",
        "user.password_reset",
        "credit.adjusted",
    }


async def test_regular_user_is_denied_without_forging_admin_audit(
    admin_service, session_factory
) -> None:
    with pytest.raises(AdminOperationError) as denied:
        await admin_service.adjust_credits(
            access_token="user-token",
            target_user_id=USER_ID,
            amount=25,
            current_password="user-current-password",
            reason="越权尝试",
            idempotency_key="forbidden-adjustment",
            audit=audit_context(),
        )
    assert denied.value.error_code == "admin_required"
    async with session_factory() as session:
        assert await session.scalar(select(AuditLog.id)) is None


async def test_missing_target_business_failure_commits_failure_audit(
    admin_service, session_factory
) -> None:
    missing_user_id = UUID("019f0000-0000-7000-8000-000000000999")
    with pytest.raises(AdminOperationError) as missing:
        await admin_service.reset_password(
            access_token="admin-token",
            target_user_id=missing_user_id,
            new_password="temporary-password-2026",
            current_password=ADMIN_PASSWORD,
            reason="用户身份核查",
            audit=audit_context(),
        )
    assert missing.value.error_code == "user_not_found"
    async with session_factory() as session:
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.target_id == missing_user_id)
        )
    assert audit is not None
    assert audit.action == "user.password_reset"
    assert audit.result == "failed"
