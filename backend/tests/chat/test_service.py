import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.models.chat_messages import ChatMessage
from app.models.chat_runs import ChatRun
from app.providers.agnes import ProviderConfigurationError, ProviderStreamChunk
from app.services.chat_contracts import (
    ChatOperationError,
    ChatRunCommand,
    ChatThreadCreateCommand,
    ChatThreadUpdateCommand,
)
from tests.chat.conftest import (
    MODEL_20_ID,
    MODEL_25_ID,
    OTHER_USER_ID,
)


class BrokenCipher:
    def decrypt(self, _ciphertext: str) -> str:
        raise ValueError("test-only decrypt failure")


class FailingAdapter:
    def __init__(self) -> None:
        self.requests = []

    async def stream_chat_completion(self, *, api_key, request):
        self.requests.append(request)
        if False:
            yield ProviderStreamChunk()
        raise ProviderConfigurationError(
            "provider_response_invalid",
            "test-only invalid response",
        )

    def classify_error(self, _error):
        raise AssertionError("configuration errors must not be reclassified")


class BlockingAdapter:
    def __init__(self) -> None:
        self.requests = []
        self.first_delta_sent = asyncio.Event()
        self.release = asyncio.Event()

    async def stream_chat_completion(self, *, api_key, request):
        self.requests.append(request)
        yield ProviderStreamChunk(content_delta="可保留片段")
        self.first_delta_sent.set()
        await self.release.wait()

    def classify_error(self, _error):
        raise AssertionError("cancelled streams must not be classified")


async def test_thread_crud_is_owner_scoped_and_soft_delete_hides_history(
    chat_harness,
) -> None:
    created = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-001",
    )
    renamed = await chat_harness.service.update_thread(
        "access",
        created.thread_id,
        ChatThreadUpdateCommand(title="董事会叙事打磨"),
    )
    detail = await chat_harness.service.get_thread("access", created.thread_id)

    assert renamed.title == "董事会叙事打磨"
    assert detail.thread_id == created.thread_id
    assert detail.messages == ()

    chat_harness.sessions.user_id = OTHER_USER_ID
    with pytest.raises(ChatOperationError) as hidden:
        await chat_harness.service.get_thread("access", created.thread_id)
    assert hidden.value.error_code == "chat_thread_not_found"

    chat_harness.sessions.user_id = created.user_id
    await chat_harness.service.delete_thread("access", created.thread_id)
    assert await chat_harness.service.list_threads("access") == ()


async def test_stream_persists_partial_and_terminal_events_without_fallback(
    chat_harness,
) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-002",
    )
    prepared = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(content="请整理一个产品发布叙事", model_id=MODEL_25_ID),
        "chat-run-0001",
        trace_id="trace-chat-run-1",
    )
    events = [event async for event in prepared.events]

    assert [event.event for event in events] == [
        "run.started",
        "message.delta",
        "message.delta",
        "run.completed",
    ]
    assert [event.sequence for event in events] == [1, 2, 3, 4]
    assert events[-1].payload["content"] == "第一段第二段"
    assert len(chat_harness.adapter.requests) == 1
    request = chat_harness.adapter.requests[0]
    assert request.model == "agnes-2.5-flash"
    assert request.stream is True

    async with chat_harness.session_factory() as session:
        run = await session.get(ChatRun, prepared.run_id)
        assistant = await session.get(ChatMessage, run.assistant_message_id)
    assert run.status == "succeeded"
    assert run.prompt_tokens == 12
    assert run.completion_tokens == 7
    assert assistant.status == "succeeded"
    assert assistant.content == "第一段第二段"
    assert [call[0] for call in chat_harness.admission.calls] == [
        "chat-hour",
        "chat-day",
    ]


async def test_same_idempotency_key_replays_without_second_provider_call(
    chat_harness,
) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-003",
    )
    command = ChatRunCommand(content="给我三个标题", model_id=MODEL_25_ID)
    first = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        command,
        "chat-run-replay",
        trace_id="trace-replay-1",
    )
    first_events = [event async for event in first.events]
    replay = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        command,
        "chat-run-replay",
        trace_id="trace-replay-2",
    )
    replay_events = [event async for event in replay.events]

    assert first.run_id == replay.run_id
    assert replay.replayed is True
    assert replay_events[-1].event == "run.completed"
    assert replay_events[-1].payload["content"] == "第一段第二段"
    assert len(chat_harness.adapter.requests) == 1
    assert first_events[-1].payload["content"] == "第一段第二段"


async def test_idempotency_key_rejects_a_different_payload(chat_harness) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-004",
    )
    prepared = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(content="版本 A", model_id=MODEL_25_ID),
        "chat-run-conflict",
        trace_id="trace-conflict-1",
    )
    _ = [event async for event in prepared.events]

    with pytest.raises(ChatOperationError) as conflict:
        await chat_harness.service.prepare_stream(
            "access",
            thread.thread_id,
            ChatRunCommand(content="版本 B", model_id=MODEL_25_ID),
            "chat-run-conflict",
            trace_id="trace-conflict-2",
        )
    assert conflict.value.error_code == "idempotency_conflict"


async def test_model_selection_is_explicit_and_thinking_is_capability_gated(
    chat_harness,
) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-005",
    )
    with pytest.raises(ChatOperationError) as unsupported:
        await chat_harness.service.prepare_stream(
            "access",
            thread.thread_id,
            ChatRunCommand(
                content="需要深度整理",
                model_id=MODEL_20_ID,
                thinking_enabled=True,
            ),
            "chat-run-thinking",
            trace_id="trace-thinking",
        )
    assert unsupported.value.error_code == "chat_thinking_unsupported"
    assert chat_harness.adapter.requests == []


async def test_regenerate_creates_a_sibling_without_overwriting_history(
    chat_harness,
) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-006",
    )
    first = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(content="写一段开场", model_id=MODEL_25_ID),
        "chat-run-branch-a",
        trace_id="trace-branch-a",
    )
    _ = [event async for event in first.events]
    detail = await chat_harness.service.get_thread("access", thread.thread_id)
    first_assistant = next(
        message for message in detail.messages if message.role == "assistant"
    )

    second = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(
            regenerate_from_message_id=first_assistant.message_id,
            model_id=MODEL_25_ID,
        ),
        "chat-run-branch-b",
        trace_id="trace-branch-b",
    )
    _ = [event async for event in second.events]

    async with chat_harness.session_factory() as session:
        runs = list(
            await session.scalars(
                select(ChatRun)
                .where(ChatRun.thread_id == thread.thread_id)
                .order_by(ChatRun.created_at)
            )
        )
        assistants = [
            await session.get(ChatMessage, run.assistant_message_id) for run in runs
        ]
    assert len(runs) == 2
    assert assistants[0].content == "第一段第二段"
    assert assistants[1].parent_message_id == assistants[0].parent_message_id
    assert assistants[0].id != assistants[1].id


async def test_chat_rejects_file_context_before_any_provider_call(
    chat_harness,
) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-007",
    )
    with pytest.raises(ChatOperationError) as disabled:
        await chat_harness.service.prepare_stream(
            "access",
            thread.thread_id,
            ChatRunCommand(
                content="读取附件",
                model_id=MODEL_25_ID,
                context_asset_ids=(uuid4(),),
            ),
            "chat-run-file-context",
            trace_id="trace-file-context",
        )
    assert disabled.value.error_code == "chat_file_context_not_enabled"
    assert chat_harness.adapter.requests == []


async def test_run_is_inserted_before_the_assistant_foreign_key_is_bound(
    chat_harness,
) -> None:
    statements: list[str] = []
    engine = chat_harness.session_factory.kw["bind"].sync_engine

    def record_statement(_connection, _cursor, statement, *_args):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        thread = await chat_harness.service.create_thread(
            "access",
            ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
            "thread-create-flush-order",
        )
        await chat_harness.service.prepare_stream(
            "access",
            thread.thread_id,
            ChatRunCommand(content="验证外键顺序", model_id=MODEL_25_ID),
            "chat-run-flush-order",
            trace_id="trace-flush-order",
        )
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    run_insert = next(
        index
        for index, statement in enumerate(statements)
        if statement.startswith("insert into chat_runs")
    )
    message_run_update = next(
        index
        for index, statement in enumerate(statements)
        if statement.startswith("update chat_messages") and "run_id" in statement
    )
    assert run_insert < message_run_update


async def test_provider_initialization_failure_is_persisted_without_fallback(
    chat_harness,
) -> None:
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-008",
    )
    prepared = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(content="只需失败，不要切换模型", model_id=MODEL_25_ID),
        "chat-run-provider-init-failure",
        trace_id="trace-provider-init-failure",
    )
    chat_harness.service._runtime._cipher = BrokenCipher()

    events = [event async for event in prepared.events]

    assert [event.event for event in events] == ["run.started", "run.failed"]
    assert events[-1].payload["error_code"] == "chat_provider_initialization_failed"
    assert chat_harness.adapter.requests == []
    async with chat_harness.session_factory() as session:
        run = await session.get(ChatRun, prepared.run_id)
    assert run.status == "failed"


async def test_provider_contract_failure_does_not_fallback_to_another_model(
    chat_harness,
) -> None:
    adapter = FailingAdapter()
    chat_harness.service._runtime._adapter_factory = lambda _provider: adapter
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-009",
    )
    prepared = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(content="保持所选模型", model_id=MODEL_25_ID),
        "chat-run-provider-contract-failure",
        trace_id="trace-provider-contract-failure",
    )

    events = [event async for event in prepared.events]

    assert [event.event for event in events] == ["run.started", "run.failed"]
    assert events[-1].payload["error_code"] == "provider_response_invalid"
    assert len(adapter.requests) == 1
    assert adapter.requests[0].model == "agnes-2.5-flash"


async def test_cancel_marks_the_partial_message_terminal(chat_harness) -> None:
    adapter = BlockingAdapter()
    chat_harness.service._runtime._adapter_factory = lambda _provider: adapter
    thread = await chat_harness.service.create_thread(
        "access",
        ChatThreadCreateCommand(model_id=MODEL_25_ID, mode="chat"),
        "thread-create-010",
    )
    prepared = await chat_harness.service.prepare_stream(
        "access",
        thread.thread_id,
        ChatRunCommand(content="生成后立即停止", model_id=MODEL_25_ID),
        "chat-run-cancel",
        trace_id="trace-chat-cancel",
    )

    stream_task = asyncio.create_task(
        _collect_events(prepared.events),
    )
    await asyncio.wait_for(adapter.first_delta_sent.wait(), timeout=1)
    await chat_harness.service.cancel_run("access", prepared.run_id)
    events = await asyncio.wait_for(stream_task, timeout=1)

    assert [event.event for event in events] == [
        "run.started",
        "message.delta",
        "run.cancelled_partial",
    ]
    assert events[-1].payload["content"] == "可保留片段"
    async with chat_harness.session_factory() as session:
        run = await session.get(ChatRun, prepared.run_id)
        assistant = await session.get(ChatMessage, run.assistant_message_id)
    assert run.status == "cancelled_partial"
    assert assistant.status == "cancelled_partial"
    assert assistant.content == "可保留片段"


async def _collect_events(events):
    return [event async for event in events]
