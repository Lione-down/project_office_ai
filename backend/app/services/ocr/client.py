from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.services.ocr.contracts import OcrResult, OcrServiceError


class PaddleOcrClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
        max_items: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed_url = urlparse(base_url)
        if (
            parsed_url.scheme != "http"
            or not parsed_url.hostname
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("PaddleOCR URL must be an internal HTTP base URL")
        self._endpoint = base_url.rstrip("/") + "/v1/ocr"
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._max_items = max_items
        self._transport = transport

    async def recognize(
        self,
        image_path: Path,
        *,
        mime_type: str,
        content_sha256: str,
    ) -> OcrResult:
        try:
            image_bytes = await self._read_image(image_path)
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "POST",
                    self._endpoint,
                    content=image_bytes,
                    headers={
                        "Content-Type": mime_type,
                        "X-Content-Sha256": content_sha256,
                    },
                ) as response:
                    if response.status_code in {429, 502, 503, 504}:
                        raise OcrServiceError(
                            "ocr_unavailable",
                            "OCR 服务暂时不可用",
                            retryable=True,
                        )
                    if response.status_code != 200:
                        raise OcrServiceError(
                            "ocr_request_rejected",
                            "OCR 请求被拒绝",
                            retryable=False,
                        )
                    payload = await self._bounded_response(response)
        except OcrServiceError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exception:
            raise OcrServiceError(
                "ocr_unavailable",
                "OCR 服务暂时不可用",
                retryable=True,
            ) from exception
        except OSError as exception:
            raise OcrServiceError(
                "ocr_input_unavailable",
                "OCR 输入不可读取",
                retryable=False,
            ) from exception

        try:
            result = OcrResult.model_validate_json(payload)
        except ValidationError as exception:
            raise OcrServiceError(
                "ocr_response_invalid",
                "OCR 响应格式无效",
                retryable=False,
            ) from exception
        if len(result.items) > self._max_items:
            raise OcrServiceError(
                "ocr_item_limit_exceeded",
                "OCR 识别项超过允许上限",
                retryable=False,
            )
        return result

    @staticmethod
    async def _read_image(image_path: Path) -> bytes:
        return image_path.read_bytes()

    async def _bounded_response(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._max_response_bytes:
                    raise OcrServiceError(
                        "ocr_response_too_large",
                        "OCR 响应超过允许上限",
                        retryable=False,
                    )
            except ValueError as exception:
                raise OcrServiceError(
                    "ocr_response_invalid",
                    "OCR 响应格式无效",
                    retryable=False,
                ) from exception
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            chunks.extend(chunk)
            if len(chunks) > self._max_response_bytes:
                raise OcrServiceError(
                    "ocr_response_too_large",
                    "OCR 响应超过允许上限",
                    retryable=False,
                )
        return bytes(chunks)
