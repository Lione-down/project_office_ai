import httpx
import pytest

from app.providers.agnes import (
    AgnesAdapter,
    ChatCompletionRequest,
    ProviderConfigurationError,
)


def completion_response() -> dict:
    return {
        "id": "agnes-request-1",
        "choices": [
            {
                "message": {"content": '{"status":"ok"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
    }


async def test_adapter_exposes_fixed_contract_and_conservative_defaults() -> None:
    adapter = AgnesAdapter()

    configuration = adapter.validate_configuration({})

    assert configuration.base_url == "https://apihub.agnes-ai.com/v1"
    assert configuration.model == "agnes-2.0-flash"
    assert configuration.context_window == 262_144
    assert configuration.timeout_seconds == 120
    for method_name in (
        "validate_configuration",
        "test_authentication",
        "test_structured_output",
        "test_image_url",
        "create_chat_completion",
        "classify_error",
        "extract_usage",
    ):
        assert callable(getattr(adapter, method_name))


async def test_chat_completion_uses_agnes_contract_and_extracts_usage() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["trace_id"] = request.headers["x-trace-id"]
        captured["body"] = request.read().decode()
        return httpx.Response(200, json=completion_response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = AgnesAdapter(client=client)
        result = await adapter.create_chat_completion(
            api_key="agnes-adapter-test-key",
            request=ChatCompletionRequest(
                model="agnes-2.0-flash",
                messages=[{"role": "user", "content": "ping"}],
                tools=[],
                timeout_seconds=120,
                max_output_tokens=128,
                temperature=0,
                trace_id="trace-agnes-chat",
            ),
        )

    assert captured["authorization"] == "Bearer agnes-adapter-test-key"
    assert captured["trace_id"] == "trace-agnes-chat"
    assert '"max_tokens":128' in captured["body"]
    assert result.provider_request_id == "agnes-request-1"
    assert result.content == '{"status":"ok"}'
    assert result.usage.total_tokens == 18
    assert result.finish_reason == "stop"


async def test_contract_tests_use_mock_http_and_reject_local_image_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=completion_response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = AgnesAdapter(client=client)
        assert await adapter.test_authentication("mock-key") is True
        assert await adapter.test_structured_output("mock-key") is True
        with pytest.raises(ProviderConfigurationError) as error:
            await adapter.test_image_url("mock-key", "http://127.0.0.1/private.png")

    assert len(requests) == 2
    assert error.value.error_code == "image_url_not_public"


@pytest.mark.parametrize(
    ("status_code", "category", "retryable", "disable_credential"),
    [
        (400, "invalid_request", False, False),
        (401, "authentication", False, True),
        (403, "authentication", False, True),
        (429, "rate_limited", True, False),
        (500, "provider_error", True, False),
        (503, "provider_error", True, False),
    ],
)
def test_http_error_classification(
    status_code: int,
    category: str,
    retryable: bool,
    disable_credential: bool,
) -> None:
    response = httpx.Response(status_code, request=httpx.Request("POST", "https://x"))
    error = httpx.HTTPStatusError(
        "provider failed", request=response.request, response=response
    )

    classified = AgnesAdapter().classify_error(error)

    assert classified.category == category
    assert classified.retryable is retryable
    assert classified.disable_credential is disable_credential
    assert classified.uncertain is False


def test_timeout_is_provider_uncertain_and_not_automatically_retried() -> None:
    error = httpx.ReadTimeout(
        "timeout", request=httpx.Request("POST", "https://example.invalid")
    )

    classified = AgnesAdapter().classify_error(error)

    assert classified.category == "provider_uncertain"
    assert classified.retryable is False
    assert classified.uncertain is True
