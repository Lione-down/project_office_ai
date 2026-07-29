import json

import httpx
import pytest

from app.providers.agnes import (
    AgnesAdapter,
    ProviderConfigurationError,
    VideoGenerationRequest,
)


async def test_agnes_video_20_uses_official_create_and_video_id_poll_contract() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert request.url.path == "/v1/videos"
            assert json.loads(request.content) == {
                "model": "agnes-video-v2.0",
                "prompt": "Synthetic geometric shapes moving across a neutral background",
                "width": 1152,
                "height": 768,
                "num_frames": 81,
                "frame_rate": 24,
            }
            return httpx.Response(
                200,
                headers={"x-request-id": "request-create-1"},
                json={
                    "id": "task-opaque-1",
                    "task_id": "task-opaque-1",
                    "video_id": "video-opaque-1",
                    "status": "queued",
                    "progress": 0,
                    "seconds": "3.375",
                    "size": "1152x768",
                },
            )
        assert request.method == "GET"
        assert request.url.path == "/agnesapi"
        assert dict(request.url.params) == {
            "video_id": "video-opaque-1",
            "model_name": "agnes-video-v2.0",
        }
        return httpx.Response(
            200,
            headers={"retry-after": "7", "x-request-id": "request-poll-1"},
            json={
                "id": "task-opaque-1",
                "task_id": "task-opaque-1",
                "video_id": "video-opaque-1",
                "status": "completed",
                "progress": 100,
                "seconds": "3.375",
                "size": "1152x768",
                "metadata": {
                    "url": (
                        "https://platform-outputs.agnes-ai.space/videos/"
                        "agnes-video-v2.0/task-opaque-1.mp4"
                    )
                },
            },
        )

    adapter = AgnesAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    created = await adapter.create_video(
        api_key="test-only-key",
        request=VideoGenerationRequest(
            model="agnes-video-v2.0",
            prompt="Synthetic geometric shapes moving across a neutral background",
            width=1152,
            height=768,
            num_frames=81,
            frame_rate=24,
            negative_prompt=None,
            timeout_seconds=120,
            trace_id="video-contract-create",
        ),
    )
    completed = await adapter.get_video(
        api_key="test-only-key",
        model="agnes-video-v2.0",
        video_id=created.video_id,
        timeout_seconds=120,
        trace_id="video-contract-poll",
    )

    assert created.video_id == "video-opaque-1"
    assert created.task_id == "task-opaque-1"
    assert created.provider_request_id == "request-create-1"
    assert created.status == "queued"
    assert completed.status == "completed"
    assert completed.progress == 100
    assert completed.retry_after_seconds == 7
    assert completed.seconds == pytest.approx(3.375)
    assert completed.width == 1152
    assert completed.height == 768
    assert completed.result_url is not None
    assert len(requests) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"video_id": "video-1", "status": "unknown"},
        {"video_id": "video-1", "status": "completed", "metadata": {}},
        {"status": "queued", "progress": 0},
    ],
)
async def test_agnes_video_rejects_unknown_status_missing_id_or_result(
    payload: dict,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    adapter = AgnesAdapter(
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(ProviderConfigurationError) as error:
        await adapter.create_video(
            api_key="test-only-key",
            request=VideoGenerationRequest(
                model="agnes-video-v2.0",
                prompt="Synthetic motion study",
                width=1152,
                height=768,
                num_frames=81,
                frame_rate=24,
                negative_prompt=None,
                timeout_seconds=120,
                trace_id="video-contract-invalid",
            ),
        )

    assert error.value.error_code == "provider_response_invalid"
