from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.audit_logs import AuditLog
from app.models.base import utc_now
from app.models.credit_ledger import CreditLedger
from app.models.file_assets import FileAsset
from app.models.user_sessions import UserSession
from app.models.users import User
from app.services.admin_contracts import (
    AdminAssetSummary,
    AdminOperationError,
    AdminUserSummary,
    AuditLogSummary,
    CreditAdjustmentResult,
)
from app.services.asset_contracts import AssetAuditContext
from app.services.audit import (
    AuditContext,
    redact_audit_context,
    summarize_ip,
    summarize_user_agent,
)
from app.services.auth_security import PasswordService
from app.services.auth_sessions import AuthSessionService, CurrentUser


class AdminOperationsService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        passwords: PasswordService,
        asset_service,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._passwords = passwords
        self._assets = asset_service

    async def list_users(self, access_token: str) -> list[AdminUserSummary]:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            users = (
                await session.scalars(select(User).order_by(User.created_at, User.id))
            ).all()
        return [
            AdminUserSummary(
                user.id,
                self._mask_phone(user.phone_country_code, user.phone_number),
                user.role,
                user.status,
                user.credit_balance,
                user.must_change_password,
                user.created_at,
            )
            for user in users
        ]

    async def list_assets(self, access_token: str) -> list[AdminAssetSummary]:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            assets = (
                await session.scalars(
                    select(FileAsset)
                    .where(FileAsset.deleted_at.is_(None))
                    .order_by(FileAsset.created_at, FileAsset.id)
                )
            ).all()
        return [
            AdminAssetSummary(
                asset.id,
                asset.user_id,
                asset.project_id,
                asset.original_filename,
                asset.file_category,
                asset.mime_type,
                asset.byte_size,
                asset.sha256,
                asset.processing_status,
                asset.created_at,
            )
            for asset in assets
        ]

    async def reset_password(
        self,
        *,
        access_token: str,
        target_user_id: UUID,
        new_password: str,
        current_password: str,
        reason: str,
        audit: AuditContext,
    ) -> None:
        admin, normalized_reason = await self._reauthenticate(
            access_token,
            current_password,
            reason,
            "user.password_reset",
            "user",
            target_user_id,
            audit,
        )
        async with self._session_factory() as session, session.begin():
            target = await session.get(User, target_user_id, with_for_update=True)
            if target is not None:
                target.password_hash = self._passwords.hash(new_password)
                target.must_change_password = True
                await session.execute(
                    update(UserSession)
                    .where(
                        UserSession.user_id == target.id,
                        UserSession.revoked_at.is_(None),
                    )
                    .values(
                        revoked_at=utc_now(),
                        revocation_reason="admin_password_reset",
                    )
                )
                await self._add_audit(
                    session,
                    admin,
                    "user.password_reset",
                    "user",
                    target.id,
                    normalized_reason,
                    "success",
                    audit,
                    {},
                )
        if target is None:
            await self._write_audit(
                admin,
                "user.password_reset",
                "user",
                target_user_id,
                normalized_reason,
                "failed",
                audit,
                {},
            )
            raise AdminOperationError("user_not_found", "用户不存在", 404)

    async def change_user_status(
        self,
        *,
        access_token: str,
        target_user_id: UUID,
        status: str,
        current_password: str,
        reason: str,
        audit: AuditContext,
    ) -> None:
        if status not in {"active", "suspended"}:
            raise AdminOperationError("user_status_invalid", "用户状态无效", 422)
        admin, normalized_reason = await self._reauthenticate(
            access_token,
            current_password,
            reason,
            "user.status_changed",
            "user",
            target_user_id,
            audit,
        )
        if admin.user_id == target_user_id and status != "active":
            await self._write_audit(
                admin,
                "user.status_changed",
                "user",
                target_user_id,
                normalized_reason,
                "failed",
                audit,
                {"to_status": status},
            )
            raise AdminOperationError(
                "admin_self_suspend_forbidden", "不能停用当前管理员", 409
            )
        async with self._session_factory() as session, session.begin():
            target = await session.get(User, target_user_id, with_for_update=True)
            if target is not None:
                previous = target.status
                target.status = status
                if status != "active":
                    await session.execute(
                        update(UserSession)
                        .where(
                            UserSession.user_id == target.id,
                            UserSession.revoked_at.is_(None),
                        )
                        .values(
                            revoked_at=utc_now(),
                            revocation_reason="admin_user_suspended",
                        )
                    )
                await self._add_audit(
                    session,
                    admin,
                    "user.status_changed",
                    "user",
                    target.id,
                    normalized_reason,
                    "success",
                    audit,
                    {"from_status": previous, "to_status": status},
                )
        if target is None:
            await self._write_audit(
                admin,
                "user.status_changed",
                "user",
                target_user_id,
                normalized_reason,
                "failed",
                audit,
                {"to_status": status},
            )
            raise AdminOperationError("user_not_found", "用户不存在", 404)

    async def adjust_credits(
        self,
        *,
        access_token: str,
        target_user_id: UUID,
        amount: int,
        current_password: str,
        reason: str,
        idempotency_key: str,
        audit: AuditContext,
    ) -> CreditAdjustmentResult:
        if amount == 0:
            raise AdminOperationError("credit_amount_invalid", "积分调整不能为零", 422)
        admin, normalized_reason = await self._reauthenticate(
            access_token,
            current_password,
            reason,
            "credit.adjusted",
            "user",
            target_user_id,
            audit,
        )
        failure: AdminOperationError | None = None
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(CreditLedger).where(
                    CreditLedger.user_id == target_user_id,
                    CreditLedger.idempotency_key == idempotency_key,
                    CreditLedger.entry_type == "admin_grant",
                )
            )
            if existing is not None:
                return self._credit_result(existing)
            target = await session.get(User, target_user_id, with_for_update=True)
            if target is None:
                failure = AdminOperationError("user_not_found", "用户不存在", 404)
            elif target.credit_balance + amount < 0:
                failure = AdminOperationError(
                    "credit_balance_insufficient", "积分余额不足", 409
                )
            else:
                target.credit_balance += amount
                ledger = CreditLedger(
                    user_id=target.id,
                    task_id=None,
                    entry_type="admin_grant",
                    amount=amount,
                    balance_after=target.credit_balance,
                    related_entry_id=None,
                    idempotency_key=idempotency_key,
                    description=normalized_reason,
                )
                session.add(ledger)
                await session.flush()
                await self._add_audit(
                    session,
                    admin,
                    "credit.adjusted",
                    "user",
                    target.id,
                    normalized_reason,
                    "success",
                    audit,
                    {"amount": amount, "idempotency_key": idempotency_key},
                )
        if failure is not None:
            await self._write_audit(
                admin,
                "credit.adjusted",
                "user",
                target_user_id,
                normalized_reason,
                "failed",
                audit,
                {"amount": amount},
            )
            raise failure
        return self._credit_result(ledger)

    async def open_asset(
        self,
        *,
        access_token: str,
        asset_id: UUID,
        current_password: str,
        reason: str,
        action: str,
        audit: AuditContext,
    ):
        if action not in {"preview", "download"}:
            raise AdminOperationError("asset_action_invalid", "资产操作无效", 422)
        await self._reauthenticate(
            access_token,
            current_password,
            reason,
            f"asset.{action}",
            "file_asset",
            asset_id,
            audit,
        )
        self._require_asset_service()
        return await self._assets.admin_open_asset(
            access_token=access_token,
            asset_id=asset_id,
            reason=reason,
            action=action,
            audit=AssetAuditContext(audit.ip_address, audit.user_agent, audit.trace_id),
        )

    async def delete_asset(
        self,
        *,
        access_token: str,
        asset_id: UUID,
        current_password: str,
        reason: str,
        audit: AuditContext,
    ) -> None:
        await self._reauthenticate(
            access_token,
            current_password,
            reason,
            "asset.deleted",
            "file_asset",
            asset_id,
            audit,
        )
        self._require_asset_service()
        await self._assets.admin_delete_asset(
            access_token=access_token,
            asset_id=asset_id,
            reason=reason,
            audit=AssetAuditContext(audit.ip_address, audit.user_agent, audit.trace_id),
        )

    async def list_audit_logs(self, access_token: str) -> list[AuditLogSummary]:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            entries = (
                await session.scalars(
                    select(AuditLog).order_by(
                        AuditLog.created_at.desc(), AuditLog.id.desc()
                    )
                )
            ).all()
        return [
            AuditLogSummary(
                item.id,
                item.actor_user_id,
                item.action,
                item.target_type,
                item.target_id,
                item.ip_address,
                item.user_agent,
                item.reason,
                item.result,
                redact_audit_context(item.context),
                item.trace_id,
                item.created_at,
            )
            for item in entries
        ]

    async def _reauthenticate(
        self,
        access_token: str,
        current_password: str,
        reason: str,
        action: str,
        target_type: str,
        target_id: UUID,
        audit: AuditContext,
    ) -> tuple[CurrentUser, str]:
        admin = await self._require_admin(access_token)
        normalized_reason = reason.strip()
        if not normalized_reason:
            await self._write_audit(
                admin, action, target_type, target_id, "", "failed", audit, {}
            )
            raise AdminOperationError("reason_required", "敏感操作必须填写原因", 422)
        async with self._session_factory() as session:
            stored = await session.get(User, admin.user_id)
        if stored is None or not self._passwords.verify(
            stored.password_hash, current_password
        ):
            await self._write_audit(
                admin,
                action,
                target_type,
                target_id,
                normalized_reason,
                "failed",
                audit,
                {},
            )
            raise AdminOperationError("reauthentication_failed", "重新认证失败", 401)
        return admin, normalized_reason[:500]

    async def _require_admin(self, access_token: str) -> CurrentUser:
        current = await self._sessions.authenticate_access(access_token)
        if current.role != "admin":
            raise AdminOperationError("admin_required", "需要管理员权限", 403)
        return current

    async def _write_audit(
        self,
        admin: CurrentUser,
        action: str,
        target_type: str,
        target_id: UUID,
        reason: str,
        result: str,
        audit: AuditContext,
        context: dict,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await self._add_audit(
                session,
                admin,
                action,
                target_type,
                target_id,
                reason,
                result,
                audit,
                context,
            )

    @staticmethod
    async def _add_audit(
        session: AsyncSession,
        admin: CurrentUser,
        action: str,
        target_type: str,
        target_id: UUID,
        reason: str,
        result: str,
        audit: AuditContext,
        context: dict,
    ) -> None:
        session.add(
            AuditLog(
                actor_user_id=admin.user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                ip_address=summarize_ip(audit.ip_address),
                user_agent=summarize_user_agent(audit.user_agent),
                reason=reason[:500],
                result=result,
                context=redact_audit_context(context),
                trace_id=audit.trace_id[:64],
            )
        )

    def _require_asset_service(self) -> None:
        if self._assets is None:
            raise AdminOperationError("asset_not_configured", "资产服务未配置", 503)

    @staticmethod
    def _mask_phone(country_code: str, number: str) -> str:
        masked = f"{number[:3]}****{number[-4:]}" if len(number) >= 7 else "****"
        return f"{country_code} {masked}"

    @staticmethod
    def _credit_result(ledger: CreditLedger) -> CreditAdjustmentResult:
        return CreditAdjustmentResult(
            ledger.id, ledger.user_id, ledger.amount, ledger.balance_after
        )
