from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.user_sessions import UserSession
from app.models.users import User
from app.services.auth_registration import AuthOperationError, RateLimiter
from app.services.auth_security import (
    AccessTokenInvalidError,
    PasswordService,
    RefreshTokenService,
    TokenCodec,
)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    phone_country_code: str
    phone_number: str
    role: str
    status: str
    credit_balance: int
    must_change_password: bool


class AuthSessionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        passwords: PasswordService,
        refresh_tokens: RefreshTokenService,
        token_codec: TokenCodec,
        rate_limiter: RateLimiter,
        refresh_ttl: timedelta,
    ) -> None:
        self._session_factory = session_factory
        self._passwords = passwords
        self._refresh_tokens = refresh_tokens
        self._token_codec = token_codec
        self._rate_limiter = rate_limiter
        self._refresh_ttl = refresh_ttl

    async def login(
        self,
        phone_number: str,
        password: str,
        client_key: str,
        device_info: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        async with self._session_factory() as session, session.begin():
            user = await session.scalar(
                select(User).where(
                    User.phone_country_code == "+86",
                    User.phone_number == phone_number,
                )
            )
            if (
                user is None
                or user.status != "active"
                or not self._passwords.verify(user.password_hash, password)
            ):
                await self._rate_limiter.check(
                    "login", f"{phone_number}:{client_key}", 5, 900
                )
                raise AuthOperationError("invalid_credentials", "手机号或密码错误", 401)
            return await self._create_session(
                session, user, device_info=device_info, ip_address=ip_address
            )

    async def authenticate_access(self, access_token: str) -> CurrentUser:
        claims = self._decode_access_token(access_token)
        async with self._session_factory() as session:
            stored_session = await session.get(UserSession, UUID(claims.session_id))
            if not self._session_is_active(stored_session):
                raise AuthOperationError("session_invalid", "Session 已失效", 401)
            user = await session.get(User, UUID(claims.user_id))
            if (
                user is None
                or user.id != stored_session.user_id
                or user.status != "active"
            ):
                raise AuthOperationError("session_invalid", "Session 已失效", 401)
            return self._to_current_user(user)

    async def refresh(
        self, refresh_token: str, device_info: str | None, ip_address: str | None
    ) -> TokenPair:
        refresh_hash = self._refresh_tokens.hash(refresh_token)
        async with self._session_factory() as session, session.begin():
            stored_session = await session.scalar(
                select(UserSession)
                .where(UserSession.refresh_token_hash == refresh_hash)
                .with_for_update()
            )
            if not self._session_is_active(stored_session):
                raise AuthOperationError(
                    "refresh_token_invalid", "Refresh Token 无效", 401
                )
            user = await session.get(User, stored_session.user_id)
            if user is None or user.status != "active":
                raise AuthOperationError(
                    "refresh_token_invalid", "Refresh Token 无效", 401
                )
            new_refresh_token = self._refresh_tokens.issue()
            stored_session.refresh_token_hash = self._refresh_tokens.hash(
                new_refresh_token
            )
            stored_session.expires_at = utc_now() + self._refresh_ttl
            stored_session.device_info = device_info
            stored_session.ip_address = ip_address
            access_token = self._token_codec.issue_access_token(
                str(user.id), str(stored_session.id)
            )
            return TokenPair(access_token, new_refresh_token)

    async def logout(self, access_token: str) -> None:
        claims = self._decode_access_token(access_token)
        async with self._session_factory() as session, session.begin():
            stored_session = await session.get(UserSession, UUID(claims.session_id))
            if not self._session_is_active(stored_session):
                raise AuthOperationError("session_invalid", "Session 已失效", 401)
            stored_session.revoked_at = utc_now()
            stored_session.revocation_reason = "logout"

    async def change_password(
        self,
        access_token: str,
        current_password: str,
        new_password: str,
        device_info: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        claims = self._decode_access_token(access_token)
        async with self._session_factory() as session, session.begin():
            user, stored_session = await self._load_authenticated_for_update(
                session, claims.user_id, claims.session_id
            )
            if not self._passwords.verify(user.password_hash, current_password):
                raise AuthOperationError(
                    "current_password_invalid", "当前密码错误", 401
                )
            user.password_hash = self._passwords.hash(new_password)
            user.must_change_password = False
            await self._revoke_user_sessions(session, user.id, "password_changed")
            return await self._create_session(
                session, user, device_info=device_info, ip_address=ip_address
            )

    async def admin_reset_password(
        self, admin_access_token: str, target_user_id: UUID, new_password: str
    ) -> None:
        claims = self._decode_access_token(admin_access_token)
        async with self._session_factory() as session, session.begin():
            admin, _ = await self._load_authenticated_for_update(
                session, claims.user_id, claims.session_id
            )
            if admin.role != "admin":
                raise AuthOperationError("admin_required", "需要管理员权限", 403)
            target = await session.get(User, target_user_id, with_for_update=True)
            if target is None:
                raise AuthOperationError("user_not_found", "用户不存在", 404)
            target.password_hash = self._passwords.hash(new_password)
            target.must_change_password = True
            await self._revoke_user_sessions(session, target.id, "admin_password_reset")

    async def _create_session(
        self,
        session: AsyncSession,
        user: User,
        device_info: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        refresh_token = self._refresh_tokens.issue()
        stored_session = UserSession(
            user_id=user.id,
            refresh_token_hash=self._refresh_tokens.hash(refresh_token),
            device_info=device_info,
            ip_address=ip_address,
            expires_at=utc_now() + self._refresh_ttl,
        )
        session.add(stored_session)
        await session.flush()
        access_token = self._token_codec.issue_access_token(
            str(user.id), str(stored_session.id)
        )
        return TokenPair(access_token, refresh_token)

    def _decode_access_token(self, access_token: str):
        try:
            return self._token_codec.decode_access_token(access_token)
        except (AccessTokenInvalidError, ValueError) as exception:
            raise AuthOperationError(
                "session_invalid", "Session 已失效", 401
            ) from exception

    @staticmethod
    def _session_is_active(stored_session: UserSession | None) -> bool:
        return (
            stored_session is not None
            and stored_session.revoked_at is None
            and stored_session.expires_at > utc_now()
        )

    async def _load_authenticated_for_update(
        self, session: AsyncSession, user_id: str, session_id: str
    ) -> tuple[User, UserSession]:
        stored_session = await session.get(
            UserSession, UUID(session_id), with_for_update=True
        )
        if not self._session_is_active(stored_session):
            raise AuthOperationError("session_invalid", "Session 已失效", 401)
        user = await session.get(User, UUID(user_id), with_for_update=True)
        if user is None or user.id != stored_session.user_id or user.status != "active":
            raise AuthOperationError("session_invalid", "Session 已失效", 401)
        return user, stored_session

    @staticmethod
    async def _revoke_user_sessions(
        session: AsyncSession, user_id: UUID, reason: str
    ) -> None:
        await session.execute(
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=utc_now(), revocation_reason=reason)
        )

    @staticmethod
    def _to_current_user(user: User) -> CurrentUser:
        return CurrentUser(
            user_id=user.id,
            phone_country_code=user.phone_country_code,
            phone_number=user.phone_number,
            role=user.role,
            status=user.status,
            credit_balance=user.credit_balance,
            must_change_password=user.must_change_password,
        )
