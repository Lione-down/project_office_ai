from datetime import datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.services.chat_contracts import (
    ChatEvent,
    ChatMessageSnapshot,
    ChatServices,
    ChatThreadDetail,
    ChatThreadSnapshot,
    PreparedChatStream,
)
from tests.chat.conftest import MODEL_25_ID, USER_ID


THREAD_ID = UUID("019fa9dc-0000-7000-8000-000000000101")
RUN_ID = UUID("019fa9dc-0000-7000-8000-000000000102")
USER_MESSAGE_ID = UUID("019fa9dc-0000-7000-8000-000000000103")
ASSISTANT_MESSAGE_ID = UUID("019fa9dc-0000-7000-8000-000000000104")


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


class ChatStub:
    def __init__(self) -> None:
        self.cancelled = []

    @staticmethod
    def thread() -> ChatThreadSnapshot:
        return ChatThreadSnapshot(
            thread_id=THREAD_ID,
            user_id=USER_ID,
            title="新对话",
            default_model_id=MODEL_25_ID,
            model_code="agnes-2.5-flash",
            mode="chat",
            status="active",
            last_activity_at=datetime(2026, 7, 29, 10, 0, 0),
            created_at=datetime(2026, 7, 29, 10, 0, 0),
            updated_at=datetime(2026, 7, 29, 10, 0, 0),
        )

    async def create_thread(self, access_token, command, idempotency_key):
        assert access_token == "access"
        assert command.model_id == MODEL_25_ID
        assert idempotency_key == "thread-api-001"
        return self.thread()

    async def list_threads(self, access_token, search=None):
        assert access_token == "access"
        return (self.thread(),)

    async def get_thread(self, access_token, thread_id):
        assert access_token == "access"
        assert thread_id == THREAD_ID
        return ChatThreadDetail(**self.thread().model_dump(), messages=())

    async def prepare_stream(
        self,
        access_token,
        thread_id,
        command,
        idempotency_key,
        *,
        trace_id,
    ):
        assert access_token == "access"
        assert thread_id == THREAD_ID
        assert command.content == "你好"
        assert idempotency_key == "chat-api-run-001"
        assert trace_id

        async def events():
            yield ChatEvent(
                event="run.started",
                run_id=RUN_ID,
                thread_id=THREAD_ID,
                sequence=1,
                occurred_at=datetime(2026, 7, 29, 10, 0, 0),
                trace_id=trace_id,
                payload={
                    "user_message_id": str(USER_MESSAGE_ID),
                    "assistant_message_id": str(ASSISTANT_MESSAGE_ID),
                },
            )
            yield ChatEvent(
                event="message.delta",
                run_id=RUN_ID,
                thread_id=THREAD_ID,
                sequence=2,
                occurred_at=datetime(2026, 7, 29, 10, 0, 1),
                trace_id=trace_id,
                payload={"delta": "你好"},
            )
            yield ChatEvent(
                event="run.completed",
                run_id=RUN_ID,
                thread_id=THREAD_ID,
                sequence=3,
                occurred_at=datetime(2026, 7, 29, 10, 0, 2),
                trace_id=trace_id,
                payload={"content": "你好"},
            )

        return PreparedChatStream(run_id=RUN_ID, events=events(), replayed=False)

    async def cancel_run(self, access_token, run_id):
        assert access_token == "access"
        self.cancelled.append(run_id)
        return ChatMessageSnapshot(
            message_id=ASSISTANT_MESSAGE_ID,
            sequence=2,
            role="assistant",
            content="部分内容",
            status="cancelled_partial",
            parent_message_id=USER_MESSAGE_ID,
            supersedes_message_id=None,
            branch_root_id=USER_MESSAGE_ID,
            run_id=RUN_ID,
            model_code="agnes-2.5-flash",
            created_at=datetime(2026, 7, 29, 10, 0, 0),
            finalized_at=datetime(2026, 7, 29, 10, 0, 1),
        )


async def test_chat_api_exposes_no_store_crud_sse_and_cancel_contract() -> None:
    chat = ChatStub()
    app = create_app(
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        chat_services=ChatServices(chat),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/api/v1/chat/threads",
            headers={
                "Authorization": "Bearer access",
                "Idempotency-Key": "thread-api-001",
            },
            json={"model_id": str(MODEL_25_ID), "mode": "chat"},
        )
        listed = await client.get(
            "/api/v1/chat/threads",
            headers={"Authorization": "Bearer access"},
        )
        detail = await client.get(
            f"/api/v1/chat/threads/{THREAD_ID}",
            headers={"Authorization": "Bearer access"},
        )
        streamed = await client.post(
            f"/api/v1/chat/threads/{THREAD_ID}/messages:stream",
            headers={
                "Authorization": "Bearer access",
                "Idempotency-Key": "chat-api-run-001",
            },
            json={"content": "你好", "model_id": str(MODEL_25_ID)},
        )
        cancelled = await client.post(
            f"/api/v1/chat/runs/{RUN_ID}/cancel",
            headers={
                "Authorization": "Bearer access",
                "Idempotency-Key": "chat-cancel-001",
            },
            json={},
        )

    assert created.status_code == 201
    assert listed.status_code == 200
    assert detail.status_code == 200
    assert created.headers["cache-control"] == "private, no-store"
    assert listed.headers["cache-control"] == "private, no-store"
    assert detail.headers["cache-control"] == "private, no-store"
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert streamed.headers["cache-control"] == "private, no-store"
    assert streamed.headers["x-accel-buffering"] == "no"
    assert "event: run.started" in streamed.text
    assert f"id: {RUN_ID}:1" in streamed.text
    assert '"schema_version":"chat-sse.v1"' in streamed.text
    assert "event: run.completed" in streamed.text
    assert cancelled.json()["status"] == "cancelled_partial"
    assert chat.cancelled == [RUN_ID]
