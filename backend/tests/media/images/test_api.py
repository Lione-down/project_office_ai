from httpx import ASGITransport, AsyncClient

from app.core.application import AuthServices, create_app
from app.settings.config import Settings

from .conftest import DRAFT_ID, MODEL_ID, SLIDE_IDS


class ReadyDependencies:
    async def check(self) -> dict[str, bool]:
        return {"mysql": True, "redis": True}


async def test_image_api_is_explicit_versioned_and_no_store(image_harness) -> None:
    app = create_app(
        settings=Settings(),
        readiness_checker=ReadyDependencies(),
        auth_services=AuthServices(registration=object(), sessions=object()),
        media_services=image_harness.service,
    )
    headers = {
        "Authorization": "Bearer access",
        "Idempotency-Key": "image-api-create-0001",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            f"/api/v1/deck-drafts/{DRAFT_ID}/media/images",
            headers=headers,
            json={
                "expected_revision": 1,
                "slide_id": str(SLIDE_IDS[1]),
                "action": "generate",
                "prompt": "Synthetic quarterly trend illustration",
                "alt_text": "季度趋势合成插画",
                "model_id": str(MODEL_ID),
                "requested_size": "2K",
                "requested_ratio": "16:9",
                "crop_mode": "cover",
                "confirmed": True,
                "accepted_estimated_credits": 12,
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
    assert created.json()["status"] == "queued"
    assert created.json()["kind"] == "image"
    assert cancelled.json()["status"] == "cancelled"
    assert all(
        response.headers["cache-control"] == "private, no-store"
        for response in (created, detail, cancelled)
    )
