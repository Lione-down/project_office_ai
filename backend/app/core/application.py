from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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
from app.settings.config import Settings, get_settings


class ReadinessChecker(Protocol):
    async def check(self) -> dict[str, bool]: ...


def create_app(
    settings: Settings | None = None,
    readiness_checker: ReadinessChecker | None = None,
) -> FastAPI:
    application_settings = settings or get_settings()
    configure_logging(application_settings.log_level)
    resources: list[DatabaseManager | RedisManager] = []

    if readiness_checker is None:
        database = DatabaseManager(application_settings.database_url)
        redis = RedisManager(application_settings.redis_url)
        readiness_checker = DependencyReadinessChecker(database, redis)
        resources.extend((database, redis))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for resource in reversed(resources):
            await resource.close()

    app = FastAPI(title="Office AI API", version="0.1.0", lifespan=lifespan)
    app.state.readiness_checker = readiness_checker
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
