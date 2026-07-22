from dataclasses import dataclass
from datetime import UTC, datetime
import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.invite_codes import InviteCode
from app.services.auth_registration import AuthOperationError
from app.services.auth_security import InviteCodeHasher
from app.services.auth_sessions import AuthSessionService


@dataclass(frozen=True)
class CreatedInvite:
    invite_id: UUID
    code: str
    code_prefix: str
    max_uses: int
    expires_at: datetime
    registration_credit: int


@dataclass(frozen=True)
class InviteSummary:
    invite_id: UUID
    code_prefix: str
    max_uses: int
    used_count: int
    expires_at: datetime
    status: str
    registration_credit: int


class InviteAdminService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        invite_codes: InviteCodeHasher,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._invite_codes = invite_codes

    async def create(
        self,
        admin_access_token: str,
        max_uses: int,
        expires_at: datetime,
        registration_credit: int,
    ) -> CreatedInvite:
        admin = await self._require_admin(admin_access_token)
        code = secrets.token_hex(6).upper()
        normalized_expiry = (
            expires_at.astimezone(UTC).replace(tzinfo=None)
            if expires_at.tzinfo is not None
            else expires_at
        )
        async with self._session_factory() as session, session.begin():
            invite = InviteCode(
                code_hash=self._invite_codes.hash(code),
                code_prefix=self._invite_codes.prefix(code),
                max_uses=max_uses,
                used_count=0,
                expires_at=normalized_expiry,
                status="active",
                registration_credit=registration_credit,
                created_by_user_id=admin.user_id,
            )
            session.add(invite)
        return CreatedInvite(
            invite_id=invite.id,
            code=code,
            code_prefix=invite.code_prefix,
            max_uses=invite.max_uses,
            expires_at=invite.expires_at,
            registration_credit=invite.registration_credit,
        )

    async def list(self, admin_access_token: str) -> list[InviteSummary]:
        await self._require_admin(admin_access_token)
        async with self._session_factory() as session:
            invites = list(
                await session.scalars(
                    select(InviteCode).order_by(InviteCode.created_at.desc())
                )
            )
        return [
            InviteSummary(
                invite_id=invite.id,
                code_prefix=invite.code_prefix,
                max_uses=invite.max_uses,
                used_count=invite.used_count,
                expires_at=invite.expires_at,
                status=invite.status,
                registration_credit=invite.registration_credit,
            )
            for invite in invites
        ]

    async def _require_admin(self, access_token: str):
        user = await self._sessions.authenticate_access(access_token)
        if user.role != "admin":
            raise AuthOperationError("admin_required", "需要管理员权限", 403)
        return user
