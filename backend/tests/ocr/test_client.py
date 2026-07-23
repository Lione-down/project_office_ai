import json
from pathlib import Path

import httpx
import pytest

from app.services.ocr.client import PaddleOcrClient
from app.services.ocr.contracts import OcrServiceError


def response_payload(*, text: str = "营业收入 123 万元", confidence: float = 0.98):
    return {
        "schema_version": "paddleocr-response.v1",
        "engine": {"name": "PaddleOCR", "version": "3.7.0"},
        "items": [
            {
                "text": text,
                "confidence": confidence,
                "polygon": [[1, 2], [10, 2], [10, 8], [1, 8]],
            }
        ],
    }


async def test_client_sends_raw_image_to_internal_endpoint_and_validates_result(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\ncontent")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://paddleocr:8080/v1/ocr"
        assert request.headers["content-type"] == "image/png"
        assert request.headers["x-content-sha256"] == "a" * 64
        assert await request.aread() == image_path.read_bytes()
        return httpx.Response(200, json=response_payload())

    client = PaddleOcrClient(
        "http://paddleocr:8080",
        timeout_seconds=2,
        max_response_bytes=4096,
        max_items=10,
        transport=httpx.MockTransport(handler),
    )

    result = await client.recognize(
        image_path, mime_type="image/png", content_sha256="a" * 64
    )

    assert result.engine.name == "PaddleOCR"
    assert result.engine.version == "3.7.0"
    assert result.items[0].text == "营业收入 123 万元"
    assert result.items[0].bbox == (1.0, 2.0, 10.0, 8.0)


@pytest.mark.parametrize(
    ("handler", "error_code", "retryable"),
    [
        (
            lambda _request: httpx.Response(503, json={"detail": "loading"}),
            "ocr_unavailable",
            True,
        ),
        (
            lambda _request: httpx.Response(200, content=b"not-json"),
            "ocr_response_invalid",
            False,
        ),
        (
            lambda _request: httpx.Response(
                200,
                json={
                    **response_payload(),
                    "items": response_payload()["items"] * 3,
                },
            ),
            "ocr_item_limit_exceeded",
            False,
        ),
    ],
)
async def test_client_fails_closed_without_returning_partial_evidence(
    tmp_path: Path, handler, error_code: str, retryable: bool
) -> None:
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"image")
    client = PaddleOcrClient(
        "http://paddleocr:8080",
        timeout_seconds=1,
        max_response_bytes=4096,
        max_items=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OcrServiceError) as captured:
        await client.recognize(
            image_path, mime_type="image/png", content_sha256="b" * 64
        )

    assert captured.value.error_code == error_code
    assert captured.value.retryable is retryable


async def test_client_rejects_oversized_response_before_json_use(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "chart.png"
    image_path.write_bytes(b"image")
    oversized = json.dumps(response_payload(text="x" * 4096)).encode()
    client = PaddleOcrClient(
        "http://paddleocr:8080",
        timeout_seconds=1,
        max_response_bytes=128,
        max_items=10,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=oversized)
        ),
    )

    with pytest.raises(OcrServiceError) as captured:
        await client.recognize(
            image_path, mime_type="image/png", content_sha256="c" * 64
        )

    assert captured.value.error_code == "ocr_response_too_large"
    assert captured.value.retryable is False
