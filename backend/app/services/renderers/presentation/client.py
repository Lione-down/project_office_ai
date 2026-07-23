from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.renderers.presentation.contracts import (
    PresentationPlan,
    presentation_plan_sha256,
)


SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class PresentationRendererError(RuntimeError):
    def __init__(self, error_code: str, message: str, *, retryable: bool) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable


class RenderSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["ppt-renderer.response.v1"]
    request_id: Annotated[UUID, Field(strict=False)]
    status: Literal["succeeded"]
    output_key: str
    sha256: str
    byte_size: int = Field(gt=0, le=100 * 1024 * 1024)
    slide_count: int = Field(ge=3, le=30)
    template_code: Literal[
        "ppt.executive-blue.v1",
        "ppt.operating-review.v1",
        "ppt.data-story.v1",
    ]
    template_version: Literal["1.0.0"]
    renderer_version: Literal["ppt-renderer.v1"]
    plan_sha256: str


@dataclass(frozen=True)
class RenderedPresentation:
    path: Path
    sha256: str
    byte_size: int
    slide_count: int
    template_code: str
    template_version: str
    renderer_version: str
    plan_sha256: str


class PresentationRendererClient:
    def __init__(
        self,
        base_url: str,
        work_root: str | Path,
        *,
        timeout_seconds: float = 120,
        max_request_bytes: int = 10 * 1024 * 1024,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed_url = urlsplit(base_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.path not in {"", "/"}
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("renderer base URL is invalid")
        self._base_url = base_url.rstrip("/")
        self._work_root = Path(work_root).resolve()
        self._timeout = timeout_seconds
        self._max_request_bytes = max_request_bytes
        self._transport = transport

    async def render(self, request_id: UUID, plan) -> RenderedPresentation:
        validated_plan = PresentationPlan.validate_for_renderer(plan)
        expected_plan_sha256 = presentation_plan_sha256(validated_plan)
        payload = {
            "schema_version": "ppt-renderer.request.v1",
            "request_id": str(request_id),
            "plan": validated_plan.model_dump(mode="json", exclude_none=True),
        }
        request_content = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(request_content) > self._max_request_bytes:
            raise PresentationRendererError(
                "renderer_request_too_large",
                "PresentationPlan 超过 Renderer 请求上限",
                retryable=False,
            )
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                async with client.stream(
                    "POST",
                    "/v1/render",
                    content=request_content,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    response_status = response.status_code
                    response_type = response.headers.get("content-type", "")
                    response_content = bytearray()
                    async for chunk in response.aiter_bytes():
                        response_content.extend(chunk)
                        if len(response_content) > 64 * 1024:
                            raise self._invalid_response()
            except httpx.HTTPError as exception:
                raise PresentationRendererError(
                    "renderer_unavailable",
                    "PPT Renderer 不可用",
                    retryable=True,
                ) from exception
        if response_type.split(";")[0].strip() != "application/json":
            raise self._invalid_response()
        try:
            body = json.loads(response_content)
        except (UnicodeDecodeError, ValueError) as exception:
            raise self._invalid_response() from exception
        if response_status != 200:
            raise self._remote_error(body)
        try:
            result = RenderSuccess.model_validate(body)
        except ValidationError as exception:
            raise self._invalid_response() from exception
        if (
            result.schema_version != "ppt-renderer.response.v1"
            or result.request_id != request_id
            or result.status != "succeeded"
            or result.renderer_version != "ppt-renderer.v1"
            or result.template_code != validated_plan.template.code
            or result.template_version != validated_plan.template.version
            or not SHA256_PATTERN.fullmatch(result.sha256)
            or not SHA256_PATTERN.fullmatch(result.plan_sha256)
            or result.plan_sha256 != expected_plan_sha256
        ):
            raise self._invalid_response()
        path = self._resolve_output(request_id, result.output_key)
        digest, byte_size = self._digest(path)
        if digest != result.sha256 or byte_size != result.byte_size:
            raise self._invalid_response()
        return RenderedPresentation(
            path=path,
            sha256=digest,
            byte_size=byte_size,
            slide_count=result.slide_count,
            template_code=result.template_code,
            template_version=result.template_version,
            renderer_version=result.renderer_version,
            plan_sha256=result.plan_sha256,
        )

    def _resolve_output(self, request_id: UUID, output_key: str) -> Path:
        key = PurePosixPath(output_key)
        if key.is_absolute() or key.parts != (
            "requests",
            str(request_id),
            "presentation.pptx",
        ):
            raise self._invalid_response()
        path = self._work_root.joinpath(*key.parts).resolve()
        if not path.is_relative_to(self._work_root) or not path.is_file():
            raise self._invalid_response()
        return path

    @staticmethod
    def _digest(path: Path) -> tuple[str, int]:
        digest = sha256()
        byte_size = 0
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                byte_size += len(chunk)
                if byte_size > 100 * 1024 * 1024:
                    raise PresentationRendererClient._invalid_response()
        return digest.hexdigest(), byte_size

    @staticmethod
    def _remote_error(body) -> PresentationRendererError:
        error = body.get("error") if isinstance(body, dict) else None
        if (
            not isinstance(error, dict)
            or not isinstance(error.get("code"), str)
            or not isinstance(error.get("message"), str)
            or not isinstance(error.get("retryable"), bool)
        ):
            return PresentationRendererClient._invalid_response()
        return PresentationRendererError(
            error["code"],
            error["message"][:255],
            retryable=error["retryable"],
        )

    @staticmethod
    def _invalid_response() -> PresentationRendererError:
        return PresentationRendererError(
            "renderer_response_invalid",
            "PPT Renderer 响应无效",
            retryable=False,
        )
