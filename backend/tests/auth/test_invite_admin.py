from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.base import utc_now
from app.models.invite_codes import InviteCode
from app.services.auth_invites import InviteAdminService
from app.services.auth_registration import AuthOperationError
from app.services.auth_security import InviteCodeHasher, PasswordService
from app.services.auth_sessions import AuthSessionService
from tests.auth.test_sessions import build_service, seed_user


async def test_admin_creates_invite_without_persisting_plaintext(
    session_factory,
) -> None:
    passwords = PasswordService()
    admin = await seed_user(
        session_factory,
        passwords,
        phone="13900139000",
        password="admin-correct-horse-battery-staple",
        role="admin",
    )
    sessions: AuthSessionService = build_service(session_factory)
    admin_tokens = await sessions.login(
        admin.phone_number,
        "admin-correct-horse-battery-staple",
        "admin-ip",
        None,
        "admin-ip",
    )
    invite_codes = InviteCodeHasher("test-session-secret-with-enough-entropy")
    service = InviteAdminService(session_factory, sessions, invite_codes)

    created = await service.create(
        admin_tokens.access_token,
        max_uses=3,
        expires_at=utc_now() + timedelta(days=7),
        registration_credit=120,
    )
    listed = await service.list(admin_tokens.access_token)

    async with session_factory() as session:
        stored = await session.scalar(select(InviteCode))

    assert created.code
    assert created.code not in stored.code_hash
    assert stored.code_hash == invite_codes.hash(created.code)
    assert stored.created_by_user_id == admin.id
    assert listed[0].code_prefix == created.code_prefix
    assert not hasattr(listed[0], "code")


async def test_non_admin_cannot_manage_invites(session_factory) -> None:
    passwords = PasswordService()
    user = await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="user-correct-horse-battery-staple",
    )
    sessions = build_service(session_factory)
    tokens = await sessions.login(
        user.phone_number,
        "user-correct-horse-battery-staple",
        "user-ip",
        None,
        "user-ip",
    )
    service = InviteAdminService(
        session_factory,
        sessions,
        InviteCodeHasher("test-session-secret-with-enough-entropy"),
    )

    with pytest.raises(AuthOperationError) as error:
        await service.list(tokens.access_token)

    assert error.value.error_code == "admin_required"


async def test_invite_expiry_is_normalized_to_naive_utc_for_mysql(
    session_factory,
) -> None:
    passwords = PasswordService()
    admin = await seed_user(
        session_factory,
        passwords,
        phone="13900139000",
        password="admin-correct-horse-battery-staple",
        role="admin",
    )
    sessions = build_service(session_factory)
    tokens = await sessions.login(
        admin.phone_number,
        "admin-correct-horse-battery-staple",
        "admin-ip",
        None,
        "admin-ip",
    )
    service = InviteAdminService(
        session_factory,
        sessions,
        InviteCodeHasher("test-session-secret-with-enough-entropy"),
    )

    created = await service.create(
        tokens.access_token,
        max_uses=1,
        expires_at=datetime(2026, 7, 30, 8, 0, tzinfo=UTC),
        registration_credit=0,
    )

    assert created.expires_at == datetime(2026, 7, 30, 8, 0)
    assert created.expires_at.tzinfo is None
