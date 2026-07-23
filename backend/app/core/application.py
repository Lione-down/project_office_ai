import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import include_routers
from app.controllers.health import DependencyReadinessChecker
from app.core.database import DatabaseManager
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import TraceIdMiddleware, UploadBodyLimitMiddleware
from app.core.redis import RedisManager
from app.services.auth_registration import RegistrationService
from app.services.admin_operations import AdminOperationsService
from app.services.auth_invites import InviteAdminService
from app.services.auth_security import (
    InviteCodeHasher,
    PasswordService,
    RefreshTokenService,
    TokenCodec,
)
from app.services.auth_sessions import AuthSessionService
from app.services.asset_management import AssetManagementService
from app.services.briefs.dependencies import BriefServices
from app.services.briefs.service import BriefGenerationService
from app.services.evidence.store import EvidenceManifestStore
from app.services.file_safety.output_store import ParsedOutputStore
from app.services.generation import GenerationService
from app.services.generation_contracts import GenerationServices
from app.services.outbox import (
    OutboxDispatcher,
    OutboxRuntime,
    RedisGenerationPublisher,
    TaskRecoveryService,
)
from app.services.rate_limit import RedisRateLimiter
from app.services.provider_admin import ProviderAdminService
from app.services.provider_security import CredentialCipher, ProviderConfigurationError
from app.services.preflight.service import BriefWorkflowService
from app.services.skills import SkillCatalogService
from app.services.terminology.service import TerminologyLibraryService
from app.settings.config import Settings, get_settings
from app.storage.local import LocalStorageAdapter


class ReadinessChecker(Protocol):
    async def check(self) -> dict[str, bool]: ...


@dataclass(frozen=True)
class AuthServices:
    registration: object
    sessions: object
    invites: object | None = None


def create_app(
    settings: Settings | None = None,
    readiness_checker: ReadinessChecker | None = None,
    auth_services: AuthServices | None = None,
    provider_services: object | None = None,
    asset_services: object | None = None,
    terminology_services: object | None = None,
    brief_services: BriefServices | None = None,
    generation_services: GenerationServices | None = None,
    admin_services: object | None = None,
) -> FastAPI:
    application_settings = settings or get_settings()
    configure_logging(application_settings.log_level)
    resources: list[DatabaseManager | RedisManager] = []
    database: DatabaseManager | None = None
    redis: RedisManager | None = None
    credential_cipher: CredentialCipher | None = None
    outbox_runtime: OutboxRuntime | None = None
    evidence_manifest_store = EvidenceManifestStore(
        application_settings.evidence_root,
        max_output_bytes=application_settings.max_evidence_manifest_bytes,
    )

    if readiness_checker is None:
        database = DatabaseManager(application_settings.database_url)
        redis = RedisManager(application_settings.redis_url)
        readiness_checker = DependencyReadinessChecker(database, redis)
        resources.extend((database, redis))

    if (
        auth_services is None
        and database is not None
        and redis is not None
        and application_settings.session_secret is not None
    ):
        password_service = PasswordService()
        rate_limiter = RedisRateLimiter(redis)
        secret = application_settings.session_secret.get_secret_value()
        registration_service = RegistrationService(
            database.session_factory,
            password_service,
            InviteCodeHasher(secret),
            rate_limiter,
        )
        session_service = AuthSessionService(
            database.session_factory,
            password_service,
            RefreshTokenService(),
            TokenCodec(
                secret,
                timedelta(seconds=application_settings.access_token_ttl_seconds),
            ),
            rate_limiter,
            timedelta(seconds=application_settings.refresh_token_ttl_seconds),
        )
        auth_services = AuthServices(
            registration=registration_service,
            sessions=session_service,
            invites=InviteAdminService(
                database.session_factory,
                session_service,
                InviteCodeHasher(secret),
            ),
        )

    if (
        database is not None
        and auth_services is not None
        and application_settings.master_key is not None
    ):
        try:
            credential_cipher = CredentialCipher(application_settings.master_key)
        except ProviderConfigurationError:
            credential_cipher = None

    if (
        provider_services is None
        and database is not None
        and redis is not None
        and auth_services is not None
        and credential_cipher is not None
    ):
        provider_services = ProviderAdminService(
            database.session_factory,
            auth_services.sessions,
            PasswordService(),
            credential_cipher,
            rate_limiter=RedisRateLimiter(redis),
        )

    if asset_services is None and database is not None and auth_services is not None:
        asset_services = AssetManagementService(
            database.session_factory,
            auth_services.sessions,
            LocalStorageAdapter(application_settings.files_root),
            max_file_bytes=application_settings.max_file_bytes,
            max_image_bytes=application_settings.max_image_bytes,
            parsed_outputs=ParsedOutputStore(
                application_settings.parsed_root,
                max_output_bytes=application_settings.max_parsed_output_bytes,
            ),
            evidence_manifests=evidence_manifest_store,
        )

    if admin_services is None and database is not None and auth_services is not None:
        admin_services = AdminOperationsService(
            database.session_factory,
            auth_services.sessions,
            PasswordService(),
            asset_services,
        )

    if (
        terminology_services is None
        and database is not None
        and auth_services is not None
    ):
        terminology_services = TerminologyLibraryService(
            database.session_factory,
            auth_services.sessions,
        )

    if brief_services is None and database is not None and auth_services is not None:
        skills = SkillCatalogService(
            database.session_factory,
            auth_services.sessions,
        )
        generation = None
        if credential_cipher is not None:
            generation = BriefGenerationService(
                database.session_factory,
                auth_services.sessions,
                evidence_manifest_store,
                credential_cipher,
            )
        brief_services = BriefServices(
            skills=skills,
            generation=generation,
            workflow=BriefWorkflowService(
                database.session_factory,
                auth_services.sessions,
                evidence_manifest_store,
            ),
        )

    if (
        generation_services is None
        and database is not None
        and auth_services is not None
    ):
        generation_services = GenerationServices(
            GenerationService(
                database.session_factory,
                auth_services.sessions,
                task_timeout_seconds=application_settings.task_timeout_seconds,
            )
        )

    if database is not None and redis is not None:
        outbox_runtime = OutboxRuntime(
            OutboxDispatcher(
                database.session_factory,
                RedisGenerationPublisher(redis),
            ),
            TaskRecoveryService(
                database.session_factory,
                stale_after=timedelta(
                    seconds=application_settings.task_timeout_seconds
                ),
            ),
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        background_task = (
            asyncio.create_task(outbox_runtime.run())
            if outbox_runtime is not None
            else None
        )
        try:
            yield
        finally:
            if background_task is not None:
                background_task.cancel()
                await asyncio.gather(background_task, return_exceptions=True)
            for resource in reversed(resources):
                await resource.close()

    app = FastAPI(title="Office AI API", version="0.1.0", lifespan=lifespan)
    app.state.readiness_checker = readiness_checker
    app.state.auth_services = auth_services
    app.state.provider_services = provider_services
    app.state.asset_services = asset_services
    app.state.admin_services = admin_services
    app.state.terminology_services = terminology_services
    app.state.brief_services = brief_services
    app.state.generation_services = generation_services
    app.add_middleware(
        UploadBodyLimitMiddleware,
        max_body_bytes=application_settings.max_upload_body_bytes,
        auth_sessions=auth_services.sessions if auth_services is not None else None,
        asset_services=asset_services,
    )
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[application_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    include_routers(app)
    return app
