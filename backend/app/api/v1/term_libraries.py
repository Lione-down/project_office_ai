from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response

from app.schemas.terminology import (
    TermItemCreateRequest,
    TermItemResponse,
    TermItemUpdateRequest,
    TermLibraryCreateRequest,
    TermLibraryResponse,
    TermLibraryUpdateRequest,
)
from app.services.terminology.service import TerminologyOperationError


router = APIRouter(prefix="/api/v1/term-libraries", tags=["terminology"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise TerminologyOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise TerminologyOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    service = request.app.state.terminology_services
    if service is None:
        raise TerminologyOperationError(
            "terminology_not_configured", "术语服务未配置", 503
        )
    return service


def _library_response(snapshot) -> TermLibraryResponse:
    return TermLibraryResponse(**snapshot.model_dump())


@router.post("", status_code=201, response_model=TermLibraryResponse)
async def create_library(
    payload: TermLibraryCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> TermLibraryResponse:
    snapshot = await _service(request).create_library(
        _bearer_token(authorization), **payload.model_dump()
    )
    return _library_response(snapshot)


@router.get("", response_model=list[TermLibraryResponse])
async def list_libraries(
    request: Request,
    authorization: str | None = Header(default=None),
) -> list[TermLibraryResponse]:
    snapshots = await _service(request).list_libraries(_bearer_token(authorization))
    return [_library_response(snapshot) for snapshot in snapshots]


@router.get("/{library_id}", response_model=TermLibraryResponse)
async def get_library(
    library_id: UUID,
    request: Request,
    version: int | None = Query(default=None, ge=1),
    authorization: str | None = Header(default=None),
) -> TermLibraryResponse:
    snapshot = await _service(request).get_library(
        _bearer_token(authorization), library_id, version=version
    )
    return _library_response(snapshot)


@router.patch("/{library_id}", response_model=TermLibraryResponse)
async def update_library(
    library_id: UUID,
    payload: TermLibraryUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> TermLibraryResponse:
    snapshot = await _service(request).update_library(
        _bearer_token(authorization),
        library_id,
        payload.model_dump(exclude_unset=True),
    )
    return _library_response(snapshot)


@router.delete("/{library_id}", status_code=204)
async def delete_library(
    library_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _service(request).delete_library(_bearer_token(authorization), library_id)
    return Response(status_code=204)


@router.post(
    "/{library_id}/items",
    status_code=201,
    response_model=TermLibraryResponse,
)
async def create_item(
    library_id: UUID,
    payload: TermItemCreateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> TermLibraryResponse:
    snapshot = await _service(request).create_item(
        _bearer_token(authorization),
        library_id,
        **payload.model_dump(),
    )
    return _library_response(snapshot)


@router.get("/{library_id}/items", response_model=list[TermItemResponse])
async def list_items(
    library_id: UUID,
    request: Request,
    version: int | None = Query(default=None, ge=1),
    authorization: str | None = Header(default=None),
) -> list[TermItemResponse]:
    snapshot = await _service(request).get_library(
        _bearer_token(authorization), library_id, version=version
    )
    return [TermItemResponse(**item.model_dump()) for item in snapshot.items]


@router.patch(
    "/{library_id}/items/{item_id}",
    response_model=TermLibraryResponse,
)
async def update_item(
    library_id: UUID,
    item_id: UUID,
    payload: TermItemUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
) -> TermLibraryResponse:
    snapshot = await _service(request).update_item(
        _bearer_token(authorization),
        library_id,
        item_id,
        payload.model_dump(exclude_unset=True),
    )
    return _library_response(snapshot)


@router.delete("/{library_id}/items/{item_id}", status_code=204)
async def delete_item(
    library_id: UUID,
    item_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    await _service(request).delete_item(
        _bearer_token(authorization), library_id, item_id
    )
    return Response(status_code=204)
