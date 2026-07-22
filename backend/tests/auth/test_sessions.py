from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models.user_sessions import UserSession
from app.models.users import User
from app.services.auth_registration import AuthOperationError
from app.services.auth_security import PasswordService, RefreshTokenService, TokenCodec
from app.services.auth_sessions import AuthSessionService
from app.services.rate_limit import RateLimitExceeded


class CountingRateLimiter:
    def __init__(self) -> None:
        self.counts: dict[tuple[str, str], int] = {}

    async def check(
        self, scope: str, key: str, limit: int, window_seconds: int
    ) -> None:
        counter_key = (scope, key)
        self.counts[counter_key] = self.counts.get(counter_key, 0) + 1
        if self.counts[counter_key] > limit:
            raise RateLimitExceeded()


async def seed_user(
    session_factory,
    passwords: PasswordService,
    *,
    phone: str,
    password: str,
    role: str = "user",
) -> User:
    async with session_factory() as session, session.begin():
        user = User(
            phone_number=phone,
            password_hash=passwords.hash(password),
            role=role,
        )
        session.add(user)
    return user


def build_service(session_factory, limiter=None) -> AuthSessionService:
    return AuthSessionService(
        session_factory=session_factory,
        passwords=PasswordService(),
        refresh_tokens=RefreshTokenService(),
        token_codec=TokenCodec(
            "test-session-secret-with-enough-entropy", timedelta(minutes=15)
        ),
        rate_limiter=limiter or CountingRateLimiter(),
        refresh_ttl=timedelta(days=30),
    )


async def test_login_persists_only_refresh_hash_and_authenticates_access_token(
    session_factory,
) -> None:
    passwords = PasswordService()
    user = await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="correct-horse-battery-staple",
    )
    service = build_service(session_factory)

    tokens = await service.login(
        phone_number="13800138000",
        password="correct-horse-battery-staple",
        client_key="127.0.0.1",
        device_info="pytest",
        ip_address="127.0.0.1",
    )
    current_user = await service.authenticate_access(tokens.access_token)

    async with session_factory() as session:
        stored_session = await session.scalar(select(UserSession))

    assert current_user.user_id == user.id
    assert current_user.role == "user"
    assert tokens.refresh_token not in stored_session.refresh_token_hash
    assert len(stored_session.refresh_token_hash) == 64


async def test_refresh_rotates_token_and_rejects_replay(session_factory) -> None:
    passwords = PasswordService()
    await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="correct-horse-battery-staple",
    )
    service = build_service(session_factory)
    original = await service.login(
        "13800138000",
        "correct-horse-battery-staple",
        "127.0.0.1",
        "pytest",
        "127.0.0.1",
    )

    rotated = await service.refresh(original.refresh_token, "pytest", "127.0.0.1")

    assert rotated.refresh_token != original.refresh_token
    with pytest.raises(AuthOperationError) as error:
        await service.refresh(original.refresh_token, "pytest", "127.0.0.1")
    assert error.value.error_code == "refresh_token_invalid"


async def test_logout_revokes_current_session(session_factory) -> None:
    passwords = PasswordService()
    await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="correct-horse-battery-staple",
    )
    service = build_service(session_factory)
    tokens = await service.login(
        "13800138000",
        "correct-horse-battery-staple",
        "127.0.0.1",
        None,
        "127.0.0.1",
    )

    await service.logout(tokens.access_token)

    with pytest.raises(AuthOperationError) as error:
        await service.authenticate_access(tokens.access_token)
    assert error.value.error_code == "session_invalid"


async def test_change_password_revokes_old_sessions_and_issues_replacement(
    session_factory,
) -> None:
    passwords = PasswordService()
    user = await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="correct-horse-battery-staple",
    )
    service = build_service(session_factory)
    original = await service.login(
        "13800138000",
        "correct-horse-battery-staple",
        "127.0.0.1",
        "pytest",
        "127.0.0.1",
    )

    replacement = await service.change_password(
        original.access_token,
        "correct-horse-battery-staple",
        "new-correct-horse-battery-staple",
        "pytest",
        "127.0.0.1",
    )

    with pytest.raises(AuthOperationError):
        await service.authenticate_access(original.access_token)
    assert (
        await service.authenticate_access(replacement.access_token)
    ).user_id == user.id
    with pytest.raises(AuthOperationError) as error:
        await service.login(
            "13800138000",
            "correct-horse-battery-staple",
            "127.0.0.1",
            None,
            "127.0.0.1",
        )
    assert error.value.error_code == "invalid_credentials"


async def test_admin_reset_marks_force_change_and_revokes_target_sessions(
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
    target = await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="user-correct-horse-battery-staple",
    )
    service = build_service(session_factory)
    admin_tokens = await service.login(
        admin.phone_number,
        "admin-correct-horse-battery-staple",
        "admin-ip",
        None,
        "admin-ip",
    )
    target_tokens = await service.login(
        target.phone_number,
        "user-correct-horse-battery-staple",
        "user-ip",
        None,
        "user-ip",
    )

    await service.admin_reset_password(
        admin_tokens.access_token,
        target.id,
        "reset-correct-horse-battery-staple",
    )

    with pytest.raises(AuthOperationError):
        await service.authenticate_access(target_tokens.access_token)
    async with session_factory() as session:
        stored_target = await session.get(User, target.id)
    assert stored_target.must_change_password is True


async def test_login_failures_are_limited(session_factory) -> None:
    passwords = PasswordService()
    await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="correct-horse-battery-staple",
    )
    limiter = CountingRateLimiter()
    service = build_service(session_factory, limiter)

    for _ in range(5):
        with pytest.raises(AuthOperationError) as error:
            await service.login(
                "13800138000", "wrong-password", "127.0.0.1", None, "127.0.0.1"
            )
        assert error.value.error_code == "invalid_credentials"

    with pytest.raises(RateLimitExceeded):
        await service.login(
            "13800138000", "wrong-password", "127.0.0.1", None, "127.0.0.1"
        )

    async with session_factory() as session:
        session_count = await session.scalar(
            select(func.count()).select_from(UserSession)
        )
    assert session_count == 0


async def test_successful_logins_do_not_consume_failure_budget(session_factory) -> None:
    passwords = PasswordService()
    await seed_user(
        session_factory,
        passwords,
        phone="13800138000",
        password="correct-horse-battery-staple",
    )
    limiter = CountingRateLimiter()
    service = build_service(session_factory, limiter)

    for _ in range(6):
        await service.login(
            "13800138000",
            "correct-horse-battery-staple",
            "127.0.0.1",
            None,
            "127.0.0.1",
        )

    assert limiter.counts == {}
