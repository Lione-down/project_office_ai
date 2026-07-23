from hashlib import sha256
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from app.services.quality.presentation.libreoffice import (
    ArtifactDescriptor,
    LibreOfficeError,
    LibreOfficeResponse,
    PageDescriptor,
)
from app.services.quality.presentation.server import create_libreoffice_app


REQUEST_ID = UUID("019b0000-0000-7000-8000-000000000361")
USER_ID = UUID("019b0000-0000-7000-8000-000000000362")
ASSET_ID = UUID("019b0000-0000-7000-8000-000000000363")


class FakeRunner:
    def __init__(self, failure: LibreOfficeError | None = None) -> None:
        self.failure = failure
        self.requests = []

    def convert(self, request):
        self.requests.append(request)
        if self.failure is not None:
            raise self.failure
        return LibreOfficeResponse(
            schema_version="libreoffice-presentation-response.v1",
            request_id=request.request_id,
            status="succeeded",
            libreoffice_version="LibreOffice 25.2.3",
            pdf=ArtifactDescriptor(
                key=f"quality/{REQUEST_ID}/preview.pdf",
                sha256=sha256(b"pdf").hexdigest(),
                byte_size=3,
            ),
            pages=[
                PageDescriptor(
                    key=f"quality/{REQUEST_ID}/pages/page-0001.png",
                    sha256=sha256(b"png").hexdigest(),
                    byte_size=3,
                    page_number=1,
                    width=1280,
                    height=720,
                )
            ],
        )


def payload() -> dict:
    return {
        "schema_version": "libreoffice-presentation-request.v1",
        "request_id": str(REQUEST_ID),
        "user_id": str(USER_ID),
        "asset_id": str(ASSET_ID),
        "source_variant": "original",
        "source_sha256": "a" * 64,
        "source_byte_size": 1024,
    }


async def test_server_exposes_internal_health_and_strict_convert_contract() -> None:
    runner = FakeRunner()
    async with AsyncClient(
        transport=ASGITransport(app=create_libreoffice_app(runner)),
        base_url="http://libreoffice",
    ) as client:
        health = await client.get("/health")
        response = await client.post("/v1/presentation/convert", json=payload())

    assert health.status_code == 200
    assert response.status_code == 200
    assert response.json()["request_id"] == str(REQUEST_ID)
    assert len(runner.requests) == 1


async def test_server_returns_stable_redacted_error() -> None:
    runner = FakeRunner(LibreOfficeError("libreoffice_open_failed", retryable=False))
    async with AsyncClient(
        transport=ASGITransport(app=create_libreoffice_app(runner)),
        base_url="http://libreoffice",
    ) as client:
        response = await client.post("/v1/presentation/convert", json=payload())

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "libreoffice_open_failed",
            "retryable": False,
        }
    }
    assert "path" not in response.text
