from decimal import Decimal
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai_models import AiModel
from app.models.ai_providers import AiProvider
from app.models.audit_logs import AuditLog
from app.models.provider_credentials import ProviderCredential
from app.models.users import User
from app.models.base import utc_now
from app.services.auth_registration import RateLimiter
from app.services.auth_security import PasswordService
from app.services.auth_sessions import AuthSessionService, CurrentUser
from app.services.provider_contracts import (
    AuditContext,
    CreatedCredential,
    CredentialSummary,
    CredentialTestResult,
    ModelSummary,
    ProviderAdapter,
    ProviderOperationError,
    ProviderSummary,
    RevealedCredential,
    build_provider_adapter,
    credential_summary,
    mask_key,
    model_summary,
    provider_summary,
    validate_provider_changes,
    validate_provider_configuration,
)
from app.services.provider_security import CredentialCipher


class ProviderAdminService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sessions: AuthSessionService,
        passwords: PasswordService,
        cipher: CredentialCipher,
        adapter_factory: Callable[[AiProvider], ProviderAdapter] | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._sessions = sessions
        self._passwords = passwords
        self._cipher = cipher
        self._adapter_factory = adapter_factory or build_provider_adapter
        self._rate_limiter = rate_limiter

    async def create_provider(
        self,
        *,
        access_token: str,
        vendor: str,
        display_name: str,
        protocol: str,
        base_url: str,
        default_timeout_seconds: int,
        config: dict,
    ) -> ProviderSummary:
        await self._require_admin(access_token)
        validate_provider_configuration(
            vendor, base_url, default_timeout_seconds, config
        )
        provider = AiProvider(
            vendor=vendor,
            display_name=display_name,
            protocol=protocol,
            base_url=base_url.rstrip("/"),
            status="active",
            default_timeout_seconds=default_timeout_seconds,
            config=config,
        )
        async with self._session_factory() as session, session.begin():
            session.add(provider)
        return provider_summary(provider)

    async def update_provider(
        self, *, access_token: str, provider_id: UUID, changes: dict
    ) -> ProviderSummary:
        await self._require_admin(access_token)
        validate_provider_changes(changes)
        async with self._session_factory() as session, session.begin():
            provider = await session.get(AiProvider, provider_id, with_for_update=True)
            if provider is None:
                raise ProviderOperationError(
                    "provider_not_found", "Provider 不存在", 404
                )
            for field_name, value in changes.items():
                setattr(
                    provider,
                    field_name,
                    value.rstrip("/") if field_name == "base_url" else value,
                )
        return provider_summary(provider)

    async def create_credential(
        self,
        *,
        access_token: str,
        provider_id: UUID,
        name: str,
        api_key: str,
        rpm_limit: int,
        tpm_limit: int,
        max_concurrency: int,
        rotation_source: str,
    ) -> CreatedCredential:
        admin = await self._require_admin(access_token)
        if not api_key.strip():
            raise ProviderOperationError(
                "credential_key_invalid", "Credential Key 不能为空", 422
            )
        fingerprint = self._cipher.fingerprint(api_key)
        credential = ProviderCredential(
            provider_id=provider_id,
            name=name,
            encrypted_key=self._cipher.encrypt(api_key),
            key_fingerprint=fingerprint,
            status="active",
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            max_concurrency=max_concurrency,
            rotation_source=rotation_source,
            created_by_user_id=admin.user_id,
        )
        async with self._session_factory() as session:
            if await session.get(AiProvider, provider_id) is None:
                raise ProviderOperationError(
                    "provider_not_found", "Provider 不存在", 404
                )
            existing_id = await session.scalar(
                select(ProviderCredential.id).where(
                    ProviderCredential.provider_id == provider_id,
                    ProviderCredential.key_fingerprint == fingerprint,
                )
            )
            if existing_id is not None:
                raise ProviderOperationError(
                    "credential_duplicate", "该 Provider 已存在相同 Credential", 409
                )
            session.add(credential)
            try:
                await session.commit()
            except IntegrityError as exception:
                await session.rollback()
                raise ProviderOperationError(
                    "credential_duplicate", "该 Provider 已存在相同 Credential", 409
                ) from exception
        return CreatedCredential(
            credential_id=credential.id,
            provider_id=credential.provider_id,
            name=credential.name,
            masked_key=mask_key(api_key),
            status=credential.status,
            rpm_limit=credential.rpm_limit,
            tpm_limit=credential.tpm_limit,
            max_concurrency=credential.max_concurrency,
            rotation_source=credential.rotation_source,
        )

    async def update_credential(
        self, *, access_token: str, credential_id: UUID, changes: dict
    ) -> CredentialSummary:
        await self._require_admin(access_token)
        allowed = {"name", "status", "rpm_limit", "tpm_limit", "max_concurrency"}
        if unknown := set(changes) - allowed:
            raise ProviderOperationError(
                "credential_update_invalid",
                f"不支持更新 Credential 字段：{', '.join(sorted(unknown))}",
                422,
            )
        async with self._session_factory() as session, session.begin():
            credential = await session.get(
                ProviderCredential, credential_id, with_for_update=True
            )
            if credential is None:
                raise ProviderOperationError(
                    "credential_not_found", "Credential 不存在", 404
                )
            for field_name, value in changes.items():
                setattr(credential, field_name, value)
        return credential_summary(credential)

    async def reveal_credential(
        self,
        *,
        access_token: str,
        credential_id: UUID,
        current_password: str,
        reason: str,
        audit: AuditContext,
    ) -> RevealedCredential:
        admin = await self._require_admin(access_token)
        async with self._session_factory() as session:
            credential = await session.get(ProviderCredential, credential_id)
            user = await session.get(User, admin.user_id)
        if credential is None or credential.status != "active":
            raise ProviderOperationError(
                "credential_not_found", "Credential 不存在或不可用", 404
            )
        if not reason.strip():
            await self._write_reveal_audit(admin, credential, reason, "failed", audit)
            raise ProviderOperationError("reason_required", "敏感操作必须填写原因", 422)
        if user is None or not self._passwords.verify(
            user.password_hash, current_password
        ):
            await self._write_reveal_audit(admin, credential, reason, "failed", audit)
            raise ProviderOperationError("reauthentication_failed", "重新认证失败", 401)
        try:
            api_key = self._cipher.decrypt(credential.encrypted_key)
        except Exception:
            await self._write_reveal_audit(admin, credential, reason, "failed", audit)
            raise
        await self._write_reveal_audit(admin, credential, reason, "success", audit)
        return RevealedCredential(credential_id=credential.id, api_key=api_key)

    async def create_model(
        self,
        *,
        access_token: str,
        provider_id: UUID,
        credential_id: UUID,
        model_code: str,
        display_name: str,
        capabilities: dict,
        context_window: int,
        max_output_tokens: int,
        user_visible: bool,
        is_recommended: bool,
        credit_multiplier: str | Decimal,
        allowed_skills: list,
    ) -> ModelSummary:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            provider = await session.get(AiProvider, provider_id)
            credential = await session.get(ProviderCredential, credential_id)
            if provider is None:
                raise ProviderOperationError(
                    "provider_not_found", "Provider 不存在", 404
                )
            if credential is None:
                raise ProviderOperationError(
                    "credential_not_found", "Credential 不存在", 404
                )
            if credential.provider_id != provider_id:
                raise ProviderOperationError(
                    "credential_provider_mismatch",
                    "Credential 不属于指定 Provider",
                    409,
                )
            model = AiModel(
                provider_id=provider_id,
                credential_id=credential_id,
                model_code=model_code,
                display_name=display_name,
                capabilities=capabilities,
                context_window=context_window,
                max_output_tokens=max_output_tokens,
                user_visible=user_visible,
                is_recommended=is_recommended,
                credit_multiplier=Decimal(credit_multiplier),
                allowed_skills=allowed_skills,
                status="active",
            )
            session.add(model)
            try:
                await session.commit()
            except IntegrityError as exception:
                await session.rollback()
                raise ProviderOperationError(
                    "model_duplicate", "该 Credential 已绑定相同模型", 409
                ) from exception
        return model_summary(model)

    async def update_model(
        self, *, access_token: str, model_id: UUID, changes: dict
    ) -> ModelSummary:
        await self._require_admin(access_token)
        allowed = {
            "display_name",
            "capabilities",
            "context_window",
            "max_output_tokens",
            "user_visible",
            "is_recommended",
            "credit_multiplier",
            "allowed_skills",
            "status",
        }
        if unknown := set(changes) - allowed:
            raise ProviderOperationError(
                "model_update_invalid",
                f"不支持更新模型字段：{', '.join(sorted(unknown))}",
                422,
            )
        async with self._session_factory() as session, session.begin():
            model = await session.get(AiModel, model_id, with_for_update=True)
            if model is None:
                raise ProviderOperationError("model_not_found", "模型不存在", 404)
            for field_name, value in changes.items():
                setattr(
                    model,
                    field_name,
                    Decimal(value) if field_name == "credit_multiplier" else value,
                )
        return model_summary(model)

    async def list_visible_models(self, access_token: str) -> list[ModelSummary]:
        await self._sessions.authenticate_access(access_token)
        async with self._session_factory() as session:
            models = list(
                await session.scalars(
                    select(AiModel)
                    .join(AiProvider, AiProvider.id == AiModel.provider_id)
                    .join(
                        ProviderCredential,
                        ProviderCredential.id == AiModel.credential_id,
                    )
                    .where(
                        AiModel.user_visible.is_(True),
                        AiModel.status == "active",
                        AiProvider.status == "active",
                        ProviderCredential.status == "active",
                    )
                    .order_by(AiModel.is_recommended.desc(), AiModel.display_name)
                )
            )
        return [model_summary(model) for model in models]

    async def list_providers(self, access_token: str) -> list[ProviderSummary]:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            providers = list(
                await session.scalars(
                    select(AiProvider).order_by(AiProvider.created_at, AiProvider.id)
                )
            )
        return [provider_summary(provider) for provider in providers]

    async def list_credentials(self, access_token: str) -> list[CredentialSummary]:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            credentials = list(
                await session.scalars(
                    select(ProviderCredential).order_by(
                        ProviderCredential.created_at, ProviderCredential.id
                    )
                )
            )
        return [credential_summary(item) for item in credentials]

    async def list_models(self, access_token: str) -> list[ModelSummary]:
        await self._require_admin(access_token)
        async with self._session_factory() as session:
            models = list(
                await session.scalars(
                    select(AiModel).order_by(AiModel.created_at, AiModel.id)
                )
            )
        return [model_summary(model) for model in models]

    async def test_credential(
        self,
        *,
        access_token: str,
        credential_id: UUID,
        reason: str,
        audit: AuditContext,
    ) -> CredentialTestResult:
        admin = await self._require_admin(access_token)
        if not reason.strip():
            raise ProviderOperationError("reason_required", "敏感操作必须填写原因", 422)
        if self._rate_limiter is not None:
            await self._rate_limiter.check(
                "credential_test", f"{admin.user_id}:{credential_id}", 5, 60
            )
        async with self._session_factory() as session:
            credential = await session.get(ProviderCredential, credential_id)
            provider = (
                await session.get(AiProvider, credential.provider_id)
                if credential is not None
                else None
            )
        if credential is None or provider is None:
            raise ProviderOperationError(
                "credential_not_found", "Credential 不存在", 404
            )
        adapter = self._adapter_factory(provider)
        try:
            api_key = self._cipher.decrypt(credential.encrypted_key)
            await adapter.test_authentication(api_key)
        except Exception as error:
            classification = adapter.classify_error(error)
            await self._persist_credential_test(
                admin=admin,
                credential=credential,
                status=classification.category,
                should_disable=classification.disable_credential,
                reason=reason,
                result="failed",
                audit=audit,
            )
            return CredentialTestResult(
                credential_id=credential.id,
                status=classification.category,
                retryable=classification.retryable,
                uncertain=classification.uncertain,
            )
        await self._persist_credential_test(
            admin=admin,
            credential=credential,
            status="healthy",
            should_disable=False,
            reason=reason,
            result="success",
            audit=audit,
        )
        return CredentialTestResult(
            credential_id=credential.id,
            status="healthy",
            retryable=False,
            uncertain=False,
        )

    async def _require_admin(self, access_token: str) -> CurrentUser:
        current_user = await self._sessions.authenticate_access(access_token)
        if current_user.role != "admin":
            raise ProviderOperationError("admin_required", "需要管理员权限", 403)
        return current_user

    async def _write_reveal_audit(
        self,
        admin: CurrentUser,
        credential: ProviderCredential,
        reason: str,
        result: str,
        audit: AuditContext,
    ) -> None:
        entry = AuditLog(
            actor_user_id=admin.user_id,
            action="credential.revealed",
            target_type="provider_credential",
            target_id=credential.id,
            ip_address=audit.ip_address,
            user_agent=audit.user_agent[:255] if audit.user_agent else None,
            reason=reason.strip()[:500],
            result=result,
            context={"credential_name": credential.name},
            trace_id=audit.trace_id,
        )
        async with self._session_factory() as session, session.begin():
            session.add(entry)

    async def _persist_credential_test(
        self,
        *,
        admin: CurrentUser,
        credential: ProviderCredential,
        status: str,
        should_disable: bool,
        reason: str,
        result: str,
        audit: AuditContext,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            stored = await session.get(
                ProviderCredential, credential.id, with_for_update=True
            )
            if stored is None:
                raise ProviderOperationError(
                    "credential_not_found", "Credential 不存在", 404
                )
            stored.last_test_status = status
            stored.last_tested_at = utc_now()
            if should_disable:
                stored.status = "suspended"
            session.add(
                AuditLog(
                    actor_user_id=admin.user_id,
                    action="credential.tested",
                    target_type="provider_credential",
                    target_id=credential.id,
                    ip_address=audit.ip_address,
                    user_agent=(audit.user_agent[:255] if audit.user_agent else None),
                    reason=reason.strip()[:500],
                    result=result,
                    context={"test_status": status},
                    trace_id=audit.trace_id,
                )
            )
