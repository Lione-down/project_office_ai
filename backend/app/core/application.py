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
from app.core.middleware import TraceIdMiddleware
from app.core.redis import RedisManager
from app.services.auth_registration import RegistrationService
from app.services.auth_invites import InviteAdminService
from app.services.auth_security import (
    InviteCodeHasher,
    PasswordService,
    RefreshTokenService,
    TokenCodec,
)
from app.services.auth_sessions import AuthSessionService
from app.services.rate_limit import RedisRateLimiter
from app.services.provider_admin import ProviderAdminService
from app.services.provider_security import CredentialCipher, ProviderConfigurationError
from app.settings.config import Settings, get_settings


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
) -> FastAPI:
    application_settings = settings or get_settings()
    configure_logging(application_settings.log_level)
    resources: list[DatabaseManager | RedisManager] = []
    database: DatabaseManager | None = None
    redis: RedisManager | None = None

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
        provider_services is None
        and database is not None
        and redis is not None
        and auth_services is not None
        and application_settings.master_key is not None
    ):
        try:
            credential_cipher = CredentialCipher(application_settings.master_key)
        except ProviderConfigurationError:
            credential_cipher = None
        if credential_cipher is not None:
            provider_services = ProviderAdminService(
                database.session_factory,
                auth_services.sessions,
                PasswordService(),
                credential_cipher,
                rate_limiter=RedisRateLimiter(redis),
            )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for resource in reversed(resources):
            await resource.close()

    app = FastAPI(title="Office AI API", version="0.1.0", lifespan=lifespan)
    app.state.readiness_checker = readiness_checker
    app.state.auth_services = auth_services
    app.state.provider_services = provider_services
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
