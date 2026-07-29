from fastapi import FastAPI

from app.api.v1.assets import asset_router, project_router
from app.api.v1.admin import router as admin_operations_router
from app.api.v1.auth import router as auth_router
from app.api.v1.briefs import brief_router, generation_router, skill_router
from app.api.v1.chat import router as chat_router
from app.api.v1.decks import chat_deck_router, deck_router
from app.api.v1.health import router as health_router
from app.api.v1.generations import credit_router, task_router
from app.api.v1.invite_codes import router as invite_codes_router
from app.api.v1.providers import admin_router as provider_admin_router
from app.api.v1.providers import model_router
from app.api.v1.term_libraries import router as terminology_router
from app.api.v1.templates import router as template_router
from app.api.v1.workflow_tasks import router as workflow_task_router
from app.api.v1.media import router as media_router


def include_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(invite_codes_router)
    app.include_router(provider_admin_router)
    app.include_router(admin_operations_router)
    app.include_router(model_router)
    app.include_router(project_router)
    app.include_router(asset_router)
    app.include_router(terminology_router)
    app.include_router(skill_router)
    app.include_router(template_router)
    app.include_router(brief_router)
    app.include_router(generation_router)
    app.include_router(task_router)
    app.include_router(credit_router)
    app.include_router(workflow_task_router)
    app.include_router(chat_router)
    app.include_router(chat_deck_router)
    app.include_router(deck_router)
    app.include_router(media_router)
