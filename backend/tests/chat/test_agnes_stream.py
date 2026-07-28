import json

import httpx
import pytest

from app.providers.agnes import (
    AgnesAdapter,
    ChatStreamRequest,
    ProviderConfigurationError,
)


async def test_agnes_stream_sends_explicit_model_and_parses_fragmented_sse() -> None:
    captured = {}
    body = (
        'data: {"id":"req-1","choices":[{"delta":{"content":"你好"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"世界"},"finish_reason":"stop"}],'
        '"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}\n\n'
        "data: [DONE]\n\n"
    ).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, content=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = AgnesAdapter(client=client)
        chunks = [
            chunk
            async for chunk in adapter.stream_chat_completion(
                api_key="mock-key",
                request=ChatStreamRequest(
                    model="agnes-2.5-flash",
                    messages=[{"role": "user", "content": "synthetic"}],
                    tools=[],
                    timeout_seconds=120,
                    max_output_tokens=64,
                    trace_id="trace-stream",
                    thinking_enabled=False,
                ),
            )
        ]

    assert captured["payload"]["model"] == "agnes-2.5-flash"
    assert captured["payload"]["stream"] is True
    assert "stream_options" not in captured["payload"]
    assert [chunk.content_delta for chunk in chunks if chunk.content_delta] == [
        "你好",
        "世界",
    ]
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].usage.total_tokens == 7


async def test_agnes_stream_rejects_unregistered_tool_calls() -> None:
    body = (
        'data: {"id":"req-2","choices":[{"delta":{"tool_calls":'
        '[{"id":"call-1","function":{"name":"execute","arguments":"{}"}}]}}]}\n\n'
    ).encode()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = AgnesAdapter(client=client)
        with pytest.raises(ProviderConfigurationError) as rejected:
            _ = [
                chunk
                async for chunk in adapter.stream_chat_completion(
                    api_key="mock-key",
                    request=ChatStreamRequest(
                        model="agnes-2.5-flash",
                        messages=[{"role": "user", "content": "synthetic"}],
                        tools=[],
                        timeout_seconds=120,
                        max_output_tokens=64,
                        trace_id="trace-tool",
                        thinking_enabled=False,
                    ),
                )
            ]
    assert rejected.value.error_code == "chat_tool_not_enabled"
