from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.base import utc_now
from app.models.credit_ledger import CreditLedger
from app.models.invite_codes import InviteCode
from app.models.users import User
from app.services.auth_security import InviteCodeHasher, PasswordService


class RateLimiter(Protocol):
    async def check(
        self, scope: str, key: str, limit: int, window_seconds: int
    ) -> None: ...


class AuthOperationError(ValueError):
    def __init__(self, error_code: str, message: str, status_code: int = 400) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RegisteredUser:
    user_id: UUID


class RegistrationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        passwords: PasswordService,
        invite_codes: InviteCodeHasher,
        rate_limiter: RateLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._passwords = passwords
        self._invite_codes = invite_codes
        self._rate_limiter = rate_limiter

    async def register(
        self,
        phone_number: str,
        password: str,
        invite_code: str,
        client_key: str,
    ) -> RegisteredUser:
        await self._rate_limiter.check("register", client_key, 10, 3600)
        await self._rate_limiter.check(
            "invite", self._invite_codes.hash(invite_code), 20, 3600
        )
        try:
            async with self._session_factory() as session, session.begin():
                existing_user = await session.scalar(
                    select(User).where(
                        User.phone_country_code == "+86",
                        User.phone_number == phone_number,
                    )
                )
                if existing_user is not None:
                    raise AuthOperationError(
                        "phone_already_registered", "该手机号已注册", 409
                    )

                invite = await session.scalar(
                    select(InviteCode)
                    .where(InviteCode.code_hash == self._invite_codes.hash(invite_code))
                    .with_for_update()
                )
                self._validate_invite(invite, utc_now())

                user = User(
                    phone_country_code="+86",
                    phone_number=phone_number,
                    password_hash=self._passwords.hash(password),
                    invite_code_id=invite.id,
                    credit_balance=invite.registration_credit,
                )
                invite.used_count += 1
                session.add(user)
                await session.flush()
                session.add(
                    CreditLedger(
                        user_id=user.id,
                        entry_type="registration_grant",
                        amount=invite.registration_credit,
                        balance_after=invite.registration_credit,
                        idempotency_key=f"registration:{user.id}",
                        description="邀请码注册赠送",
                    )
                )
                await session.flush()
            return RegisteredUser(user_id=user.id)
        except IntegrityError as exception:
            raise AuthOperationError(
                "phone_already_registered", "该手机号已注册", 409
            ) from exception

    @staticmethod
    def _validate_invite(invite: InviteCode | None, now: datetime) -> None:
        if invite is None or invite.status != "active":
            raise AuthOperationError("invite_invalid", "邀请码无效")
        if invite.expires_at <= now:
            raise AuthOperationError("invite_expired", "邀请码已过期")
        if invite.used_count >= invite.max_uses:
            raise AuthOperationError("invite_exhausted", "邀请码次数已用尽")
