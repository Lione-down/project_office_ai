from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, func, select

from app.models.credit_ledger import CreditLedger
from app.models.invite_codes import InviteCode
from app.models.users import User
from app.services.auth_registration import AuthOperationError, RegistrationService
from app.services.auth_security import InviteCodeHasher, PasswordService


SESSION_SECRET = "test-session-secret-with-enough-entropy"


class AllowAllRateLimiter:
    async def check(
        self, scope: str, key: str, limit: int, window_seconds: int
    ) -> None:
        return None


async def seed_invite(
    session_factory,
    *,
    code: str = "ALPHA-2026",
    status: str = "active",
    expires_at: datetime | None = None,
    max_uses: int = 2,
    used_count: int = 0,
    credit: int = 100,
) -> InviteCode:
    hasher = InviteCodeHasher(SESSION_SECRET)
    async with session_factory() as session, session.begin():
        invite = InviteCode(
            code_hash=hasher.hash(code),
            code_prefix=hasher.prefix(code),
            status=status,
            expires_at=expires_at or datetime.now(UTC) + timedelta(days=1),
            max_uses=max_uses,
            used_count=used_count,
            registration_credit=credit,
        )
        session.add(invite)
    return invite


def build_service(session_factory) -> RegistrationService:
    return RegistrationService(
        session_factory=session_factory,
        passwords=PasswordService(),
        invite_codes=InviteCodeHasher(SESSION_SECRET),
        rate_limiter=AllowAllRateLimiter(),
    )


async def test_registration_consumes_invite_and_grants_credit_atomically(
    session_factory,
) -> None:
    invite = await seed_invite(session_factory, credit=120)
    service = build_service(session_factory)

    registered = await service.register(
        phone_number="13800138000",
        password="correct-horse-battery-staple",
        invite_code="alpha-2026",
        client_key="127.0.0.1",
    )

    async with session_factory() as session:
        user = await session.scalar(select(User))
        ledger = await session.scalar(select(CreditLedger))
        stored_invite = await session.get(InviteCode, invite.id)

    assert registered.user_id == user.id
    assert user.phone_country_code == "+86"
    assert user.phone_number == "13800138000"
    assert user.credit_balance == 120
    assert user.password_hash != "correct-horse-battery-staple"
    assert user.password_hash.startswith("$argon2id$")
    assert ledger.entry_type == "registration_grant"
    assert ledger.amount == 120
    assert ledger.balance_after == 120
    assert stored_invite.used_count == 1


async def test_registration_rejects_duplicate_phone_with_stable_error(
    session_factory,
) -> None:
    await seed_invite(session_factory)
    service = build_service(session_factory)
    registration = {
        "phone_number": "13800138000",
        "password": "correct-horse-battery-staple",
        "invite_code": "ALPHA-2026",
        "client_key": "127.0.0.1",
    }
    await service.register(**registration)

    with pytest.raises(AuthOperationError, match="phone_already_registered") as error:
        await service.register(**registration)

    assert error.value.error_code == "phone_already_registered"


@pytest.mark.parametrize(
    ("invite_kwargs", "error_code"),
    [
        ({"status": "disabled"}, "invite_invalid"),
        ({"expires_at": datetime.now(UTC) - timedelta(seconds=1)}, "invite_expired"),
        ({"max_uses": 1, "used_count": 1}, "invite_exhausted"),
    ],
)
async def test_registration_rejects_unusable_invites(
    session_factory, invite_kwargs: dict[str, object], error_code: str
) -> None:
    await seed_invite(session_factory, **invite_kwargs)
    service = build_service(session_factory)

    with pytest.raises(AuthOperationError) as error:
        await service.register(
            phone_number="13800138000",
            password="correct-horse-battery-staple",
            invite_code="ALPHA-2026",
            client_key="127.0.0.1",
        )

    assert error.value.error_code == error_code


async def test_registration_rejects_unknown_invite(session_factory) -> None:
    service = build_service(session_factory)

    with pytest.raises(AuthOperationError) as error:
        await service.register(
            phone_number="13800138000",
            password="correct-horse-battery-staple",
            invite_code="UNKNOWN",
            client_key="127.0.0.1",
        )

    assert error.value.error_code == "invite_invalid"


async def test_registration_rolls_back_user_invite_and_credit_on_ledger_failure(
    session_factory,
) -> None:
    invite = await seed_invite(session_factory)
    service = build_service(session_factory)

    def fail_ledger_insert(*_args) -> None:
        raise RuntimeError("simulated ledger failure")

    event.listen(CreditLedger, "before_insert", fail_ledger_insert)
    try:
        with pytest.raises(RuntimeError, match="simulated ledger failure"):
            await service.register(
                phone_number="13800138000",
                password="correct-horse-battery-staple",
                invite_code="ALPHA-2026",
                client_key="127.0.0.1",
            )
    finally:
        event.remove(CreditLedger, "before_insert", fail_ledger_insert)

    async with session_factory() as session:
        user_count = await session.scalar(select(func.count()).select_from(User))
        ledger_count = await session.scalar(
            select(func.count()).select_from(CreditLedger)
        )
        stored_invite = await session.get(InviteCode, invite.id)

    assert user_count == 0
    assert ledger_count == 0
    assert stored_invite.used_count == 0
