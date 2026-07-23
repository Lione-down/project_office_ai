from fastapi import FastAPI

from app.api.v1.assets import asset_router, project_router
from app.api.v1.auth import router as auth_router
from app.api.v1.briefs import brief_router, skill_router
from app.api.v1.health import router as health_router
from app.api.v1.invite_codes import router as invite_codes_router
from app.api.v1.providers import admin_router as provider_admin_router
from app.api.v1.providers import model_router
from app.api.v1.term_libraries import router as terminology_router


def include_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(invite_codes_router)
    app.include_router(provider_admin_router)
    app.include_router(model_router)
    app.include_router(project_router)
    app.include_router(asset_router)
    app.include_router(terminology_router)
    app.include_router(skill_router)
    app.include_router(brief_router)
