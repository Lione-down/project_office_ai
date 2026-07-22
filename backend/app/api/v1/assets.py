import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile

from app.schemas.assets import (
    AssetResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.core.errors import log_asset_recovery_failure
from app.services.asset_contracts import AssetOperationError


project_router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
asset_router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise AssetOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise AssetOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _asset_service(request: Request):
    service = request.app.state.asset_services
    if service is None:
        raise AssetOperationError("asset_not_configured", "资产服务未配置", 503)
    return service


def _project_response(project) -> ProjectResponse:
    return ProjectResponse(**project.__dict__)


def _asset_response(asset) -> AssetResponse:
    return AssetResponse(**asset.__dict__)


async def _upload_chunks(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(1024 * 1024):
        yield chunk


@project_router.post("", status_code=201, response_model=ProjectResponse)
async def create_project(
    payload: ProjectCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    project = await _asset_service(request).create_project(
        _bearer_token(authorization), payload.name
    )
    return _project_response(project)


@project_router.get("", response_model=list[ProjectResponse])
async def list_projects(
    request: Request, authorization: str | None = Header(default=None)
) -> list[ProjectResponse]:
    projects = await _asset_service(request).list_projects(_bearer_token(authorization))
    return [_project_response(project) for project in projects]


@project_router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ProjectResponse:
    project = await _asset_service(request).update_project(
        _bearer_token(authorization),
        project_id,
        payload.model_dump(exclude_unset=True),
    )
    return _project_response(project)


@project_router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _asset_service(request).delete_project(
        _bearer_token(authorization), project_id
    )
    return Response(status_code=204)


@asset_router.post("/uploads", status_code=201, response_model=AssetResponse)
async def upload_asset(
    request: Request,
    idempotency_key: str = Header(
        ..., alias="Idempotency-Key", min_length=1, max_length=128
    ),
    authorization: str | None = Header(default=None),
) -> AssetResponse:
    token = _bearer_token(authorization)
    service = _asset_service(request)
    replay = await service.find_upload_replay(token, idempotency_key)
    if replay is not None:
        return _asset_response(replay)

    form = await request.form()
    try:
        if set(form) - {"file", "project_id"} or len(form.getlist("project_id")) > 1:
            raise AssetOperationError("upload_form_invalid", "上传表单字段无效", 422)
        files = form.getlist("file")
        if len(files) != 1 or not isinstance(files[0], UploadFile):
            raise AssetOperationError("file_required", "必须上传一个文件", 422)
        file = files[0]
        raw_project_id = form.get("project_id")
        if isinstance(raw_project_id, UploadFile):
            raise AssetOperationError("upload_form_invalid", "上传表单字段无效", 422)
        try:
            project_id = UUID(str(raw_project_id)) if raw_project_id else None
        except ValueError as exception:
            raise AssetOperationError(
                "project_id_invalid", "项目 ID 无效", 422
            ) from exception
        asset = await service.upload_asset(
            access_token=token,
            project_id=project_id,
            filename=file.filename or "",
            content_type=file.content_type or "application/octet-stream",
            content=_upload_chunks(file),
            idempotency_key=idempotency_key,
        )
    except asyncio.CancelledError as exception:
        log_asset_recovery_failure(request, exception, "upload_cancelled")
        raise
    finally:
        await form.close()
    return _asset_response(asset)


@asset_router.get("", response_model=list[AssetResponse])
async def list_assets(
    request: Request,
    project_id: UUID | None = None,
    authorization: str | None = Header(default=None),
) -> list[AssetResponse]:
    assets = await _asset_service(request).list_assets(
        _bearer_token(authorization), project_id
    )
    return [_asset_response(asset) for asset in assets]


@asset_router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> AssetResponse:
    asset = await _asset_service(request).get_asset(
        _bearer_token(authorization), asset_id
    )
    return _asset_response(asset)


def _content_response(content, disposition: str) -> FileResponse:
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if disposition == "inline":
        headers["Content-Security-Policy"] = "sandbox"
    return FileResponse(
        content.path,
        media_type=content.mime_type,
        filename=content.filename,
        content_disposition_type=disposition,
        headers=headers,
    )


@asset_router.get("/{asset_id}/preview")
async def preview_asset(
    asset_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> FileResponse:
    content = await _asset_service(request).open_asset(
        _bearer_token(authorization), asset_id
    )
    return _content_response(content, "inline")


@asset_router.get("/{asset_id}/download")
async def download_asset(
    asset_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> FileResponse:
    content = await _asset_service(request).open_asset(
        _bearer_token(authorization), asset_id
    )
    return _content_response(content, "attachment")


@asset_router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _asset_service(request).delete_asset(_bearer_token(authorization), asset_id)
    return Response(status_code=204)
