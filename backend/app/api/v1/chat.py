import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatRunRequest,
    ChatThreadCreateRequest,
    ChatThreadUpdateRequest,
)
from app.services.chat_contracts import (
    ChatMessageSnapshot,
    ChatOperationError,
    ChatThreadDetail,
    ChatThreadSnapshot,
    PreparedChatStream,
)


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise ChatOperationError("session_invalid", "Session 已失效", 401)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise ChatOperationError("session_invalid", "Session 已失效", 401)
    return token.strip()


def _service(request: Request):
    services = request.app.state.chat_services
    if services is None:
        raise ChatOperationError(
            "chat_not_configured",
            "对话服务未配置",
            503,
        )
    return services.conversations


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post("/threads", status_code=201, response_model=ChatThreadSnapshot)
async def create_thread(
    payload: ChatThreadCreateRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
) -> ChatThreadSnapshot:
    snapshot = await _service(request).create_thread(
        _bearer_token(authorization),
        payload.to_command(),
        idempotency_key,
    )
    _no_store(response)
    return snapshot


@router.get("/threads", response_model=list[ChatThreadSnapshot])
async def list_threads(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    search: str = Query(default="", max_length=200),
) -> list[ChatThreadSnapshot]:
    snapshots = await _service(request).list_threads(
        _bearer_token(authorization),
        search,
    )
    _no_store(response)
    return list(snapshots)


@router.get("/threads/{thread_id}", response_model=ChatThreadDetail)
async def get_thread(
    thread_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> ChatThreadDetail:
    snapshot = await _service(request).get_thread(
        _bearer_token(authorization),
        thread_id,
    )
    _no_store(response)
    return snapshot


@router.patch("/threads/{thread_id}", response_model=ChatThreadSnapshot)
async def update_thread(
    thread_id: UUID,
    payload: ChatThreadUpdateRequest,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    _idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
) -> ChatThreadSnapshot:
    snapshot = await _service(request).update_thread(
        _bearer_token(authorization),
        thread_id,
        payload.to_command(),
    )
    _no_store(response)
    return snapshot


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    _idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
) -> Response:
    await _service(request).delete_thread(
        _bearer_token(authorization),
        thread_id,
    )
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.post("/threads/{thread_id}/messages:stream")
async def stream_message(
    thread_id: UUID,
    payload: ChatRunRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
) -> StreamingResponse:
    prepared = await _service(request).prepare_stream(
        _bearer_token(authorization),
        thread_id,
        payload.to_command(),
        idempotency_key,
        trace_id=request.state.trace_id,
    )
    return _streaming_response(prepared, request.app.state.chat_heartbeat_seconds)


@router.get("/runs/{run_id}/stream")
async def reconnect_stream(
    run_id: UUID,
    request: Request,
    authorization: str | None = Header(default=None),
    last_event_id: str = Header(alias="Last-Event-ID"),
) -> StreamingResponse:
    prepared = await _service(request).reconnect_stream(
        _bearer_token(authorization),
        run_id,
        last_event_id,
        trace_id=request.state.trace_id,
    )
    return _streaming_response(prepared, request.app.state.chat_heartbeat_seconds)


@router.post("/runs/{run_id}/cancel", response_model=ChatMessageSnapshot)
async def cancel_run(
    run_id: UUID,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    _idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
) -> ChatMessageSnapshot:
    snapshot = await _service(request).cancel_run(
        _bearer_token(authorization),
        run_id,
    )
    _no_store(response)
    return snapshot


def _streaming_response(
    prepared: PreparedChatStream,
    heartbeat_seconds: int,
) -> StreamingResponse:
    return StreamingResponse(
        _sse_frames(prepared.events, heartbeat_seconds),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "private, no-store",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_frames(
    events: AsyncIterator,
    heartbeat_seconds: int,
) -> AsyncIterator[str]:
    iterator = events.__aiter__()
    pending = asyncio.create_task(anext(iterator))
    try:
        while True:
            done, _ = await asyncio.wait(
                {pending},
                timeout=heartbeat_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                yield "event: heartbeat\ndata: {}\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            yield (
                f"id: {event.run_id}:{event.sequence}\n"
                f"event: {event.event}\n"
                f"data: {event.model_dump_json(exclude={'event'})}\n\n"
            )
            pending = asyncio.create_task(anext(iterator))
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
