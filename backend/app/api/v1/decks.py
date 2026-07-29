from uuid import UUID

from fastapi import APIRouter, Header, Request, Response

from app.schemas.decks import (
    DeckConfirmRequest,
    DeckCreateRequest,
    DeckDraftResponse,
    DeckGenerationRequest,
    DeckUpdateRequest,
)
from app.schemas.generation import GenerationTaskResponse
from app.services.decks.contracts import DeckOperationError


chat_deck_router = APIRouter(
    prefix="/api/v1/chat/messages",
    tags=["decks"],
)
deck_router = APIRouter(prefix="/api/v1/deck-drafts", tags=["decks"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise DeckOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise DeckOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    service = request.app.state.deck_services
    if service is None:
        raise DeckOperationError("deck_not_configured", "Deck 服务未配置", 503)
    return service


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@chat_deck_router.post(
    "/{message_id}/deck-drafts",
    status_code=201,
    response_model=DeckDraftResponse,
)
async def create_deck_draft(
    message_id: UUID,
    payload: DeckCreateRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
    ),
) -> DeckDraftResponse:
    snapshot = await _service(request).create(
        _bearer_token(authorization),
        message_id,
        payload,
        idempotency_key,
        trace_id=request.state.trace_id,
    )
    _no_store(response)
    return snapshot


@deck_router.get("/{draft_id}", response_model=DeckDraftResponse)
async def get_deck_draft(
    draft_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> DeckDraftResponse:
    snapshot = await _service(request).get(
        _bearer_token(authorization),
        draft_id,
    )
    _no_store(response)
    return snapshot


@deck_router.patch(
    "/{draft_id}",
    status_code=201,
    response_model=DeckDraftResponse,
)
async def update_deck_draft(
    draft_id: UUID,
    payload: DeckUpdateRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> DeckDraftResponse:
    snapshot = await _service(request).update(
        _bearer_token(authorization),
        draft_id,
        payload,
    )
    _no_store(response)
    return snapshot


@deck_router.post("/{draft_id}/confirm", response_model=DeckDraftResponse)
async def confirm_deck_draft(
    draft_id: UUID,
    payload: DeckConfirmRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> DeckDraftResponse:
    snapshot = await _service(request).confirm(
        _bearer_token(authorization),
        draft_id,
        payload,
    )
    _no_store(response)
    return snapshot


@deck_router.post("/{draft_id}/preflight", response_model=DeckDraftResponse)
async def preflight_deck_draft(
    draft_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> DeckDraftResponse:
    snapshot = await _service(request).preflight(
        _bearer_token(authorization),
        draft_id,
    )
    _no_store(response)
    return snapshot


@deck_router.post(
    "/{draft_id}/generations",
    status_code=201,
    response_model=GenerationTaskResponse,
)
async def generate_deck(
    draft_id: UUID,
    payload: DeckGenerationRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
    ),
) -> GenerationTaskResponse:
    snapshot = await _service(request).generate(
        _bearer_token(authorization),
        draft_id,
        payload,
        idempotency_key,
    )
    _no_store(response)
    return GenerationTaskResponse.from_snapshot(snapshot)
