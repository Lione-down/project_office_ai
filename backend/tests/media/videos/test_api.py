from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.settings.config import Settings
from tests.media.images.conftest import DRAFT_ID, MODEL_ID, SLIDE_IDS
from tests.media.videos.test_service_worker import video_runtime


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


async def test_video_api_requires_explicit_page_and_returns_no_store(
    image_harness,
) -> None:
    service, _worker, _adapter = await video_runtime(image_harness)
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        media_services=image_harness.service,
        video_services=service,
    )
    headers = {
        "Authorization": "Bearer access",
        "Idempotency-Key": "video-api-create-0001",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            f"/api/v1/deck-drafts/{DRAFT_ID}/media/videos",
            headers=headers,
            json={
                "expected_revision": 1,
                "slide_id": str(SLIDE_IDS[1]),
                "action": "generate",
                "mode": "text-to-video",
                "prompt": "Synthetic geometric motion study",
                "negative_prompt": "logos, watermarks",
                "model_id": str(MODEL_ID),
                "width": 1152,
                "height": 768,
                "num_frames": 81,
                "frame_rate": 24,
                "confirmed": True,
                "accepted_estimated_credits": 0,
                "embed_requested": False,
            },
        )
        job_id = created.json()["media_job_id"]
        detail = await client.get(
            f"/api/v1/media/jobs/{job_id}",
            headers={"Authorization": "Bearer access"},
        )
        cancelled = await client.post(
            f"/api/v1/media/jobs/{job_id}/cancel",
            headers={"Authorization": "Bearer access"},
        )

    assert [created.status_code, detail.status_code, cancelled.status_code] == [
        202,
        200,
        200,
    ]
    assert created.json()["kind"] == "video"
    assert created.json()["mode"] == "text-to-video"
    assert created.json()["embedding_enabled"] is False
    assert detail.json()["media_job_id"] == job_id
    assert cancelled.json()["status"] == "cancelled"
    assert all(
        response.headers["cache-control"] == "private, no-store"
        for response in (created, detail, cancelled)
    )


async def test_video_api_rejects_public_url_and_embedding_before_service_call(
    image_harness,
) -> None:
    service, _worker, _adapter = await video_runtime(image_harness)
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        media_services=image_harness.service,
        video_services=service,
    )
    payload = {
        "expected_revision": 1,
        "slide_id": str(SLIDE_IDS[1]),
        "action": "generate",
        "mode": "image-to-video",
        "prompt": "Synthetic motion study",
        "model_id": str(MODEL_ID),
        "width": 1152,
        "height": 768,
        "num_frames": 81,
        "frame_rate": 24,
        "confirmed": True,
        "accepted_estimated_credits": 0,
        "embed_requested": True,
        "input_url": "https://example.com/input.png",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/api/v1/deck-drafts/{DRAFT_ID}/media/videos",
            headers={
                "Authorization": "Bearer access",
                "Idempotency-Key": "video-api-create-0002",
            },
            json=payload,
        )

    assert response.status_code == 422
