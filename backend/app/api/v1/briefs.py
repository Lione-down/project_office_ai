from fastapi import APIRouter, Header, Request, Response

from app.schemas.briefs import (
    BriefGenerationRequest,
    BriefRevisionResponse,
    SkillResponse,
)
from app.services.briefs.service import BriefOperationError


skill_router = APIRouter(prefix="/api/v1/skills", tags=["skills"])
brief_router = APIRouter(prefix="/api/v1/briefs", tags=["briefs"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise BriefOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise BriefOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _services(request: Request):
    services = request.app.state.brief_services
    if services is None:
        raise BriefOperationError(
            "brief_not_configured", "Structured Brief服务未配置", 503
        )
    return services


@skill_router.get("", response_model=list[SkillResponse])
async def list_skills(
    request: Request,
    authorization: str | None = Header(default=None),
) -> list[SkillResponse]:
    access_token = _bearer_token(authorization)
    skills = await _services(request).skills.list_published(access_token)
    return [SkillResponse.from_definition(skill) for skill in skills]


@skill_router.get("/{skill_code}", response_model=SkillResponse)
async def get_skill(
    skill_code: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> SkillResponse:
    access_token = _bearer_token(authorization)
    skill = await _services(request).skills.get_published(access_token, skill_code)
    return SkillResponse.from_definition(skill)


@brief_router.post(
    "/generate",
    status_code=201,
    response_model=BriefRevisionResponse,
)
async def generate_brief(
    payload: BriefGenerationRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> BriefRevisionResponse:
    access_token = _bearer_token(authorization)
    generation = _services(request).generation
    if generation is None:
        raise BriefOperationError(
            "provider_not_configured", "Provider Master Key 未配置", 503
        )
    snapshot = await generation.generate(
        access_token,
        payload.to_command(),
        trace_id=request.state.trace_id,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return BriefRevisionResponse(**snapshot.model_dump())
