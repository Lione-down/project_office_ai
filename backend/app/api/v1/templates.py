from fastapi import APIRouter, Header, Query, Request, Response

from app.schemas.templates import TemplateDetailResponse, TemplateSummaryResponse
from app.services.briefs.service import BriefOperationError


router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise BriefOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise BriefOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    service = request.app.state.template_services
    if service is None:
        raise BriefOperationError(
            "template_not_configured",
            "模板目录服务未配置",
            503,
        )
    return service


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("", response_model=list[TemplateSummaryResponse])
async def list_templates(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    category: str | None = Query(default=None, min_length=1, max_length=64),
) -> list[TemplateSummaryResponse]:
    definitions = await _service(request).list_published(
        _bearer_token(authorization),
        category=category,
    )
    _no_store(response)
    return [
        TemplateSummaryResponse.from_definition(definition)
        for definition in definitions
    ]


@router.get("/{template_code}", response_model=TemplateDetailResponse)
async def get_template(
    template_code: str,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    version: str | None = Query(default=None, min_length=1, max_length=20),
) -> TemplateDetailResponse:
    definition = await _service(request).get_published(
        _bearer_token(authorization),
        template_code,
        version=version,
    )
    _no_store(response)
    return TemplateDetailResponse.from_definition(definition)
