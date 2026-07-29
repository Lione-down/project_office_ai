import base64
import json

import httpx
import pytest

from app.providers.agnes import (
    AgnesAdapter,
    ImageGenerationRequest,
    ProviderConfigurationError,
)


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAAD0In+KAAAA"
    "FElEQVR42mNkYPj/n4GBgYGJAQoAHgQCAf2J+7sAAAAASUVORK5CYII="
)


@pytest.mark.parametrize(
    ("input_images", "expected_extra_body"),
    [
        ((), None),
        (
            ("data:image/png;base64,AAAA",),
            {
                "image": ["data:image/png;base64,AAAA"],
                "response_format": "b64_json",
            },
        ),
    ],
)
async def test_agnes_image_21_uses_official_size_ratio_and_data_uri_contract(
    input_images: tuple[str, ...],
    expected_extra_body: dict | None,
) -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"x-request-id": "image-request-1"},
            json={
                "created": 1,
                "data": [{"b64_json": base64.b64encode(PNG_BYTES).decode()}],
            },
        )

    adapter = AgnesAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    result = await adapter.create_image(
        api_key="test-only-key",
        request=ImageGenerationRequest(
            model="agnes-image-2.1-flash",
            prompt="Synthetic geometric office illustration",
            size="2K",
            ratio="16:9",
            input_images=input_images,
            timeout_seconds=360,
            trace_id="image-contract",
        ),
    )

    assert captured["model"] == "agnes-image-2.1-flash"
    assert captured["size"] == "2K"
    assert captured["ratio"] == "16:9"
    assert "response_format" not in captured
    if expected_extra_body is None:
        assert captured["return_base64"] is True
        assert "extra_body" not in captured
    else:
        assert captured["extra_body"] == expected_extra_body
    assert result.provider_request_id == "image-request-1"
    assert result.image_bytes == PNG_BYTES


async def test_agnes_image_rejects_ambiguous_or_invalid_response() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"url": "https://example.invalid/output.png"}]},
        )

    adapter = AgnesAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderConfigurationError) as error:
        await adapter.create_image(
            api_key="test-only-key",
            request=ImageGenerationRequest(
                model="agnes-image-2.1-flash",
                prompt="Synthetic image",
                size="2K",
                ratio="16:9",
                input_images=(),
                timeout_seconds=360,
                trace_id="image-contract",
            ),
        )

    assert error.value.error_code == "provider_response_invalid"
