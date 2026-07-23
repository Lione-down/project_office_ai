from hashlib import sha256
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from app.services.renderers.presentation.client import (
    PresentationRendererClient,
    PresentationRendererError,
)
from app.services.renderers.presentation.contracts import (
    PresentationPlan,
    presentation_plan_sha256,
)
from tests.renderers.presentation.test_contracts import valid_plan


REQUEST_ID = UUID("019f5000-0000-7000-8000-000000000111")


async def test_client_verifies_relative_path_size_and_digest(tmp_path: Path) -> None:
    output = tmp_path / "requests" / str(REQUEST_ID) / "presentation.pptx"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"synthetic-pptx")
    digest = sha256(output.read_bytes()).hexdigest()
    plan_sha256 = presentation_plan_sha256(
        PresentationPlan.model_validate(valid_plan())
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/render"
        return httpx.Response(
            200,
            json={
                "schema_version": "ppt-renderer.response.v1",
                "request_id": str(REQUEST_ID),
                "status": "succeeded",
                "output_key": f"requests/{REQUEST_ID}/presentation.pptx",
                "sha256": digest,
                "byte_size": output.stat().st_size,
                "slide_count": 3,
                "template_code": "ppt.executive-blue.v1",
                "template_version": "1.0.0",
                "renderer_version": "ppt-renderer.v1",
                "plan_sha256": plan_sha256,
            },
        )

    client = PresentationRendererClient(
        "http://ppt-renderer:3000",
        tmp_path,
        transport=httpx.MockTransport(handler),
    )

    result = await client.render(REQUEST_ID, valid_plan())

    assert result.path == output
    assert result.sha256 == digest


@pytest.mark.parametrize(
    "output_key",
    ["../secret.pptx", "/absolute/secret.pptx", "C:/secret.pptx"],
)
async def test_client_rejects_renderer_path_escape(
    tmp_path: Path, output_key: str
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "schema_version": "ppt-renderer.response.v1",
                "request_id": str(REQUEST_ID),
                "status": "succeeded",
                "output_key": output_key,
                "sha256": "a" * 64,
                "byte_size": 1,
                "slide_count": 3,
                "template_code": "ppt.executive-blue.v1",
                "template_version": "1.0.0",
                "renderer_version": "ppt-renderer.v1",
                "plan_sha256": "b" * 64,
            },
        )

    client = PresentationRendererClient(
        "http://ppt-renderer:3000",
        tmp_path,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PresentationRendererError, match="renderer_response_invalid"):
        await client.render(REQUEST_ID, valid_plan())


async def test_client_rejects_a_response_for_a_different_plan(
    tmp_path: Path,
) -> None:
    output = tmp_path / "requests" / str(REQUEST_ID) / "presentation.pptx"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"synthetic-pptx")
    digest = sha256(output.read_bytes()).hexdigest()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "schema_version": "ppt-renderer.response.v1",
                "request_id": str(REQUEST_ID),
                "status": "succeeded",
                "output_key": f"requests/{REQUEST_ID}/presentation.pptx",
                "sha256": digest,
                "byte_size": output.stat().st_size,
                "slide_count": 3,
                "template_code": "ppt.executive-blue.v1",
                "template_version": "1.0.0",
                "renderer_version": "ppt-renderer.v1",
                "plan_sha256": "f" * 64,
            },
        )

    client = PresentationRendererClient(
        "http://ppt-renderer:3000",
        tmp_path,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PresentationRendererError, match="renderer_response_invalid"):
        await client.render(REQUEST_ID, valid_plan())


@pytest.mark.parametrize(
    "base_url",
    [
        "file:///private/renderer",
        "http://user:password@ppt-renderer:3000",
        "http://ppt-renderer:3000/v1",
    ],
)
def test_client_rejects_unsafe_base_urls(tmp_path: Path, base_url: str) -> None:
    with pytest.raises(ValueError, match="renderer base URL is invalid"):
        PresentationRendererClient(base_url, tmp_path)


async def test_client_rejects_oversized_plan_before_http_send(
    tmp_path: Path,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("oversized plan must not be sent")

    client = PresentationRendererClient(
        "http://ppt-renderer:3000",
        tmp_path,
        max_request_bytes=100,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PresentationRendererError, match="renderer_request_too_large"):
        await client.render(REQUEST_ID, valid_plan())
